import os
import csv
import io
import tempfile
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from supabase import create_client

load_dotenv()

model    = SentenceTransformer("all-MiniLM-L6-v2")
pc       = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index    = pc.Index(os.getenv("PINECONE_INDEX"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

SUPABASE_BUCKET = "plantmind-docs"

def download_to_tempfile(storage_path):
    """Download file from Supabase Storage to a temp file. Returns temp file path."""
    try:
        file_bytes = supabase.storage.from_(SUPABASE_BUCKET).download(storage_path)
        ext = storage_path.rsplit(".", 1)[-1].lower()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}")
        tmp.write(file_bytes)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"  Download error for {storage_path}: {e}")
        return None

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    separators=["\n\n", "\n", ". ", " "]
)

def chunk_csv(file_path):
    """
    Convert CSV rows into rich text chunks.
    Groups rows into batches of 5 so related events stay together.
    Each chunk includes all field values as readable sentences.
    """
    chunks = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        reader  = csv.DictReader(io.StringIO(content))
        headers = reader.fieldnames or []
        rows    = list(reader)

        if not rows:
            return chunks

        # Build a natural language summary of the whole log as first chunk
        # so questions like "what happened last shift" hit something useful
        dates  = list(set([r.get("shift_date","") for r in rows if r.get("shift_date")]))
        shifts = list(set([r.get("shift","")      for r in rows if r.get("shift")]))
        lines  = list(set([r.get("line","")       for r in rows if r.get("line")]))
        cats   = list(set([r.get("category","")   for r in rows if r.get("category")]))

        summary = (
            f"Shift log summary. "
            f"Date: {', '.join(dates)}. "
            f"Shift: {', '.join(shifts)}. "
            f"Lines covered: {', '.join(lines)}. "
            f"Event categories: {', '.join(cats)}. "
            f"Total events: {len(rows)}. "
            f"Events include: " +
            "; ".join([r.get("description","")[:80] for r in rows[:5]]) + "."
        )
        chunks.append({
            "text":       summary,
            "chunk_type": "summary",
            "shift_date": ", ".join(dates),
            "shift":      ", ".join(shifts),
            "line":       ", ".join(lines),
        })

        # Group rows into batches of 5 — keeps related events together
        batch_size = 5
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            lines_text = []
            for row in batch:
                # Build a natural language sentence for each row
                parts = []
                if row.get("shift_date"): parts.append(row["shift_date"])
                if row.get("shift"):      parts.append(row["shift"] + " shift")
                if row.get("line"):       parts.append(row["line"])
                if row.get("time"):       parts.append("at " + row["time"])
                if row.get("category"):   parts.append("[" + row["category"] + "]")
                if row.get("equipment"):  parts.append("Equipment: " + row["equipment"])
                if row.get("description"):parts.append(row["description"])
                if row.get("action_taken"):parts.append("Action: " + row["action_taken"])
                if row.get("operator"):   parts.append("Operator: " + row["operator"])
                if row.get("status"):     parts.append("Status: " + row["status"])
                lines_text.append(" — ".join(parts))

            chunk_text = "\n".join(lines_text)

            # Extract metadata from first row of batch
            first = batch[0]
            chunks.append({
                "text":       chunk_text,
                "chunk_type": "events",
                "shift_date": first.get("shift_date", ""),
                "shift":      first.get("shift",      ""),
                "line":       first.get("line",       ""),
            })

    except Exception as e:
        print(f"  CSV parse error: {e}")

    return chunks


def embed_document(doc_id, storage_path, metadata):
    print(f"Embedding: {storage_path}")
    ext = storage_path.rsplit(".", 1)[-1].lower()

    # Download from Supabase Storage to a local temp file
    file_path = download_to_tempfile(storage_path)
    if not file_path:
        print(f"  Could not download {storage_path}")
        return 0

    try:
        result = _embed_local(doc_id, file_path, ext, metadata)
    finally:
        try:
            os.unlink(file_path)
        except Exception:
            pass
    return result

