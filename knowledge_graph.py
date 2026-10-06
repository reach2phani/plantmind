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
from tracing import traceable, fault_chain_outputs

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


def _plain(value):
    """
    Neo4j date/time values -> ISO text, recursively; everything else unchanged.
    Found 5 Oct 2026: Plant Setup stamps a machine's note with created_at =
    datetime() (equipment_definition.py). Flask can't turn a Neo4j DateTime
    into JSON, so /api/graph/nodes and /api/graph/fault-chain failed for FL-101
    and their fallback showed an EMPTY graph. Every machine added through Plant
    Setup had the same problem; WM-101's note is older and has no date.
    """
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "iso_format"):          # neo4j.time Date / Time / DateTime / Duration
        return value.iso_format()
    return value


def _run(cypher, params=None):
    """Run a Cypher query and return list of dicts (dates as ISO text, see _plain)."""
    driver = _get_driver()
    try:
        with driver.session(database=None) as session:
            result = session.run(cypher, params or {})
            return [_plain(dict(r)) for r in result]
    finally:
        driver.close()


# ─────────────────────────────────────────────────────────────────────────────
# LOAD GRAPH FROM JSON INTO NEO4J
# ─────────────────────────────────────────────────────────────────────────────

def graph_file_name(equip_tag):
    """The seed file for a machine: WM-101 -> wm101_graph.json, FL-101 -> fl101_graph.json."""
    return f"{equip_tag.lower().replace('-', '')}_graph.json"


def graph_has_knowledge(equip_tag):
    """
    True when the machine has real knowledge in Neo4j (faults, fixes, ...),
    not just its own Equipment node. A machine added in Plant Setup has that
    one node, so counting all nodes said "already loaded" and the seed file
    was never loaded for it.
    """
    try:
        r = _run("MATCH (n) WHERE n.equip_tag = $e AND NOT n:Equipment "
                 "RETURN count(n) AS c", {"e": equip_tag})
        return bool(r and r[0]["c"])
    except Exception as e:
        print(f"[KG] graph_has_knowledge error: {e}")
        return True   # unknown: never trigger a reload on a failed check


