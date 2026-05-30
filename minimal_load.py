"""
Minimal graph loader — stripped down to bare minimum
No lazy init, no caching, direct connection
"""
import os, json
from dotenv import load_dotenv
load_dotenv()

from neo4j import GraphDatabase

URI  = os.getenv("NEO4J_URI", "")
USER = os.getenv("NEO4J_USERNAME", "neo4j")
PWD  = os.getenv("NEO4J_PASSWORD", "")

print(f"URI: {URI}")

# Connect fresh
driver = GraphDatabase.driver(URI, auth=(USER, PWD))
driver.verify_connectivity()
print("Connected OK")

# Load JSON
with open("wm101_graph.json") as f:
    data = json.load(f)

nodes = data["nodes"]
rels  = data["relationships"]
equip = data["metadata"]["equipment"]

print(f"Loading {len(nodes)} nodes, {len(rels)} relationships...")

with driver.session(database=None) as session:

    # Test simple query first
    r = session.run("RETURN 1 as n").single()
    print(f"Simple query OK: {r['n']}")

    # Clear existing
    session.run("MATCH (n) WHERE n.equip_tag = $e DETACH DELETE n", {"e": equip})
    print("Cleared existing nodes")

    # Load nodes one by one
    for node in nodes:
        props = dict(node.get("properties", {}))
        props["_id"]       = node["id"]
        props["_label"]    = node["label"]
        props["_type"]     = node["type"]
        props["equip_tag"] = equip

        label = node["type"].replace(" ", "_")
        session.run(
            f"MERGE (n:{label} {{_id: $id}}) SET n += $props",
            {"id": node["id"], "props": props}
        )

    print(f"Nodes loaded: {len(nodes)}")

    # Load relationships
    for rel in rels:
        session.run(
            f"MATCH (a {{_id:$f}}) MATCH (b {{_id:$t}}) MERGE (a)-[:{rel['type']}]->(b)",
            {"f": rel["from"], "t": rel["to"]}
        )

    print(f"Relationships loaded: {len(rels)}")

# Verify
with driver.session(database=None) as session:
    c = session.run("MATCH (n) WHERE n.equip_tag=$e RETURN count(n) as c", {"e": equip}).single()
    print(f"Verified: {c['c']} nodes in Neo4j")

driver.close()
print("Done")
