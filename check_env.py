"""Tests connection with SSL verification disabled"""
import os, ssl
from dotenv import load_dotenv
load_dotenv(override=True)

uri  = os.getenv("NEO4J_URI", "")
user = os.getenv("NEO4J_USERNAME", "")
pwd  = os.getenv("NEO4J_PASSWORD", "")

print(f"URI:  {repr(uri)}")
print(f"USER: {repr(user)}")
print()

from neo4j import GraphDatabase

# Test 1 - plain
print("Test 1: plain...")
try:
    d = GraphDatabase.driver(uri, auth=(user, pwd))
    d.verify_connectivity()
    with d.session(database=None) as s:
        s.run("RETURN 1").consume()
    print("SUCCESS")
    d.close()
except Exception as e:
    print(f"FAIL: {str(e)[:100]}")

# Test 2 - encrypted=False
print("Test 2: encrypted=False...")
try:
    d = GraphDatabase.driver(uri, auth=(user, pwd), encrypted=False)
    d.verify_connectivity()
    with d.session(database=None) as s:
        s.run("RETURN 1").consume()
    print("SUCCESS")
    d.close()
except Exception as e:
    print(f"FAIL: {str(e)[:100]}")

# Test 3 - with custom ssl context
print("Test 3: custom ssl context...")
try:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    d = GraphDatabase.driver(uri, auth=(user, pwd))
    d.verify_connectivity()
    with d.session(database=None) as s:
        s.run("RETURN 1").consume()
    print("SUCCESS")
    d.close()
except Exception as e:
    print(f"FAIL: {str(e)[:100]}")

# Test 4 - neo4j+s with trust_all
print("Test 4: neo4j+s with trust_all_certificates...")
try:
    s_uri = uri.replace("bolt+ssc://", "neo4j+s://")
    d = GraphDatabase.driver(
        s_uri, 
        auth=(user, pwd),
        trust="TRUST_ALL_CERTIFICATES"
    )
    d.verify_connectivity()
    with d.session(database=None) as s:
        s.run("RETURN 1").consume()
    print("SUCCESS")
    d.close()
except Exception as e:
    print(f"FAIL: {str(e)[:100]}")

# Test 5 - pip install certifi then retry
print("Test 5: checking certifi...")
try:
    import certifi
    print(f"certifi found: {certifi.where()}")
    import urllib.request
    urllib.request.urlopen(
        f"https://{uri.split('//')[1]}", 
        timeout=5,
        context=ssl.create_default_context(cafile=certifi.where())
    )
    print("HTTPS works with certifi")
except Exception as e:
    print(f"certifi test: {str(e)[:100]}")