def _embed_local(doc_id, file_path, ext, metadata):
    if ext == "pdf":
        try:
            loader    = PyPDFLoader(file_path)
            pages     = loader.load()
            full_text = "\n\n".join([p.page_content for p in pages])
            print(f"  Extracted {len(full_text)} characters from PDF")
            if len(full_text.strip()) < 100:
                print("  WARNING: Very little text extracted — PDF may be image-based")
            texts = splitter.split_text(full_text)
        except Exception as e:
            print(f"  PDF load error: {e}")
            return 0

        if not texts:
            print("  No text extracted")
            return 0

        print(f"  Split into {len(texts)} chunks")

        vectors = []
        for i, text in enumerate(texts):
            if not text.strip():
                continue
            embedding = model.encode(text).tolist()
            vectors.append({
                "id":     f"{doc_id}_chunk_{i}",
                "values": embedding,
                "metadata": {
                    "doc_id":     str(doc_id),
                    "text":       text[:2000],
                    "chunk":      i,
                    "chunk_type": "pdf",
                    "name":       metadata.get("name",       ""),
                    "doc_type":   metadata.get("doc_type",   ""),
                    "plant_site": metadata.get("plant_site", ""),
                    "line":       metadata.get("line",       ""),
                    "revision":   metadata.get("revision",   "1.0"),
                    "file_type":  metadata.get("file_type",  ""),
                    "equip_tag":  metadata.get("equip_tag",  ""),
                }
            })
            if len(vectors) >= 50:
                index.upsert(vectors=vectors)
                vectors = []
        if vectors:
            index.upsert(vectors=vectors)

        print(f"  Done — {len(texts)} chunks for {metadata.get('name')}")
        return len(texts)

    elif ext == "csv":
        csv_chunks = chunk_csv(file_path)
        if not csv_chunks:
            print("  No content extracted from CSV")
            return 0

        print(f"  Built {len(csv_chunks)} structured chunks from CSV")
        vectors = []
        for i, chunk in enumerate(csv_chunks):
            text = chunk.get("text", "")
            if not text.strip():
                continue
            embedding = model.encode(text).tolist()
            vectors.append({
                "id":     f"{doc_id}_chunk_{i}",
                "values": embedding,
                "metadata": {
                    "doc_id":     str(doc_id),
                    "text":       text[:2000],
                    "chunk":      i,
                    "chunk_type": chunk.get("chunk_type", "events"),
                    "shift_date": chunk.get("shift_date", ""),
                    "shift":      chunk.get("shift",      ""),
                    "name":       metadata.get("name",       ""),
                    "doc_type":   metadata.get("doc_type",   ""),
                    "plant_site": metadata.get("plant_site", ""),
                    "line":       metadata.get("line",       ""),
                    "revision":   metadata.get("revision",   "1.0"),
                    "file_type":  "csv",
                    "equip_tag":  metadata.get("equip_tag",  ""),
                }
            })
            if len(vectors) >= 50:
                index.upsert(vectors=vectors)
                vectors = []
        if vectors:
            index.upsert(vectors=vectors)

        print(f"  Done — {len(csv_chunks)} chunks for {metadata.get('name')}")
        return len(csv_chunks)

    elif ext == "txt":
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            texts = splitter.split_text(content)
        except Exception as e:
            print(f"  File read error: {e}")
            return 0

        vectors = []
        for i, text in enumerate(texts):
            if not text.strip():
                continue
            embedding = model.encode(text).tolist()
            vectors.append({
                "id":     f"{doc_id}_chunk_{i}",
                "values": embedding,
                "metadata": {
                    "doc_id":     str(doc_id),
                    "text":       text[:2000],
                    "chunk":      i,
                    "chunk_type": "txt",
                    "name":       metadata.get("name",       ""),
                    "doc_type":   metadata.get("doc_type",   ""),
                    "plant_site": metadata.get("plant_site", ""),
                    "line":       metadata.get("line",       ""),
                    "revision":   metadata.get("revision",   "1.0"),
                    "file_type":  "txt",
                    "equip_tag":  metadata.get("equip_tag",  ""),
                }
            })
            if len(vectors) >= 50:
                index.upsert(vectors=vectors)
                vectors = []
        if vectors:
            index.upsert(vectors=vectors)

        print(f"  Done — {len(texts)} chunks for {metadata.get('name')}")
        return len(texts)

    else:
        print(f"  Skipping unsupported type: {ext}")
        return 0
# end _embed_local
