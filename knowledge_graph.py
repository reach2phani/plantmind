"""
PlantMind — Knowledge Graph (knowledge_graph.py)
=================================================
Connects to Neo4j AuraDB and provides graph queries
for investigation enrichment and graph explorer.

Connection: bolt+ssc:// with database=None (AuraDB free tier)
Data:       loaded from wm101_graph.json on first run
"""

import os
import json
import neo4j
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# CONNECTION — fresh driver per operation (matches working minimal_load.py)
# ─────────────────────────────────────────────────────────────────────────────

def _get_driver():
    """Create a fresh Neo4j driver. Caller must close it."""
    import ssl
    from neo4j import GraphDatabase
    uri  = os.getenv("NEO4J_URI", "")
    user = os.getenv("NEO4J_USERNAME", "")
    pwd  = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not pwd:
        raise RuntimeError("NEO4J_URI or NEO4J_PASSWORD not set in .env")
    # Force neo4j+ssc:// — confirmed working on AuraDB free tier + Windows
    connect_uri = uri
    for prefix in ["neo4j+s://", "bolt+ssc://", "bolt://", "neo4j://"]:
        if uri.startswith(prefix):
            connect_uri = "neo4j+ssc://" + uri[len(prefix):]
            break
    driver = GraphDatabase.driver(connect_uri, auth=(user, pwd))
    driver.verify_connectivity()
    return driver


def _run(cypher, params=None):
    """Run a Cypher query and return list of dicts."""
    driver = _get_driver()
    try:
        with driver.session(database=None) as session:
            result = session.run(cypher, params or {})
            return [dict(r) for r in result]
    finally:
        driver.close()


# ─────────────────────────────────────────────────────────────────────────────
# LOAD GRAPH FROM JSON INTO NEO4J
# ─────────────────────────────────────────────────────────────────────────────

def load_graph(json_path=None):
    """
    Load graph data from JSON file into Neo4j.
    Clears existing equipment data first. Safe to run multiple times.
    """
    if json_path is None:
        json_path = Path(__file__).parent / "wm101_graph.json"

    print(f"\n[KG] Loading graph from {json_path}...")

    with open(json_path) as f:
        data = json.load(f)

    meta  = data.get("metadata", {})
    nodes = data.get("nodes", [])
    rels  = data.get("relationships", [])
    equip = meta.get("equipment", "UNKNOWN")

    print(f"[KG]   Equipment : {equip}")
    print(f"[KG]   Nodes     : {len(nodes)}")
    print(f"[KG]   Relations : {len(rels)}")

    driver = _get_driver()
    try:
        with driver.session(database=None) as session:

            # Clear existing nodes for this equipment — EXCEPT operator
            # knowledge promoted through the review queue.
            #
            # Why (Phase 1B): promoted operator notes exist ONLY in Neo4j. They
            # are in no file, so this reload used to delete them permanently —
            # a human-reviewed fact, gone on the next restart, with nothing
            # saying so. The seed file is the source of truth for DOCUMENT
            # facts; it was never the source of truth for operator knowledge.
            preserved = session.run(
                "MATCH (n) WHERE n.equip_tag = $e AND "
                "(n.source_type IS NOT NULL OR n._id STARTS WITH 'opfix_') "
                "RETURN n._id AS id",
                {"e": equip}
            ).data()
            preserved_ids = [p["id"] for p in preserved]

            session.run(
                "MATCH (n) WHERE n.equip_tag = $e AND NOT n._id IN $keep DETACH DELETE n",
                {"e": equip, "keep": preserved_ids}
            )
            print(f"[KG]   Cleared existing {equip} nodes "
                  f"(kept {len(preserved_ids)} promoted operator note(s))")

            # Create nodes
            for node in nodes:
                props = dict(node.get("properties", {}))
                props["_id"]       = node["id"]
                props["_label"]    = node["label"]
                props["_type"]     = node["type"]
                props["plant_site"]= meta.get("plant_site", "")
                props["line"]      = meta.get("line", "")
                props["equip_tag"] = equip
                label = node["type"].replace(" ", "_")
                session.run(
                    f"MERGE (n:{label} {{_id: $id}}) SET n += $props",
                    {"id": node["id"], "props": props}
                )

            print(f"[KG]   Created {len(nodes)} nodes")

            # Create relationships
            for rel in rels:
                rel_type = rel["type"].replace(" ", "_")
                props    = rel.get("properties", {})
                session.run(
                    f"""
                    MATCH (a {{_id: $f}})
                    MATCH (b {{_id: $t}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r += $props
                    """,
                    {"f": rel["from"], "t": rel["to"], "props": props}
                )

            print(f"[KG]   Created {len(rels)} relationships")

            # Re-attach the preserved operator notes. Deleting the Equipment
            # node above also cut the link to them, so without this they would
            # survive the reload but float unreachable — which is exactly the
            # bug that hid the correct arc-voltage spec from every report.
            if preserved_ids:
                session.run(
                    """
                    MATCH (e:Equipment {_id: $e})
                    MATCH (p) WHERE p._id IN $keep
                    MERGE (e)-[:HAS_FAULT]->(p)
                    """,
                    {"e": equip, "keep": preserved_ids}
                )
                print(f"[KG]   Re-attached {len(preserved_ids)} promoted operator note(s)")

        # Verify
        with driver.session(database=None) as session:
            c = session.run(
                "MATCH (n) WHERE n.equip_tag=$e RETURN count(n) as c",
                {"e": equip}
            ).single()
            print(f"[KG]   Verified: {c['c']} nodes in Neo4j")

    finally:
        driver.close()

    print(f"[KG] ✅ Graph loaded successfully\n")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# QUERY — FAULT CHAIN
