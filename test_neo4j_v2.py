import os
from dotenv import load_dotenv
load_dotenv()

uri  = os.getenv("NEO4J_URI","")
user = os.getenv("NEO4J_USERNAME","neo4j")
pwd  = os.getenv("NEO4J_PASSWORD","")

print(f"Original URI: {uri}")

import neo4j
print(f"Neo4j driver version: {neo4j.__version__}")

from neo4j import GraphDatabase

uris = list(dict.fromkeys([u for u in [
    uri,
    uri.replace("bolt+ssc://","neo4j+s://"),
    uri.replace("bolt+ssc://","neo4j+ssc://"),
    uri.replace("bolt+ssc://","neo4j://"),
    uri.replace("bolt+ssc://","bolt://"),
] if u]))

db_names = [None, "neo4j", "7ff2e49c", ""]

print("\nTrying all combinations...\n")

for test_uri in uris:
    for db in db_names:
        drv = None
        try:
            drv = GraphDatabase.driver(test_uri, auth=(user,pwd))
            drv.verify_connectivity()
            with drv.session(database=db) as s:
                r = s.run("RETURN 1 as n").single()
                print(f"SUCCESS uri={test_uri.split('//')[1][:20]} db={repr(db)}")
        except Exception as e:
            print(f"FAIL    uri={test_uri.split('//')[1][:20]} db={repr(db)} | {str(e)[:80]}")
        finally:
            try:
                if drv: drv.close()
            except: pass

