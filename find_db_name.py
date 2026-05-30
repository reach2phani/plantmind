"""
find_db_name.py — finds the correct database name for your AuraDB instance
Usage: python find_db_name.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

uri      = os.getenv("NEO4J_URI", "")
username = os.getenv("NEO4J_USERNAME", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "")

# Use bolt+ssc which we know works
connect_uri = uri.replace("neo4j+s://", "bolt+ssc://")
print(f"Connecting to: {connect_uri}")

from neo4j import GraphDatabase

driver = GraphDatabase.driver(connect_uri, auth=(username, password))

# Try without specifying database — uses default
print("\nTrying default database...")
try:
    with driver.session() as session:
        result = session.run("SHOW DATABASES")
        print("Databases found:")
        for record in result:
            print(f"  name={record['name']}  status={record.get('currentStatus', '?')}")
except Exception as e:
    print(f"Cannot list databases: {e}")

# Try common database names
names = ["neo4j", "data", "graph", "plantmind", "db"]
print("\nTrying common database names:")
for name in names:
    try:
        with driver.session(database=name) as session:
            session.run("RETURN 1")
            print(f"  SUCCESS: database name is '{name}'")
            break
    except Exception as e:
        print(f"  FAIL '{name}': {e}")

driver.close()