def load_graph(json_path=None):
    """
    Load graph data from JSON file into Neo4j.
    Clears existing equipment data first. Safe to run multiple times.
    """
    if json_path is None:
        json_path = Path(__file__).parent / "wm101_graph.json"

    print(f"\n[KG] Loading graph from {json_path}...")

    # utf-8 explicitly: the default on Windows (cp1252) silently garbles
    # dashes and arrows into "â€”" instead of failing.
    with open(json_path, encoding="utf-8") as f:
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

            # Refuse a file whose note ids are already used by ANOTHER machine.
            # Nodes are found by _id alone, so a shared id (two machines both
            # calling a note "loto_procedure") would silently take over the
            # other machine's note and cross-link the two graphs.
            clash = session.run(
                "MATCH (n) WHERE n._id IN $ids AND n.equip_tag IS NOT NULL "
                "AND n.equip_tag <> $e RETURN n._id AS id, n.equip_tag AS owner",
                {"ids": [n["id"] for n in nodes], "e": equip}
            ).data()
            if clash:
                for c in clash:
                    print(f"[KG]   ✗ id '{c['id']}' already belongs to {c['owner']}")
                print(f"[KG] ✗ Not loaded: rename those ids in {json_path} (e.g. prefix them)")
                return False

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

            # The Equipment node is NOT deleted, only updated in place below.
            # It also carries the plant map ("is a Filler", "is located at
            # Filling Line 1") from Plant Setup / ontology_bootstrap.py, and
            # deleting it wiped those links on every full reload (known risk).
            session.run(
                "MATCH (n) WHERE n.equip_tag = $e AND NOT n._id IN $keep "
                "AND NOT n:Equipment DETACH DELETE n",
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
                    MATCH (a {{_id: $f, equip_tag: $e}})
                    MATCH (b {{_id: $t, equip_tag: $e}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    SET r += $props
                    """,
                    {"f": rel["from"], "t": rel["to"], "e": equip, "props": props}
                )

            print(f"[KG]   Created {len(rels)} relationships")

            # Re-attach the preserved operator notes. The Equipment node is no
            # longer deleted, so the link normally survives; this MERGE stays
            # as a safety net — a note left floating unreachable is exactly the
            # bug that once hid the correct arc-voltage spec from every report.
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

@traceable(name="knowledge_graph_lookup", process_outputs=fault_chain_outputs)
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

            all_nodes = _plain(equip_node + node_results)   # dates as text (see _plain)

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
            edge_results, pattern_results = _plain(edge_results), _plain(pattern_results)

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

    # Phase 2a — only the MATCHED fault's facts. The graph value test found
    # the warnings, downtime and operator knowledge were built from all ~38
    # nodes, so a gas-alarm report was told burn-in was mandatory and a tip
    # report got the liner job's "1 hour". Everything below now comes from
    # the matched fault's path (plus machine-wide safety such as PPE). When
    # nothing matches the operator's words, relevant = every node, as before.
    # Phase 2a step A: by meaning, with a confidence. Decided ONCE here and
    # passed to the text builder, so both always agree.
    match = match_faults(chain_nodes, chain_edges, incident_text)
    matched, hit = match["relevant"], match["hit"]
    relevant_ids = _relevant_ids(equip_tag, chain_nodes, chain_edges, matched if hit else None)
    relevant_nodes = [n for n in chain_nodes if n["id"] in relevant_ids]
    for n in relevant_nodes:
        p = n["properties"]
        # "total_downtime" is the generic name; "total_with_burnin" is WM-101's.
        if n["type"] == "Procedure" and (p.get("total_downtime") or p.get("total_with_burnin")):
            downtime = p.get("total_downtime") or p["total_with_burnin"]

    # Warnings derived from the notes themselves (see _derive_warnings).
    warnings.extend(_derive_warnings(relevant_nodes))

    # Add pattern warnings
    on_a_fault_path = _relevant_ids(equip_tag, chain_nodes, chain_edges,
                                    [n for n in chain_nodes if n["type"] == "Fault"])
    for r in pattern_results:
        props = r.get("props", {}) or {}
        # A note the reviewer marked as disputed must never become a warning.
        # It is shown separately in the chain text, with the fact that overrules
        # it, so the AI can see the claim AND see that it lost.
        if props.get("status") == "disputed":
            continue
        # Only patterns on the matched path, or approved operator patterns
        # that hang off the machine itself and belong to no fault in particular.
        pid = props.get("_id")
        if pid not in relevant_ids and pid in on_a_fault_path:
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
                                   equip_tag, incident_text, relevant_ids, match=match)

    return {
        "equip_tag":   equip_tag,
        "chain_nodes": chain_nodes,   # full chain: the report diagram still gets everything
        "chain_edges": chain_edges,
        "chain_text":  chain_text,
        "warnings":    warnings,
        "downtime":    downtime,
        # What the AI was actually given facts about (Phase 2a). Used to scope
        # the orchestrator's graph rules, and later by the supervisor.
        "relevant_node_ids": sorted(relevant_ids),
        "matched_faults":    [f["label"] for f in matched] if hit else [],
        # How sure the fault match is (Phase 2a step A). The safety floor is
        # only applied from a "sure" match, never from a close call.
        "match_confidence":  match["confidence"],
        "match_method":      match["method"],
        "no_fault_reported": bool(match.get("not_a_fault")),
        "match_scores":      match["scores"][:3],
        # Real knowledge only: a lone Equipment node (e.g. a machine just added
        # in Plant Setup, before its fault graph exists) is NOT graph data —
        # counting it made the report claim "knowledge graph verified" (FL-101).
        "has_data":    any(n.get("type") != "Equipment" for n in chain_nodes),
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


# Links that make up a fault's path: its causes, their fixes, parts and
# patterns, what each fix requires or includes, its specs and triggered steps.
_PATH_LINKS = {"CAUSED_BY", "FIXED_BY", "REPLACED_WITH", "REQUIRES",
               "REQUIRES_SAFETY", "HAS_PARAMETER", "TRIGGERS", "INCLUDES"}

# Bookkeeping on a note, not a fact for the AI. Everything else is printed.
_HANDOVER_SKIP = {"equip_tag", "plant_site", "line", "line_name", "source", "added_by",
                  "created_at", "candidate_id", "reviewed_at", "repaired_at",
                  "flagged_critical", "status", "overruled_by", "confirmed_count",
                  "source_type", "contributors", "disputed_reason", "operator_summary"}


def _fact_lines(props, indent):
    """
    Every fact on a note, one line each.

    Phase 2a: the old builder printed a fixed list of property names per note
    type, so facts stored under any other name never reached the AI. The graph
    held "allow 10 minutes cooling" and "20 bar" and the reports never said
    either. Printing everything but bookkeeping means a fact cannot be dropped
    because of what it happens to be called, on any machine.
    """
    out = []
    for k, v in (props or {}).items():
        if k.startswith("_") or k in _HANDOVER_SKIP or v in (None, "") or isinstance(v, bool):
            continue
        out.append(f'{indent}{k.replace("_", " ")}: {_clean(str(v))}')
    return out


# ─────────────────────────────────────────────────────────────────────────────
# FAULT MATCHING BY MEANING (Phase 2a step A)
#
# Which fault is the operator describing? Everything downstream depends on it:
# the facts handed to the AI, the required searches, the safety floor.
# Counting shared words (_match_faults below) broke on everyday wording: FL-101
# "underfill alarms ... checkweigher is rejecting them" matched OVERFILL, and
# "pressure dropped to 1.2 bar" tied with Glass Breakage (CRITICAL).
#
# Now: each fault gets a short description card; the card and the question
# are turned into meaning vectors with the same embedding model as document
# search; the closest fault wins IF it is clearly closest. A close call gets a
# second opinion from the word count, then (only then) one short AI question.
# Still unsure -> the close candidates are handed over, marked "unsure", and
# the safety floor is not applied from a guess.
# ─────────────────────────────────────────────────────────────────────────────

# Tuned on evals/fault_match_check.py. e5 similarities sit in a narrow band
# (roughly 0.75-0.90), so the GAP to the runner-up matters more than the level.
MATCH_MIN_SIMILARITY = 0.80
MATCH_MIN_GAP        = 0.03    # 0.02 let two wrong "sure" answers through
MATCH_WORDS_MIN_GAP  = 0.01    # the word count may settle a close call, not a coin toss
MATCH_AI_CANDIDATES  = 3

_card_vectors = {}   # card text -> vector, kept for the life of the process
_pinecone     = None


def _embed(texts, input_type):
    """Meaning vectors from the same model document search uses."""
    global _pinecone
    if _pinecone is None:
        from pinecone import Pinecone
        _pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    res = _pinecone.inference.embed(
        model="multilingual-e5-large", inputs=[t[:2000] for t in texts],
        parameters={"input_type": input_type, "truncate": "END"})
    return [r.values for r in res]


def _fault_card(fault, nodes, edges):
    """A short description of a fault, in the words its notes use."""
    p = fault.get("properties") or {}
    parts = [fault.get("label", "")]
    # How the fault SHOWS UP, in any of the names a graph uses for it.
    # alarm_trigger was missing at first: FL-101's Underfill card had no
    # "checkweigher rejects" while Overfill's did, so "checkweigher is
    # rejecting them" read as Overfill.
    parts += [str(p[k]) for k in ("alarm_message", "alarm_trigger", "symptom",
                                  "definition", "effect") if p.get(k)]
    by_id = {n["id"]: n for n in nodes}
    causes = []
    for e in edges:
        if e["from"] == fault["id"] and e["type"] == "CAUSED_BY" and e["to"] in by_id:
            c = by_id[e["to"]]
            symptom = (c.get("properties") or {}).get("symptom")
            causes.append(c["label"] + (f" ({symptom})" if symptom else ""))
    if causes:
        parts.append("Causes: " + "; ".join(causes))
    return ". ".join(_clean(x).rstrip(". ") for x in parts if x) + "."


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _ai_pick_fault(incident_text, options):
    """
    The tie-breaker: one short multiple-choice question to the small model.
    options = [(fault, card), ...]. Returns a fault, "none", or None (no answer).
    """
    try:
        from groq import Groq
        from models import MODEL_FAST, completion_kwargs
        from token_budget import acquire, settle, estimate_tokens, usage_from_response
        from llm_logger import log_llm_call
    except Exception:
        return None
    listing = "\n".join(f"{i}. {card}" for i, (_, card) in enumerate(options, 1))
    # The question used to assume a fault ("which ONE of these faults are they
    # describing?") with "none" last. Fresh questions (6 Oct 2026) showed the
    # cost: "line's been sitting since Friday, anything special before we
    # start?" became Infeed Jam, and a leak at the valve body became Underfill,
    # both labelled "sure". A plain score cut-off can't separate these from
    # real faults (T-2 "filler's short again" scores 0.798; FR-05 0.792), so
    # the AI is asked the judgement question first.
    prompt = ("An operator on the plant floor wrote:\n"
              f'"{incident_text[:600]}"\n\n'
              "First decide: are they reporting one of the machine faults below, happening now?\n"
              "Answer 0 if they are asking a routine question (for example a start-up, a "
              "changeover, cleaning, or how to do a task) or describing a problem that is "
              "not one of these faults, or if it is not clear.\n\n"
              f"0. Not one of these faults, a routine question, or not clear\n{listing}\n\n"
              "Reply with the number only.")
    kwargs = completion_kwargs(MODEL_FAST, "supervisor", 10)
    reservation = acquire(MODEL_FAST, estimate_tokens([prompt], 600))
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        resp = log_llm_call(
            fn=lambda: client.chat.completions.create(
                model=MODEL_FAST, temperature=0,
                messages=[{"role": "user", "content": prompt}], **kwargs),
            call_type="fault_match", model=MODEL_FAST)
        settle(reservation, usage_from_response(resp))
    except Exception as e:
        settle(reservation, None)
        print(f"[KG] fault-match AI tie-break failed: {str(e)[:80]}")
        return None
    import re as _re
    m = _re.search(r"\d+", resp.choices[0].message.content or "")
    if not m:
        return None
    n = int(m.group(0))
    if n == 0:
        return "none"
    return options[n - 1][0] if 1 <= n <= len(options) else None


def match_faults(nodes, edges, incident_text, use_ai=True):
    """
    Which fault is the operator describing, and how sure are we?

    Returns a dict:
      relevant    faults to write out in full
      others      the rest (listed by name only)
      hit         False = no match: every fault is handed over, as before
      confidence  "sure" | "unsure" | "none" | "words only"
      method      how it was decided (shown in the progress line)
      scores      [(fault label, similarity), ...] best first
    """
    faults = [n for n in nodes if n["type"] == "Fault"]
    w_rel, w_others, w_hit = _match_faults(nodes, edges, incident_text)

    def all_faults(confidence, method, scores=()):
        return {"relevant": faults, "others": [], "hit": False,
                "confidence": confidence, "method": method, "scores": list(scores)}

    if not faults or not (incident_text or "").strip():
        return all_faults("none", "no description")

    try:
        cards = {f["id"]: _fault_card(f, nodes, edges) for f in faults}
        missing = [c for c in cards.values() if c not in _card_vectors]
        if missing:
            for c, v in zip(missing, _embed(missing, "passage")):
                _card_vectors[c] = v
        q = _embed([incident_text], "query")[0]
    except Exception as e:
        # Embedding service down: today's word count, clearly labelled.
        print(f"[KG] meaning match unavailable ({str(e)[:80]}) — using word count")
        return {"relevant": w_rel, "others": w_others, "hit": w_hit,
                "confidence": "words only", "method": "word count (meaning unavailable)",
                "scores": []}

    ranked = sorted(((_cosine(q, _card_vectors[cards[f["id"]]]), f) for f in faults),
                    key=lambda t: -t[0])
    scores = [(f["label"], round(s, 3)) for s, f in ranked]
    best_s, best = ranked[0]
    second_s = ranked[1][0] if len(ranked) > 1 else 0.0

    def chosen(picked, confidence, method):
        ids = {f["id"] for f in picked}
        return {"relevant": picked, "others": [f for f in faults if f["id"] not in ids],
                "hit": True, "confidence": confidence, "method": method, "scores": scores}

    # 1. Clearly closest by meaning.
    if best_s >= MATCH_MIN_SIMILARITY and best_s - second_s >= MATCH_MIN_GAP:
        return chosen([best], "sure", "meaning")
    # 2. Close call, but the word count independently points at the same fault.
    if (best_s >= MATCH_MIN_SIMILARITY and best_s - second_s >= MATCH_WORDS_MIN_GAP
            and w_hit and len(w_rel) == 1 and w_rel[0]["id"] == best["id"]):
        return chosen([best], "sure", "meaning + word count agree")
    # 3. Still unsure: ask the small model to choose between the closest few.
    top = [f for _, f in ranked[:MATCH_AI_CANDIDATES]]
    if use_ai:
        pick = _ai_pick_fault(incident_text, [(f, cards[f["id"]]) for f in top])
        if pick == "none":
            # The AI judged that no fault of this machine is being reported (a
            # routine question, or a different problem). Write out NO fault: the
            # fault chains don't apply, and handing over every fault, as the
            # "can't decide" path does, made the writer's request too big for
            # the free tier (fresh questions, 6 Oct 2026: 413 "request too large"
            # at 8,100-8,800 tokens). Fault names are still listed.
            return {"relevant": [], "others": faults, "hit": True, "not_a_fault": True,
                    "confidence": "none", "method": "AI: not one of these faults",
                    "scores": scores}
        if pick:
            return chosen([pick], "sure", "AI tie-break")
    # 4. No confident answer: hand over the close candidates, marked unsure.
    if best_s < MATCH_MIN_SIMILARITY:
        return all_faults("none", "nothing close by meaning", scores)
    close = [f for s, f in ranked if best_s - s < MATCH_MIN_GAP][:MATCH_AI_CANDIDATES]
    return chosen(close, "unsure", "close call between faults")


def _match_faults(nodes, edges, incident_text):
    """
    Word-count matcher: the backup, and the second opinion for match_faults().
    Which fault(s) does the operator's description match?
    Returns (relevant, others, matched). When nothing matches, every fault is
    relevant and matched is False.
    """
    faults = [n for n in nodes if n["type"] == "Fault"]
    scored = sorted(((_score_fault(f, nodes, edges, incident_text), f) for f in faults),
                    key=lambda t: -t[0])
    best = scored[0][0] if scored else 0
    if best > 0:
        # Only the best-matching fault (plus any tie) is written out in full.
        # Taking every fault with score > 0 was too loose: a wire-feed incident
        # pulled in arc instability and contact-tip faults because they share
        # a cause. The rest are listed by name.
        return ([f for s, f in scored if s == best],
                [f for s, f in scored if s < best], True)
    return [f for _, f in scored], [], False


def _relevant_ids(equip_tag, nodes, edges, faults):
    """
    Every note on the given faults' paths, plus what applies to the whole
    machine (e.g. PPE) and the documents those notes cite. faults=None
    means nothing matched: every note is relevant, as before Phase 2a.
    """
    if faults is None:
        return {n["id"] for n in nodes}
    by_id = {n["id"]: n for n in nodes}
    seen = {f["id"] for f in faults}
    todo = list(seen)
    while todo:
        cur = todo.pop()
        for e in edges:
            if e["from"] == cur and e["type"] in _PATH_LINKS and e["to"] not in seen:
                seen.add(e["to"])
                todo.append(e["to"])
    # A disputed note belongs to the path of the fact that overrules it.
    for n in nodes:
        if (n["properties"] or {}).get("overruled_by") in seen:
            seen.add(n["id"])
    for e in edges:
        # Machine-wide safety (PPE) and the machine's own documents.
        if e["from"] == equip_tag and e["type"] in ("REQUIRES_SAFETY", "DOCUMENTED_IN"):
            seen.add(e["to"])
    for e in edges:
        # Documents cited by anything on the path.
        if (e["from"] in seen and e["type"] in ("DOCUMENTED_IN", "REFERENCED_IN")
                and by_id.get(e["to"], {}).get("type") == "Document"):
            seen.add(e["to"])
    return seen


def _build_chain_text(nodes, edges, warnings, downtime, equip_tag, incident_text="",
                      relevant_ids=None, match=None):
    """
    Turn the graph into text for the orchestrator, KEEPING THE LINKS.

    Each matched fault is written with every fact it holds: its causes (with
    every fact on each), each cause's fix (with its steps, times, torque...),
    the fix's parts, what the fix includes and requires (burn-in, LOTO), the
    fault's specifications and the steps it triggers, each with its source.
    Other faults are listed by name only. A note shared by two causes is
    written once and referred to after that.

    relevant_ids limits operator knowledge, disputed notes and documents to
    the matched path (Phase 2a); None means everything (backup-file path).
    """
    if not nodes:
        return ""

    by_id = {n["id"]: n for n in nodes}
    patterns = [n for n in nodes if n["type"] == "Pattern"]
    documents = [n for n in nodes if n["type"] == "Document"]
    rel = relevant_ids if relevant_ids is not None else {n["id"] for n in nodes}

    def linked(from_id, rel_type):
        return [by_id[e["to"]] for e in edges
                if e["from"] == from_id and e["type"] == rel_type and e["to"] in by_id]

    if match:
        relevant, others = match["relevant"], match["others"]
    else:
        relevant, others, _ = _match_faults(nodes, edges, incident_text)
    lines = [f"KNOWLEDGE GRAPH FOR {equip_tag} — human-reviewed facts, each with its source.", ""]
    if match and match.get("not_a_fault"):
        lines += ["NO MACHINE FAULT REPORTED: the operator's words do not describe one of this "
                  "machine's known faults (a routine question, or a different problem). Answer "
                  "their question from the documents. Do not take a fault, its causes or its "
                  "criticality from the list below.", ""]
    if match and match.get("confidence") == "unsure":
        names = " or ".join(f["label"] for f in relevant)
        lines += [f"FAULT NOT CONFIRMED: the description could be {names}. Say so in the "
                  "report, give the check that tells them apart, and ask the operator to "
                  "confirm. Do not rate criticality from a fault that is not confirmed.", ""]
    written = set()

    def note(n, indent, prefix):
        """Write a note and all its facts once; later, just refer back to it."""
        if n["id"] in written:
            lines.append(f"{indent}{prefix}{n['label']} (details above)")
            return False
        written.add(n["id"])
        lines.append(f"{indent}{prefix}{n['label']}{_src(n['properties'])}")
        lines.extend(_fact_lines(n["properties"], indent + "    "))
        return True

    for fault in relevant:
        written.add(fault["id"])
        lines.append(f"FAULT: {fault['label']}{_src(fault['properties'])}")
        lines.extend(_fact_lines(fault["properties"], "  "))

        for spec in linked(fault["id"], "HAS_PARAMETER"):
            written.add(spec["id"])
            sp = spec["properties"]
            detail = "; ".join(l.strip() for l in _fact_lines(sp, ""))
            lines.append(f'  SPECIFICATION — {spec["label"]}: {detail}{_src(sp)}')

        causes = linked(fault["id"], "CAUSED_BY")
        if causes:
            lines.append("  Possible causes:")
        for c in causes:
            note(c, "    ", "- ")
            for part in linked(c["id"], "REPLACED_WITH"):
                note(part, "        ", "part: ")
            for fix in linked(c["id"], "FIXED_BY"):
                if note(fix, "        ", "fix: "):
                    # What the fix itself demands: the burn-in after a liner
                    # change, LOTO before opening the machine. One hop further
                    # out, and the steps it is dangerous to miss.
                    for inc in linked(fix["id"], "INCLUDES"):
                        note(inc, "            ", "includes: ")
                    for req in linked(fix["id"], "REQUIRES") + linked(fix["id"], "REQUIRES_SAFETY"):
                        note(req, "            ", "then required: ")
            for pat in linked(c["id"], "TRIGGERS"):
                note(pat, "        ", "known pattern: ")

        for t in linked(fault["id"], "TRIGGERS"):
            if note(t, "  ", f"{t['type'].lower()}: ") and t["type"] == "Pattern":
                for req in linked(t["id"], "REQUIRES"):
                    note(req, "      ", "then required: ")
        lines.append("")

    # Safety that applies to ANY work on this machine (PPE, LOTO), whatever
    # fault matched. Linked from the machine itself, so it is never scoped out.
    machine_wide = [by_id[e["to"]] for e in edges
                    if e["from"] == equip_tag and e["type"] == "REQUIRES_SAFETY" and e["to"] in by_id]
    if machine_wide:
        lines.append("Machine-wide safety (applies to any work on this machine):")
        for s in machine_wide:
            note(s, "  ", "")
        lines.append("")

    if others:
        lines.append("Other faults this machine can have (not matching this incident): "
                     + "; ".join(f["label"] for f in others))
        lines.append("")

    # Approved operator knowledge not already written on the path above.
    confirmed = [p for p in patterns if p["properties"].get("status") != "disputed"
                 and p["id"] in rel and p["id"] not in written]
    disputed = [p for p in patterns if p["properties"].get("status") == "disputed"
                and p["id"] in rel]

    if confirmed:
        lines.append("Operator knowledge (reviewed and approved):")
        for p in confirmed:
            pp = p["properties"]
            lines.extend(_fact_lines(pp, "  "))
            summary = _clean(pp.get("operator_summary", ""))
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

    docs = [d for d in documents if d["id"] in rel]
    if docs:
        lines.append("\nRelevant documents:")
        for d in docs:
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
    # Each machine's file is named after its tag: WM-101 -> wm101_graph.json.
    path = Path(__file__).parent / graph_file_name(equip_tag or "")
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
        if node.get("type") == "Procedure" and (props.get("total_downtime") or props.get("total_with_burnin")):
            downtime = props.get("total_downtime") or props["total_with_burnin"]
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
        # Real knowledge only: a lone Equipment node (e.g. a machine just added
        # in Plant Setup, before its fault graph exists) is NOT graph data —
        # counting it made the report claim "knowledge graph verified" (FL-101).
        "has_data":    any(n.get("type") != "Equipment" for n in chain_nodes),
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
                    "properties": _plain({k: v for k, v in dict(n).items() if not k.startswith("_")})
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
                        "properties": _plain(r.get("props", {}) or {}),
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
    """
    Returns the machines that have graph KNOWLEDGE (a fault, fix, procedure...),
    not just their own Equipment note. Every machine added in Plant Setup gets
    that one note, so listing all Equipment notes put a "has graph" tick next to
    machines with nothing to show (5 Oct 2026; same mistake as finding 3 in
    evals/fl101/LEARNINGS.md). Same rule as graph_has_knowledge().
    """
    try:
        results = _run("""
            MATCH (n:Equipment)
            OPTIONAL MATCH (m) WHERE m.equip_tag = n._id AND NOT m:Equipment
            WITH n, count(m) AS facts
            WHERE facts > 0
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


def reinforce_promoted_node(node_id, new_fix_rows, new_confirmed_count, new_summary=""):
    """
    For candidate_type='reinforcement' — a second operator's capture joins an
    already-promoted note instead of creating a duplicate.

    THE BUG THIS FIXES (Phase 1B)
        This used to raise confirmed_count and nothing else. The new capture's
        words were thrown away, and the contributors list — calculated on the
        line below, then never written — was discarded too. The note ended up
        claiming "confirmed by 2 operators" while holding ONE operator's
        content, and sometimes not even naming the second person.

        That is the worst possible direction for the error: confirmed_count is
        the trust signal that makes a note outrank a single unconfirmed tip.
        It grew while the knowledge behind it did not.

        Real damage found in the live graph: THREE reinforcements were approved
        into one arc-voltage note — about a duty-cycle alarm, low gas flow and
        weld spatter. Three unrelated fixes, all silently dropped.

    Now the new capture's summary is APPENDED, with who contributed it, and the
    contributors property is actually written. Nothing is overwritten.
    """
    contributors = sorted({f.get("captured_by_name", "") for f in new_fix_rows if f.get("captured_by_name")})
    addition = (new_summary or "").strip()
    who = ", ".join(contributors) or "an operator"

    driver = _get_driver()
    try:
        with driver.session(database=None) as session:
            existing = session.run(
                "MATCH (n:Pattern {_id: $id}) RETURN n.operator_summary AS s",
                {"id": node_id}
            ).single()
            current = (existing["s"] if existing else "") or ""

            # Only append text that is genuinely new: approving the same
            # candidate twice must not duplicate the paragraph.
            merged = current
            if addition and addition[:60].lower() not in current.lower():
                merged = (current + ("\n\n" if current else "")
                          + f"Also reported by {who}: {addition}")

            session.run(
                """
                MATCH (n:Pattern {_id: $id})
                SET n.confirmed_count = $count,
                    n.contributors     = $contributors,
                    n.operator_summary = $summary,
                    n.source_type = CASE WHEN $count > 1 THEN 'multi_operator' ELSE 'single_operator' END
                """,
                {"id": node_id, "count": new_confirmed_count,
                 "contributors": ", ".join(contributors), "summary": merged}
            )
    finally:
        driver.close()

    print(f"[KG] Reinforced Pattern node {node_id} -> confirmed_count={new_confirmed_count}, "
          f"contributors={who}, content {'merged' if addition else 'unchanged (no new summary given)'}")
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