# Used by multi_agent.py to enrich investigation context
# Used by /api/graph/fault-chain endpoint
# ─────────────────────────────────────────────────────────────────────────────

def get_fault_chain(equip_tag, fault_type=None, incident_text=""):
    """
    Returns the fault chain for equipment and optional fault type.
    Traverses connected nodes up to 5 hops.

    Returns dict with:
      chain_text  — plain English for LLM orchestrator
      chain_nodes — list of node dicts for UI rendering
      chain_edges — list of edge dicts for UI rendering
      warnings    — critical warnings list
      downtime    — estimated downtime string
      has_data    — bool
    """
    try:
        driver = _get_driver()
    except Exception as e:
        # Neo4j unreachable (commonly: Aura free tier auto-paused). Fall back to
        # the local graph file so the verified SOP/NCR warnings still reach the
        # report -- but mark the result as degraded so the report can SAY SO.
        # Silently returning "no graph data" is what made the same WM-101
        # question produce two different reports with no explanation.
        print(f"[KG] Neo4j unavailable ({str(e)[:80]}) -- falling back to local graph file")
        return _fault_chain_from_file(equip_tag, reason="knowledge graph database unreachable")

    try:
        with driver.session(database=None) as session:

            # Get all nodes connected to equipment
            fault_id = fault_type or ""
            node_results = session.run("""
                MATCH (start {equip_tag: $equip})
                WHERE $fault_id = '' OR start._id = $fault_id
                MATCH (start)-[*0..5]->(n)
                WHERE n.equip_tag = $equip
                  AND NOT n._type = 'Equipment'
                RETURN DISTINCT
                    n._id AS id, n._label AS label,
                    n._type AS type, properties(n) AS props
                LIMIT 200   // raised from 30: the graph outgrew it and was silently
                            // dropping notes, burn-in and LOTO among them
            """, {"equip": equip_tag, "fault_id": fault_id}).data()

            # If no results, get all nodes for equipment
            if not node_results:
                node_results = session.run("""
                    MATCH (n {equip_tag: $equip})
                    WHERE NOT n._type = 'Equipment'
                    RETURN DISTINCT
                        n._id AS id, n._label AS label,
                        n._type AS type, properties(n) AS props
                    LIMIT 200   // raised from 30: the graph outgrew it and was silently
                            // dropping notes, burn-in and LOTO among them
                """, {"equip": equip_tag}).data()

            # Get equipment node
            equip_node = session.run("""
                MATCH (n {_id: $id})
                RETURN n._id AS id, n._label AS label,
                       n._type AS type, properties(n) AS props
            """, {"id": equip_tag}).data()

            all_nodes = equip_node + node_results

            # Get edges between these nodes
            node_ids = list(set([r["id"] for r in all_nodes if r.get("id")]))
            edge_results = session.run("""
                MATCH (a)-[r]->(b)
                WHERE a._id IN $ids AND b._id IN $ids
                RETURN a._id AS from_id, b._id AS to_id,
                       type(r) AS rel_type, properties(r) AS props
            """, {"ids": node_ids}).data()

            # Get patterns
            pattern_results = session.run("""
                MATCH (n {equip_tag: $equip})
                WHERE n._type = 'Pattern'
                RETURN properties(n) AS props
            """, {"equip": equip_tag}).data()

    except Exception as e:
        print(f"[KG] fault chain query failed ({str(e)[:80]}) -- falling back to local graph file")
        return _fault_chain_from_file(equip_tag, reason="knowledge graph query failed")
    finally:
        driver.close()

    # Build chain nodes
    chain_nodes = []
    seen_ids    = set()
    warnings    = []
    downtime    = ""

    for r in all_nodes:
        nid = r.get("id", "")
        if not nid or nid in seen_ids:
            continue
        seen_ids.add(nid)
        props = r.get("props", {}) or {}
        chain_nodes.append({
            "id":         nid,
            "label":      r.get("label", nid),
            "type":       r.get("type", ""),
            "properties": props
        })
        # Warnings used to be hard-coded here by node id (burn_in_procedure,
        # loto_procedure, quality_flag, shielding_gas_low) — Known issue #5.
        # A second machine's graph produced NO warnings at all, however good
        # its data. They are now derived from the notes' own properties, by
        # _derive_warnings() below, so any machine gets them for free.
        if r.get("type") == "Procedure" and props.get("total_with_burnin"):
            downtime = props.get("total_with_burnin", "")

    # Build chain edges
    chain_edges = []
    seen_edges  = set()
    for r in edge_results:
        key = f"{r['from_id']}→{r['to_id']}"
        if key in seen_edges:
            continue
        seen_edges.add(key)
        chain_edges.append({
            "from":       r["from_id"],
            "to":         r["to_id"],
            "type":       r["rel_type"],
            "label":      r["rel_type"].replace("_", " ").lower(),
            "properties": r.get("props", {}) or {},
            "warning":    r["rel_type"] in ["REQUIRES", "REQUIRES_SAFETY"]
        })

    # Warnings derived from the notes themselves (see _derive_warnings).
    warnings.extend(_derive_warnings(chain_nodes))

    # Add pattern warnings
    for r in pattern_results:
        props = r.get("props", {}) or {}
        # A note the reviewer marked as disputed must never become a warning.
        # It is shown separately in the chain text, with the fact that overrules
        # it, so the AI can see the claim AND see that it lost.
        if props.get("status") == "disputed":
            continue
        if props.get("wrong_response"):
            warnings.append(f"Do NOT: {props['wrong_response']}")
        # NEW Session 15 follow-up -- operator-confirmed patterns promoted
        # via the graph_candidates review flow carry different properties
        # (operator_summary/source_type/confirmed_count/contributors, not
        # wrong_response/correct_response) -- these were previously fetched
        # here but silently produced no warning at all. Worded distinctly
        # from the formal SOP-derived warnings above: this is field
        # evidence a human reviewed and approved, not an engineering fact.
        elif props.get("operator_summary"):
            count        = props.get("confirmed_count", 1)
            contributors = props.get("contributors", "")
            summary      = props.get("operator_summary", "")
            if props.get("source_type") == "multi_operator":
                lead = f"{count} operators independently confirmed"
            else:
                lead = f"{contributors or 'An operator'} found"
            warnings.append(f"{lead}: {summary}")

    chain_text = _build_chain_text(chain_nodes, chain_edges, warnings, downtime,
                                   equip_tag, incident_text)

    return {
        "equip_tag":   equip_tag,
        "chain_nodes": chain_nodes,
        "chain_edges": chain_edges,
        "chain_text":  chain_text,
        "warnings":    warnings,
        "downtime":    downtime,
        "has_data":    len(chain_nodes) > 0,
        "source":      "neo4j",       # live graph: includes promoted operator patterns
        "degraded":    False,
        "degraded_reason": "",
    }


