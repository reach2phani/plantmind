"""
test_neo4j.py — run this to diagnose Neo4j connection
Usage: python test_neo4j.py
"""
import os
from dotenv import load_dotenv

load_dotenv()

uri      = os.getenv("NEO4J_URI", "NOT SET")
username = os.getenv("NEO4J_USERNAME", "NOT SET")
password = os.getenv("NEO4J_PASSWORD", "NOT SET")

print("=" * 50)
print("Neo4j Connection Test")
print("=" * 50)
print(f"URI      : {uri}")
print(f"Username : {username}")
print(f"Password : {'SET' if password != 'NOT SET' else 'NOT SET'}")
print()

if uri == "NOT SET":
    print("ERROR: NEO4J_URI not found in .env")
    exit(1)

if password == "NOT SET":
    print("ERROR: NEO4J_PASSWORD not found in .env")
    exit(1)

# Test 1 — standard connection
print("Test 1: Standard neo4j+s connection...")
try:
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(uri, auth=(username, password))
    driver.verify_connectivity()
    print("SUCCESS — connected with neo4j+s")
    driver.close()
    exit(0)
except Exception as e:
    print(f"FAILED: {e}")

# Test 2 — bolt+ssc
print()
print("Test 2: Trying bolt+ssc scheme...")
try:
    bolt_uri = uri.replace("neo4j+s://", "bolt+ssc://")
    print(f"URI: {bolt_uri}")
    driver = GraphDatabase.driver(bolt_uri, auth=(username, password))
    driver.verify_connectivity()
    print("SUCCESS — connected with bolt+ssc")
    print()
    print("FIX: Change NEO4J_URI in .env to:")
    print(f"  NEO4J_URI={bolt_uri}")
    driver.close()
    exit(0)
except Exception as e:
    print(f"FAILED: {e}")

# Test 3 — encrypted=True
print()
print("Test 3: Trying with encrypted=True...")
try:
    driver = GraphDatabase.driver(
        uri,
        auth=(username, password),
        encrypted=True
    )
    driver.verify_connectivity()
    print("SUCCESS — connected with encrypted=True")
    driver.close()
    exit(0)
except Exception as e:
    print(f"FAILED: {e}")

# Test 4 — port check
print()
print("Test 4: Checking port 7687 reachability...")
try:
    import socket
    host = uri.replace("neo4j+s://", "").replace("bolt+ssc://", "").split("/")[0]
    s = socket.create_connection((host, 7687), timeout=5)
    s.close()
    print(f"Port 7687 is REACHABLE at {host}")
    print("Port is open but driver still fails — likely a TLS or driver version issue")
except Exception as e:
    print(f"Port 7687 BLOCKED or unreachable: {e}")
    print()
    print("DIAGNOSIS: Port 7687 is blocked.")
    print("Solutions:")
    print("  1. Try a different network (mobile hotspot)")
    print("  2. Check Windows Firewall / antivirus")
    print("  3. Use Neo4j HTTP API instead of Bolt")

print()
print("=" * 50)
print("All tests failed. Share output above for diagnosis.")
print("=" * 50)