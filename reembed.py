"""
reembed.py - re-embed uploaded documents from Supabase Storage into Pinecone.
Run this after: adding new metadata columns, changing how documents are cut, or after bulk uploads.

Usage:
    python reembed.py                                  every uploaded document
    python reembed.py --equip FL-101,WM-101 --ext txt  only these machines' text files
                                                       (e.g. after the section cutter, 6 Oct 2026)
    python reembed.py --equip FL-101 --dry-run         list what would be re-embedded, change nothing
"""
import argparse
import os
from dotenv import load_dotenv
from supabase import create_client
from embedder import embed_document

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))


def reembed_all(equip=None, ext=None, dry_run=False):
    docs = supabase.table("documents").select("*").eq("status", "uploaded").execute()
    if not docs.data:
        print("No uploaded documents found in Supabase.")
        return

    selected = [d for d in docs.data
                if (not equip or d.get("equip_tag") in equip)
                and (not ext or (d.get("file_path") or "").lower().rsplit(".", 1)[-1] in ext)]
    print(f"Found {len(docs.data)} uploaded documents; {len(selected)} selected"
          + (f" (machines: {', '.join(sorted(equip))})" if equip else "")
          + (f" (types: {', '.join(sorted(ext))})" if ext else "") + ".\n")
    total_chunks = 0

    for doc in selected:
        storage_path = doc.get("file_path", "")
        if not storage_path:
            print(f"  SKIP {doc.get('name')} - no file_path in DB")
            continue
        if dry_run:
            print(f"  would re-embed: {doc.get('equip_tag')}  {doc.get('name')}")
            continue

        print(f"Processing: {doc.get('name')} (Rev {doc.get('revision', '?')})")
        chunks = embed_document(doc["id"], storage_path, doc)
        total_chunks += chunks
        print(f"  -> {chunks} chunks embedded\n")

    if not dry_run:
        print(f"Done. Total chunks embedded: {total_chunks}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--equip", default="", help="comma-separated machine tags, e.g. FL-101,WM-101")
    ap.add_argument("--ext", default="", help="comma-separated file types, e.g. txt or pdf,csv")
    ap.add_argument("--dry-run", action="store_true", help="only list the documents")
    args = ap.parse_args()
    reembed_all(equip={e.strip() for e in args.equip.split(",") if e.strip()} or None,
                ext={e.strip().lower().lstrip(".") for e in args.ext.split(",") if e.strip()} or None,
                dry_run=args.dry_run)