def _clean(text):
    """
    Repair double-encoded dashes ("â€”") coming from the seed file, and trim.
    Cosmetic, but these land in the AI's context and in operator-facing text.
    """
    if not isinstance(text, str):
        return text
    return (text.replace("â€”", "—").replace("â€“", "–")
                .replace("â€™", "'").replace("Â", "")).strip()


def _src(props):
    """'  [source: WM-101-SOP Section 4.1]' — or nothing if the note has none."""
    s = _clean(props.get("source", ""))
    return f"  [source: {s}]" if s else ""


def _derive_warnings(nodes):
    """
    Build the critical warnings from the notes' OWN properties.

    Before Phase 1B these four warnings were hard-coded by node id, so they
    existed only for WM-101 (Known issue #5). Everything below reads a property
    any machine's graph can carry, so a second machine gets warnings for free:

        Fault.criticality / .quality_impact / .wrong_response
        Procedure.mandatory / .important_note
        Safety.rule / .action
    """
    out = []
    for n in nodes:
        p, label = n.get("properties", {}) or {}, n.get("label", "")
        if n["type"] == "Fault":
            if p.get("criticality"):
                out.append(f'{_clean(p["criticality"])}{_src(p)}')
            if p.get("quality_impact"):
                out.append(f'{label}: {_clean(p["quality_impact"])}{_src(p)}')
            if p.get("wrong_response"):
                out.append(f'Do NOT: {_clean(p["wrong_response"])}{_src(p)}')
        elif n["type"] == "Procedure":
            if str(p.get("mandatory", "")).lower().startswith("true"):
                out.append(f'{label} is MANDATORY — {_clean(p["mandatory"])}{_src(p)}')
            if p.get("important_note"):
                out.append(f'{_clean(p["important_note"])}{_src(p)}')
        elif n["type"] == "Safety":
            for key in ("rule", "action", "required_before"):
                if p.get(key):
                    out.append(f'{label}: {_clean(p[key])}{_src(p)}')
                    break
    # De-duplicate while keeping the order.
    seen, unique = set(), []
    for w in out:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique


