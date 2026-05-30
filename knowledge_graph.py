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

            # Clear existing nodes for this equipment
            session.run(
                "MATCH (n) WHERE n.equip_tag = $e DETACH DELETE n",
                {"e": equip}
            )
            print(f"[KG]   Cleared existing {equip} nodes")

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

def get_fault_chain(equip_tag, fault_type=None):
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
    driver = _get_driver()
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
                LIMIT 30
            """, {"equip": equip_tag, "fault_id": fault_id}).data()

            # If no results, get all nodes for equipment
            if not node_results:
                node_results = session.run("""
                    MATCH (n {equip_tag: $equip})
                    WHERE NOT n._type = 'Equipment'
                    RETURN DISTINCT
                        n._id AS id, n._label AS label,
                        n._type AS type, properties(n) AS props
                    LIMIT 30
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
        if nid == "burn_in_procedure":
            warnings.append("Burn-in is MANDATORY after liner replacement. Wire instability in first 5 minutes is EXPECTED — not a fault.")
        if nid == "loto_procedure":
            warnings.append("LOTO required — isolate power at main disconnect before any maintenance.")
        if nid == "quality_flag":
            warnings.append("Parts welded during fault event must be quarantined for quality inspection.")
        if nid == "shielding_gas_low":
            warnings.append("CRITICAL — never weld without shielding gas. Parts welded after alarm must be scrapped.")
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

    # Add pattern warnings
    for r in pattern_results:
        props = r.get("props", {}) or {}
        if props.get("wrong_response"):
            warnings.append(f"Do NOT: {props['wrong_response']}")

    chain_text = _build_chain_text(chain_nodes, chain_edges, warnings, downtime, equip_tag)

    return {
        "equip_tag":   equip_tag,
        "chain_nodes": chain_nodes,
        "chain_edges": chain_edges,
        "chain_text":  chain_text,
        "warnings":    warnings,
        "downtime":    downtime,
        "has_data":    len(chain_nodes) > 0
    }


def _build_chain_text(nodes, edges, warnings, downtime, equip_tag):
    """Build plain English fault chain for LLM orchestrator context."""
    if not nodes:
        return ""

    lines = [f"Knowledge graph context for {equip_tag}:", ""]

    faults     = [n for n in nodes if n["type"] == "Fault"]
    components = [n for n in nodes if n["type"] == "Component"]
    procedures = [n for n in nodes if n["type"] == "Procedure"]
    patterns   = [n for n in nodes if n["type"] == "Pattern"]
    documents  = [n for n in nodes if n["type"] == "Document"]

    if faults:
        lines.append("Known faults:")
        for f in faults:
            msg = f["properties"].get("alarm_message", "")
            lines.append(f"  - {f['label']}" + (f": {msg}" if msg else ""))

    if components:
        lines.append("\nRoot causes:")
        for c in components:
            lines.append(f"  - {c['label']}")
            for e in edges:
                if e["from"] == c["id"] and e["type"] == "FIXED_BY":
                    fix = next((n for n in nodes if n["id"] == e["to"]), None)
                    if fix:
                        lines.append(f"    → Fixed by: {fix['label']}")

    if procedures:
        lines.append("\nRequired procedures:")
        for p in procedures:
            t = p["properties"].get("total_with_burnin", "")
            lines.append(f"  - {p['label']}" + (f" (~{t})" if t else ""))
            if p["properties"].get("mandatory") == "true":
                lines.append(f"    ⚠️  MANDATORY — do not skip")

    if patterns:
        lines.append("\nKnown patterns:")
        for p in patterns:
            wrong   = p["properties"].get("wrong_response", "")
            correct = p["properties"].get("correct_response", "")
            if wrong:   lines.append(f"  ❌ Wrong: {wrong}")
            if correct: lines.append(f"  ✅ Correct: {correct}")

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


def _empty_chain():
    return {
        "equip_tag": "", "chain_nodes": [], "chain_edges": [],
        "chain_text": "", "warnings": [], "downtime": "", "has_data": False
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
