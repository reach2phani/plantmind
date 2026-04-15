"""
reembed.py - re-embed all uploaded documents from Supabase Storage into Pinecone.
Run this after: adding new metadata columns, changing chunk size, or after bulk uploads.
Usage: python reembed.py
"""
import os
from dotenv import load_dotenv
from supabase import create_client
from embedder import embed_document

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def reembed_all():
    docs = supabase.table("documents").select("*").eq("status", "uploaded").execute()
    if not docs.data:
        print("No uploaded documents found in Supabase.")
        return

    print(f"Found {len(docs.data)} documents to embed.\n")
    total_chunks = 0

    for doc in docs.data:
        storage_path = doc.get("file_path", "")
        if not storage_path:
            print(f"  SKIP {doc.get('name')} - no file_path in DB")
            continue

        print(f"Processing: {doc.get('name')} (Rev {doc.get('revision', '?')})")
        chunks = embed_document(doc["id"], storage_path, doc)
        total_chunks += chunks
        print(f"  -> {chunks} chunks embedded\n")

    print(f"Done. Total chunks embedded: {total_chunks}")

if __name__ == "__main__":
    reembed_all()