def _score_fault(fault, nodes, edges, incident_text):
    """How well does this fault match what the operator actually described?"""
    if not incident_text:
        return 0
    text = incident_text.lower()
    words = set()
    p = fault.get("properties", {}) or {}
    for value in (fault.get("label", ""), p.get("alarm_message", ""), p.get("symptom", "")):
        words |= {w for w in str(value).lower().replace("—", " ").split() if len(w) > 3}
    # Its causes count too: "new spool fitted" should match the overload fault.
    for e in edges:
        if e["from"] == fault["id"] and e["type"] == "CAUSED_BY":
            cause = next((n for n in nodes if n["id"] == e["to"]), None)
            if cause:
                words |= {w for w in cause["label"].lower().split() if len(w) > 3}
    return sum(1 for w in words if w in text)


def _build_chain_text(nodes, edges, warnings, downtime, equip_tag, incident_text=""):
    """
    Turn the graph into text for the orchestrator — KEEPING THE LINKS.

    The old version printed one list of faults and a separate list of causes,
    so the AI could not tell which cause belonged to which fault: it received
    31 of 34 notes for every incident, with the connections stripped out. The
    graph's whole advantage was thrown away in the last step before the AI.

    Now each fault is written with its own causes, each cause with its own fix
    and part, plus the fault's specification and the source of every fact. When
    the operator's description matches a fault, that fault is written in full
    and the others are listed by name only.
    """
    if not nodes:
        return ""

    by_id = {n["id"]: n for n in nodes}
    faults = [n for n in nodes if n["type"] == "Fault"]
    patterns = [n for n in nodes if n["type"] == "Pattern"]
    documents = [n for n in nodes if n["type"] == "Document"]

    def linked(from_id, rel):
        return [by_id[e["to"]] for e in edges
                if e["from"] == from_id and e["type"] == rel and e["to"] in by_id]

    lines = [f"KNOWLEDGE GRAPH FOR {equip_tag} — human-reviewed facts, each with its source.", ""]

    scored = sorted(((_score_fault(f, nodes, edges, incident_text), f) for f in faults),
                    key=lambda t: -t[0])
    best = scored[0][0] if scored else 0
    if best > 0:
        # Only the best-matching fault (plus any tie) is written out in full.
        # Taking every fault with score > 0 was still too loose: a wire-feed
        # incident pulled in arc instability and contact-tip faults too,
        # because they share a cause. The rest are listed by name, so the AI
        # knows they exist without the report drowning in them.
        relevant = [f for s, f in scored if s == best]
        others = [f for s, f in scored if s < best]
    else:
        relevant, others = [f for _, f in scored], []   # nothing matched — show all

    for fault in relevant:
        p = fault["properties"]
        lines.append(f"FAULT: {fault['label']}{_src(p)}")
        if p.get("alarm_message"):
            lines.append(f'  Alarm: "{_clean(p["alarm_message"])}"')
        if p.get("frequency_trigger"):
            lines.append(f'  Note: {_clean(p["frequency_trigger"])}')
        if p.get("correct_response"):
            lines.append(f'  Correct response: {_clean(p["correct_response"])}')

        for spec in linked(fault["id"], "HAS_PARAMETER"):
            sp = spec["properties"]
            # Print whatever the spec actually holds. An allow-list of property
            # names printed the tension spec as an empty line, because its
            # values live under correct_setting / too_tight_effect.
            detail = ", ".join(f"{k.replace('_', ' ')}: {_clean(v)}"
                               for k, v in sp.items()
                               if not k.startswith("_")
                               and k not in ("equip_tag", "plant_site", "line", "source",
                                             "added_by"))
            lines.append(f'  SPECIFICATION — {spec["label"]}: {detail}{_src(sp)}')

        causes = linked(fault["id"], "CAUSED_BY")
        if causes:
            lines.append("  Possible causes:")
            for c in causes:
                cp = c["properties"]
                lines.append(f'    - {c["label"]}{_src(cp)}')
                for key in ("wear_indicator", "distinguishing_sign", "service_interval",
                            "check", "effect", "evidence"):
                    if cp.get(key):
                        lines.append(f'        {key.replace("_", " ")}: {_clean(cp[key])}')
                for fix in linked(c["id"], "FIXED_BY"):
                    fp = fix["properties"]
                    mins = fp.get("total_with_burnin") or fp.get("expected_time", "")
                    lines.append(f'        fix: {fix["label"]}'
                                 + (f" (~{_clean(mins)})" if mins else "") + _src(fp))
                for part in linked(c["id"], "REPLACED_WITH"):
                    lines.append(f'        part: {part["label"]}')
                # What the fix itself demands — the burn-in after a liner
                # change, LOTO before opening the machine. These sit one hop
                # further out, and they are the steps it is dangerous to miss.
                for fix in linked(c["id"], "FIXED_BY"):
                    for req in linked(fix["id"], "REQUIRES") + linked(fix["id"], "REQUIRES_SAFETY"):
                        rp = req["properties"]
                        note = _clean(rp.get("method") or rp.get("steps") or
                                      rp.get("mandatory") or "")
                        lines.append(f'        then required: {req["label"]}'
                                     + (f" — {note[:120]}" if note else "") + _src(rp))
        for safety in linked(fault["id"], "TRIGGERS"):
            if safety["type"] == "Safety":
                lines.append(f'  Safety: {safety["label"]}'
                             f'{_src(safety["properties"])}')
        lines.append("")

    if others:
        lines.append("Other faults this machine can have (not matching this incident): "
                     + "; ".join(f["label"] for f in others))
        lines.append("")

    confirmed = [p for p in patterns if p["properties"].get("status") != "disputed"]
    disputed = [p for p in patterns if p["properties"].get("status") == "disputed"]

    if confirmed:
        lines.append("Operator knowledge (reviewed and approved):")
        for p in confirmed:
            pp = p["properties"]
            wrong, correct = _clean(pp.get("wrong_response", "")), _clean(pp.get("correct_response", ""))
            summary = _clean(pp.get("operator_summary", ""))
            if wrong:
                lines.append(f"  Wrong response: {wrong}")
            if correct:
                lines.append(f"  Correct response: {correct}")
            if summary:
                count = pp.get("confirmed_count", 1)
                who = pp.get("contributors", "")
                lead = (f"{count} operators independently confirmed"
                        if pp.get("source_type") == "multi_operator"
                        else f"{who or 'An operator'} found")
                lines.append(f"  {lead}: {summary}")
        lines.append("")

    if disputed:
        # Shown, not hidden: the AI must know the claim exists AND that it lost,
        # so it can answer an operator who repeats it. Never as a warning.
        lines.append("DISPUTED — operator claims that a documented fact overrules. "
                     "Do NOT use these as specifications:")
        for p in disputed:
            pp = p["properties"]
            claim = _clean(pp.get("operator_summary") or p["label"])
            wins = by_id.get(pp.get("overruled_by", ""))
            lines.append(f"  Claim: {claim[:220]}")
            lines.append(f"  Why it is rejected: {_clean(pp.get('disputed_reason', ''))}")
            if wins:
                lines.append(f"  Use instead: {wins['label']} — "
                             f"{_clean(wins['properties'].get('normal_range', ''))}"
                             f"{_src(wins['properties'])}")
        lines.append("")

    if warnings:
        lines.append("\nCritical warnings:")
        for w in warnings:
            lines.append(f"  ⚠️  {w}")

    if downtime:
        lines.append(f"\nEstimated downtime: {downtime}")

    if documents:
        lines.append("\nRelevant documents:")
        for d in documents:
            lines.append(f"  - {d['label']}")

    return "\n".join(lines)


