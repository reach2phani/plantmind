from neo4j import GraphDatabase

URI = "ef937a24.databases.neo4j.io"
PWD = "CErfWgjYLe-YTTQW2YBjPgS-44WGhy24H2wfPOkOcoo"

combos = [
    (f"neo4j+s://{URI}",   "neo4j",     PWD),
    (f"neo4j+s://{URI}",   "ef937a24",  PWD),
    (f"bolt+ssc://{URI}",  "neo4j",     PWD),
    (f"bolt+ssc://{URI}",  "ef937a24",  PWD),
    (f"neo4j+ssc://{URI}", "neo4j",     PWD),
    (f"neo4j+ssc://{URI}", "ef937a24",  PWD),
]

dbs = [None, "neo4j", "ef937a24"]

print("Testing all combinations...\n")
for uri, user, pwd in combos:
    for db in dbs:
        try:
            d = GraphDatabase.driver(uri, auth=(user, pwd))
            d.verify_connectivity()
            with d.session(database=db) as s:
                s.run("RETURN 1").consume()
            print(f"SUCCESS scheme={uri.split('://')[0]} user={user} db={repr(db)}")
            d.close()
            break
        except Exception as e:
            print(f"FAIL    scheme={uri.split('://')[0]} user={user} db={repr(db)} | {str(e)[:70]}")
            try: d.close()
            except: pass
    print()
