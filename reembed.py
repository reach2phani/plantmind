from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
import os
from embedder import embed_document

s = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
docs = s.table("documents").select("*").eq("status", "uploaded").execute()

base = os.path.dirname(os.path.abspath(__file__))
print("Base folder:", base)
print("Documents found:", len(docs.data))
print("")

total_chunks = 0
for doc in docs.data:
    raw_path = doc.get("file_path", "")
    full_path = os.path.join(base, raw_path)
    print("Trying:", full_path)
    if os.path.exists(full_path):
        chunks = embed_document(doc["id"], full_path, doc)
        print("OK -", chunks, "chunks for", doc["name"])
        total_chunks += chunks
    else:
        print("NOT FOUND -", doc["name"])
    print("")

print("Done. Total chunks embedded:", total_chunks)