def _fault_chain_from_file(equip_tag, reason=""):
    """
    Fallback fault chain, built from the local wm101_graph.json instead of Neo4j.

    Used ONLY when the database is unreachable. It returns the same shape as
    get_fault_chain() so nothing downstream needs to care, with two differences
    the caller must surface to the user:
      * source == "local_file"
      * promoted operator patterns are MISSING -- they live only in Neo4j, so a
        degraded report is missing the human-reviewed field knowledge.
    """
    path = Path(__file__).parent / "wm101_graph.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[KG] local graph file unusable: {e}")
        out = _empty_chain()
        out.update({"equip_tag": equip_tag, "source": "unavailable", "degraded": True,
                    "degraded_reason": reason or "knowledge graph unavailable"})
        return out

    meta = data.get("metadata", {})
    if (meta.get("equipment") or "").upper() != (equip_tag or "").upper():
        # The local file only covers one machine; anything else genuinely has
        # no graph data, degraded or not.
        out = _empty_chain()
        out.update({"equip_tag": equip_tag, "source": "unavailable", "degraded": True,
                    "degraded_reason": reason or "knowledge graph unavailable"})
        return out

    chain_nodes, warnings, downtime = [], [], ""
    for node in data.get("nodes", []):
        if node.get("type") == "Equipment":
            continue
        props = dict(node.get("properties", {}))
        chain_nodes.append({"id": node["id"], "label": node.get("label", node["id"]),
                            "type": node.get("type", ""), "properties": props})
        if node["id"] == "burn_in_procedure":
            warnings.append("Burn-in is MANDATORY after liner replacement. Wire instability in first 5 minutes is EXPECTED — not a fault.")
        if node["id"] == "loto_procedure":
            warnings.append("LOTO required — isolate power at main disconnect before any maintenance.")
        if node["id"] == "quality_flag":
            warnings.append("Parts welded during fault event must be quarantined for quality inspection.")
        if node["id"] == "shielding_gas_low":
            warnings.append("CRITICAL — never weld without shielding gas. Parts welded after alarm must be scrapped.")
        if node.get("type") == "Procedure" and props.get("total_with_burnin"):
            downtime = props["total_with_burnin"]
        if node.get("type") == "Pattern" and props.get("wrong_response"):
            warnings.append(f"Do NOT: {props['wrong_response']}")

    node_ids = {n["id"] for n in chain_nodes}
    chain_edges = [{
        "from": r["from"], "to": r["to"], "type": r["type"],
        "label": r["type"].replace("_", " ").lower(),
        "properties": r.get("properties", {}) or {},
        "warning": r["type"] in ["REQUIRES", "REQUIRES_SAFETY"],
    } for r in data.get("relationships", []) if r["from"] in node_ids and r["to"] in node_ids]

    return {
        "equip_tag":   equip_tag,
        "chain_nodes": chain_nodes,
        "chain_edges": chain_edges,
        "chain_text":  _build_chain_text(chain_nodes, chain_edges, warnings, downtime, equip_tag),
        "warnings":    warnings,
        "downtime":    downtime,
        "has_data":    len(chain_nodes) > 0,
        "source":      "local_file",
        "degraded":    True,
        "degraded_reason": reason or "knowledge graph database unreachable",
    }


