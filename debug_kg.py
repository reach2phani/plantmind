import os
from dotenv import load_dotenv

# Force reload — ignore any cached values
load_dotenv(override=True)

uri  = os.getenv("NEO4J_URI", "NOT SET")
user = os.getenv("NEO4J_USERNAME", "NOT SET")
pwd  = os.getenv("NEO4J_PASSWORD", "NOT SET")

print(f"NEO4J_URI      = {repr(uri)}")
print(f"NEO4J_USERNAME = {repr(user)}")
print(f"NEO4J_PASSWORD = {'SET' if pwd != 'NOT SET' else 'NOT SET'}")
print()

from neo4j import GraphDatabase

# Try the URI exactly as-is first
print(f"Test 1: URI as-is ({uri})...")
try:
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    with driver.session(database=None) as s:
        r = s.run("RETURN 1 as n").single()
        print(f"SUCCESS — RETURN 1 = {r['n']}")
    driver.close()
except Exception as e:
    print(f"FAIL: {str(e)[:120]}")
    driver = None

# If failed, try bolt+ssc
if not driver:
    bolt_uri = uri.replace("neo4j+s://", "bolt+ssc://")
    print(f"\nTest 2: bolt+ssc ({bolt_uri})...")
    try:
        driver = GraphDatabase.driver(bolt_uri, auth=(user, pwd))
        driver.verify_connectivity()
        with driver.session(database=None) as s:
            r = s.run("RETURN 1 as n").single()
            print(f"SUCCESS — RETURN 1 = {r['n']}")
            print(f"\nFIX: Set NEO4J_URI={bolt_uri} in .env")
        driver.close()
    except Exception as e:
        print(f"FAIL: {str(e)[:120]}")