def _empty_chain():
    return {
        "equip_tag": "", "chain_nodes": [], "chain_edges": [],
        "chain_text": "", "warnings": [], "downtime": "", "has_data": False,
        "source": "none", "degraded": False, "degraded_reason": "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# QUERY — FULL GRAPH FOR EXPLORER
# ─────────────────────────────────────────────────────────────────────────────

def get_full_graph(equip_tag=None, plant_site=None, node_type=None):
    """Returns all nodes and edges for the graph explorer (/graph page)."""
    driver = _get_driver()
    try:
        with driver.session(database=None) as session:

            # Build filters
            conditions = []
            params     = {}
            if equip_tag:
                conditions.append("n.equip_tag = $equip_tag")
                params["equip_tag"] = equip_tag
            if plant_site:
                conditions.append("n.plant_site = $plant_site")
                params["plant_site"] = plant_site
            if node_type:
                conditions.append("n._type = $node_type")
                params["node_type"] = node_type

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

            node_results = session.run(
                f"MATCH (n) {where} RETURN n", params
            ).data()

            nodes    = []
            node_ids = set()
            for r in node_results:
                n   = r["n"]
                nid = n.get("_id", "")
                if not nid or nid in node_ids:
                    continue
                node_ids.add(nid)
                nodes.append({
                    "id":         nid,
                    "label":      n.get("_label", nid),
                    "type":       n.get("_type", ""),
                    "properties": {k: v for k, v in dict(n).items() if not k.startswith("_")}
                })

            edges = []
            if node_ids:
                edge_results = session.run("""
                    MATCH (a)-[r]->(b)
                    WHERE a._id IN $ids AND b._id IN $ids
                    RETURN a._id AS from_id, b._id AS to_id,
                           type(r) AS rel_type, properties(r) AS props
                """, {"ids": list(node_ids)}).data()

                seen = set()
                for r in edge_results:
                    key = f"{r['from_id']}→{r['to_id']}"
                    if key in seen:
                        continue
                    seen.add(key)
                    edges.append({
                        "from":       r["from_id"],
                        "to":         r["to_id"],
                        "type":       r["rel_type"],
                        "label":      r["rel_type"].replace("_", " ").lower(),
                        "properties": r.get("props", {}) or {},
                        "warning":    r["rel_type"] in ["REQUIRES", "REQUIRES_SAFETY"]
                    })

    finally:
        driver.close()

    return {
        "nodes": nodes,
        "edges": edges,
        "count": {"nodes": len(nodes), "edges": len(edges)}
    }


# ─────────────────────────────────────────────────────────────────────────────
# QUERY — STATS + EQUIPMENT LIST
# ─────────────────────────────────────────────────────────────────────────────

def get_graph_stats(equip_tag=None):
    """Returns node and edge counts."""
    try:
        driver = _get_driver()
        try:
            with driver.session(database=None) as session:
                params = {}
                where  = ""
                if equip_tag:
                    where  = "WHERE n.equip_tag = $e"
                    params = {"e": equip_tag}
                nc = session.run(f"MATCH (n) {where} RETURN count(n) as c", params).single()
                where2 = "WHERE a.equip_tag=$e AND b.equip_tag=$e" if equip_tag else ""
                ec = session.run(f"MATCH (a)-[r]->(b) {where2} RETURN count(r) as c", params).single()
                return {"nodes": nc["c"], "edges": ec["c"]}
        finally:
            driver.close()
    except Exception as e:
        print(f"[KG] get_graph_stats error: {e}")
        return {"nodes": 0, "edges": 0}


def get_graphed_equipment():
    """Returns list of equipment that have graph data."""
    try:
        results = _run("""
            MATCH (n:Equipment)
            RETURN n._id AS id, n._label AS label,
                   n.plant_site AS plant_site,
                   n.line AS line, n.line_name AS line_name
            ORDER BY n.plant_site, n.line, n._id
        """)
        return results
    except Exception as e:
        print(f"[KG] get_graphed_equipment error: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# WRITE — PROMOTE AN EXPERT-FIX CANDIDATE INTO THE GRAPH (NEW, Session 15)
# Used by app.py POST /api/graph-candidates/<id>/approve
# The ONLY write path into Neo4j at runtime besides load_graph() -- every
# other function in this file is read-only. Never called automatically;
# only ever from the human-approved review flow.
# ─────────────────────────────────────────────────────────────────────────────

def debug_pattern_nodes(equip_tag):
    """
    Diagnostic only -- bypasses get_full_graph()'s filtering, layoutNodes()'s
    rendering, and get_fault_chain()'s traversal entirely. Runs the most
    direct possible query: every Pattern-type node, no filter at all, so we
    can see the RAW equip_tag values actually stored on them and compare
    against what's being searched for -- this is exactly the kind of "is it
    a write problem or a query-mismatch problem" question that's hard to
    answer by staring at the UI.
    """
    driver = _get_driver()
    try:
        with driver.session(database=None) as session:
            all_patterns = session.run(
                "MATCH (n) WHERE n._type = 'Pattern' RETURN properties(n) AS props"
            ).data()
            equip_node = session.run(
                "MATCH (e:Equipment) WHERE e._id = $tag OR e.equip_tag = $tag "
                "RETURN e._id AS id, e._label AS label, properties(e) AS props",
                {"tag": equip_tag}
            ).data()
            has_fault_edges = session.run(
                "MATCH (a)-[r:HAS_FAULT]->(b) RETURN a._id AS from_id, b._id AS to_id, b._type AS to_type"
            ).data()
    finally:
        driver.close()

    return {
        "searched_for_equip_tag": equip_tag,
        "all_pattern_nodes_in_db": all_patterns,
        "equipment_nodes_matching_tag": equip_node,
        "all_has_fault_edges_in_db": has_fault_edges,
    }


def promote_candidate_to_graph(candidate, fix_rows):
    """
    Writes ONE new Pattern node for an approved graph_candidates row, and
    connects it to its Equipment node via HAS_FAULT (the closest existing
    relationship type -- a confirmed operator pattern is a kind of
    recurring fault behaviour, same category as the graph's existing
    hand-authored Pattern nodes).

    Deliberately uses NEW property names (operator_summary, source_type,
    confirmed_count, contributors) rather than the Session-12 Pattern
    properties (wrong_response/correct_response) -- so this never
    accidentally triggers the existing hard-coded warning logic in
    get_fault_chain()/the orchestrator. Generalising THAT logic to also
    recognise operator-confirmed patterns is deferred, tracked in
    CONTEXT.md Known issues -- this function only needs to write correctly,
    not make itself visible in reports yet.

    candidate: dict from graph_candidates row (id, equip_tag, fix_ids,
               candidate_type, flagged_by_operator, summary)
    fix_rows:  list of expert_fixes rows that fed this candidate (for
               contributor names + captured_at)

    Returns the Neo4j node _id on success, raises on failure -- the
    caller (app.py) decides how to handle/report that, this function
    does not swallow errors, since a failed promotion must not silently
    look like a successful one.
    """
    equip_tag = candidate["equip_tag"]
    node_id   = f"opfix_{candidate['id']}"

    contributors    = sorted(set(f.get("captured_by_name", "") for f in fix_rows if f.get("captured_by_name")))
    source_type     = "multi_operator" if len(contributors) > 1 else "single_operator"
    confirmed_count = len(fix_rows)

    label_source = candidate.get("summary") or (fix_rows[0].get("what_fixed_it", "") if fix_rows else "")
    short_label  = (label_source[:60] + "...") if len(label_source) > 60 else label_source

    props = {
        "_id":               node_id,
        "_label":            short_label or f"Operator-confirmed pattern ({equip_tag})",
        "_type":             "Pattern",
        "equip_tag":         equip_tag,
        "plant_site":        fix_rows[0].get("plant_site", "") if fix_rows else "",
        "line":              fix_rows[0].get("line", "") if fix_rows else "",
        "operator_summary":  candidate.get("summary") or "",
        "source_type":       source_type,
        "confirmed_count":   confirmed_count,
        "contributors":      ", ".join(contributors),
        "flagged_critical":  bool(candidate.get("flagged_by_operator")),
        "candidate_id":      str(candidate["id"]),
    }

    driver = _get_driver()
    try:
        with driver.session(database=None) as session:
            session.run(
                "MERGE (n:Pattern {_id: $id}) SET n += $props",
                {"id": node_id, "props": props}
            )
            # Connect to the Equipment node -- HAS_FAULT is the existing
            # relationship type closest in meaning; matches only on
            # equip_tag since Equipment nodes are keyed by their tag.
            session.run(
                """
                MATCH (e:Equipment {_id: $equip})
                MATCH (p:Pattern {_id: $node_id})
                MERGE (e)-[r:HAS_FAULT]->(p)
                SET r.source = 'expert_fix_promotion'
                """,
                {"equip": equip_tag, "node_id": node_id}
            )
    finally:
        driver.close()

    print(f"[KG] Promoted candidate {candidate['id']} -> Pattern node {node_id} ({source_type}, {confirmed_count} sources)")
    return node_id


def reinforce_promoted_node(node_id, new_fix_rows, new_confirmed_count):
    """
    For candidate_type='reinforcement' -- updates an ALREADY-promoted
    node's confirmed_count and contributors rather than creating a
    duplicate node. Still only ever called from the human-approved
    review flow, same as promote_candidate_to_graph.
    """
    contributors = sorted(set(f.get("captured_by_name", "") for f in new_fix_rows if f.get("captured_by_name")))
    driver = _get_driver()
    try:
        with driver.session(database=None) as session:
            session.run(
                """
                MATCH (n:Pattern {_id: $id})
                SET n.confirmed_count = $count,
                    n.source_type = CASE WHEN $count > 1 THEN 'multi_operator' ELSE 'single_operator' END
                """,
                {"id": node_id, "count": new_confirmed_count}
            )
    finally:
        driver.close()
    print(f"[KG] Reinforced Pattern node {node_id} -> confirmed_count={new_confirmed_count}")
    return node_id


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE — run to load graph data
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PlantMind Knowledge Graph Loader")
    print("="*60)

    success = load_graph("wm101_graph.json")

    if success:
        print("--- Verifying queries ---\n")

        print("Testing get_fault_chain('WM-101', 'wire_feed_overload')...")
        chain = get_fault_chain("WM-101", "wire_feed_overload")
        print(f"  has_data    : {chain['has_data']}")
        print(f"  nodes found : {len(chain['chain_nodes'])}")
        print(f"  warnings    : {len(chain['warnings'])}")
        if chain["downtime"]:
            print(f"  downtime    : {chain['downtime']}")
        if chain["chain_text"]:
            preview = "\n  ".join(chain["chain_text"].split("\n")[:8])
            print(f"\n  Chain text preview:\n  {preview}")

        print("\nTesting get_full_graph('WM-101')...")
        graph = get_full_graph(equip_tag="WM-101")
        print(f"  nodes : {graph['count']['nodes']}")
        print(f"  edges : {graph['count']['edges']}")

        stats = get_graph_stats(equip_tag="WM-101")
        print(f"\nStats: {stats}")

        equip = get_graphed_equipment()
        print(f"Equipment with graph data: {[e['id'] for e in equip]}")

        print("\n✅ Knowledge graph ready")
