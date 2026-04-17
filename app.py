import os
import re
import threading
import json
import tempfile
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from dotenv import load_dotenv
from supabase import create_client
from embedder import embed_document
from pinecone import Pinecone
from groq import Groq

load_dotenv()
app = Flask(__name__)

def get_embedding(text, input_type="query"):
    """Get embedding vector using Pinecone's hosted inference API."""
    result = pc.inference.embed(
        model="multilingual-e5-large",
        inputs=[text[:8000]],
        parameters={"input_type": input_type, "truncate": "END"}
    )
    return result[0].values

SUPABASE_BUCKET = "plantmind-docs"

supabase    = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
pc          = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pine_index  = pc.Index(os.getenv("PINECONE_INDEX"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ALLOWED = {"pdf", "docx", "txt", "csv", "mp4", "mov"}

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED

def parse_revision(rev_str):
    try:
        return float(rev_str.strip())
    except Exception:
        return 0.0

def time_in_range(event_time, time_from, time_to):
    try:
        fmt = "%H:%M"
        et  = datetime.strptime(event_time.strip()[:5], fmt).time()
        tf  = datetime.strptime(time_from.strip()[:5],  fmt).time()
        tt  = datetime.strptime(time_to.strip()[:5],    fmt).time()
        if tf <= tt:
            return tf <= et <= tt
        else:
            return et >= tf or et <= tt
    except Exception:
        return True

def get_match_metadata(m):
    """Safely extract metadata from Pinecone match object or dict."""
    if isinstance(m, dict):
        return m.get("metadata", {})
    return getattr(m, "metadata", {}) or {}

def get_match_score(m):
    if isinstance(m, dict):
        return m.get("score", 0)
    return getattr(m, "score", 0)

def match_to_dict(m):
    """Convert Pinecone match object to plain dict safely."""
    meta = get_match_metadata(m)
    if not isinstance(meta, dict):
        try:
            meta = dict(meta)
        except Exception:
            meta = {}
    return {
        "score":    get_match_score(m),
        "metadata": meta
    }

def filter_shift_chunks(matches, time_from, time_to):
    if not time_from or not time_to:
        return [match_to_dict(m) for m in matches]
    filtered = []
    for m in matches:
        md   = match_to_dict(m)
        text = md["metadata"].get("text", "")
        lines = text.split("\n")
        kept  = []
        for line in lines:
            t = re.search(r'\bat (\d{2}:\d{2})\b', line)
            if t:
                if time_in_range(t.group(1), time_from, time_to):
                    kept.append(line)
            else:
                kept.append(line)
        if kept:
            md["metadata"]["text"] = "\n".join(kept)
            filtered.append(md)
    return filtered if filtered else [match_to_dict(m) for m in matches]

# ── Pages ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    docs = supabase.table("documents").select("*").order("created_at", desc=True).execute()
    return render_template("index.html", documents=docs.data)

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/library")
def library():
    return render_template("library.html")

# ── API ────────────────────────────────────────────────────────────────

@app.route("/api/documents")
def api_documents():
    docs = supabase.table("documents").select("*").order("created_at", desc=True).execute()
    return jsonify({"documents": docs.data})

@app.route("/api/documents/<doc_id>", methods=["PATCH"])
def update_document(doc_id):
    data    = request.get_json()
    allowed_fields = {"plant_site", "line", "doc_type", "revision", "equip_tag"}
    updates = {k: v for k, v in data.items() if k in allowed_fields}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400
    result = supabase.table("documents").update(updates).eq("id", doc_id).execute()
    if not result.data:
        return jsonify({"error": "Document not found"}), 404
    saved = result.data[0]
    def run_reembed():
        base      = os.path.dirname(os.path.abspath(__file__))
        storage_path = saved.get("file_path", "")
        if storage_path:
            embed_document(saved["id"], storage_path, saved)
    threading.Thread(target=run_reembed, daemon=True).start()
    return jsonify({"success": True, "document": saved})

@app.route("/api/feedback", methods=["POST"])
def save_feedback():
    data   = request.get_json()
    record = {
        "question": data.get("question", ""),
        "answer":   data.get("answer",   ""),
        "rating":   data.get("rating",   0),
        "sources":  json.dumps(data.get("sources", [])),
    }
    supabase.table("feedback").insert(record).execute()
    return jsonify({"success": True})

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file selected"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not allowed(file.filename):
        return jsonify({"error": f"'{file.filename}' is not supported. Accepted: PDF, DOCX, TXT, CSV, MP4"}), 400

    filename   = file.filename
    file_type  = filename.rsplit(".", 1)[1].lower()
    new_rev    = request.form.get("revision",   "1.0").strip()
    plant_site = request.form.get("plant_site", "")
    line       = request.form.get("line",       "")
    doc_type   = request.form.get("doc_type",   "SOP")
    equip_tag  = request.form.get("equip_tag",  "")

    existing = supabase.table("documents").select("*") \
        .eq("name", filename).eq("status", "uploaded").execute()
    if existing.data:
        existing_doc = existing.data[0]
        existing_rev = existing_doc.get("revision", "1.0")
        if parse_revision(new_rev) <= parse_revision(existing_rev):
            return jsonify({"error": f"'{filename}' already exists at Rev {existing_rev}. Increase the revision number to upload a new version."}), 409
        supabase.table("documents").update({"status": "archived"}).eq("id", existing_doc["id"]).execute()

    safe_rev  = new_rev.replace(".", "_")
    save_name = f"rev{safe_rev}_{filename}"

    # Upload to Supabase Storage
    file_bytes   = file.read()
    storage_path = f"documents/{save_name}"
    supabase.storage.from_(SUPABASE_BUCKET).upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": "application/octet-stream", "upsert": "true"}
    )

    record = {
        "name": filename, "file_type": file_type, "plant_site": plant_site,
        "line": line, "doc_type": doc_type, "revision": new_rev,
        "file_path": storage_path, "status": "uploaded", "equip_tag": equip_tag,
    }
    result = supabase.table("documents").insert(record).execute()
    saved  = result.data[0]

    was_sup = existing.data and parse_revision(new_rev) > parse_revision(existing.data[0].get("revision","1.0"))
    message = (f"Rev {new_rev} uploaded. Previous Rev {existing.data[0]['revision']} archived."
               if was_sup else f"{filename} uploaded successfully.")

    def run_embed():
        embed_document(saved["id"], storage_path, saved)
    threading.Thread(target=run_embed, daemon=True).start()

    return jsonify({"success": True, "message": message, "document": saved})

@app.route("/ask", methods=["POST"])
def ask():
    data      = request.get_json()
    question  = data.get("question",   "").strip()
    plant     = data.get("plant_site", "")
    line      = data.get("line",       "")
    equip_tag = data.get("equip_tag",  "")
    mode      = data.get("mode",       "doc")
    time_from = data.get("time_from",  "")
    time_to   = data.get("time_to",    "")

    if not question:
        def err():
            yield "NOANSWER:Please enter a question."
        return Response(stream_with_context(err()), mimetype="text/plain")

    question_vec = get_embedding(question)

    # Build filter — shift mode only searches CSVs, doc mode excludes CSVs
    filter_dict = {}
    if mode == "shift":
        filter_dict["file_type"] = {"$eq": "csv"}
        if line:
            filter_dict["line"] = {"$eq": line}
    else:
        filter_dict["file_type"] = {"$nin": ["csv"]}
        if plant:     filter_dict["plant_site"] = {"$eq": plant}
        if line:      filter_dict["line"]       = {"$eq": line}
        if equip_tag: filter_dict["equip_tag"]  = {"$eq": equip_tag}

    results  = pine_index.query(
        vector=question_vec, top_k=8, include_metadata=True,
        filter=filter_dict
    )
    matches      = results.get("matches", [])
    was_fallback = False

    # Fallback — remove non-filetype filters and retry
    if (not matches or matches[0]["score"] < 0.35) and len(filter_dict) > 1:
        fallback_filter = {"file_type": filter_dict["file_type"]}
        results  = pine_index.query(vector=question_vec, top_k=8, include_metadata=True, filter=fallback_filter)
        matches  = results.get("matches", [])
        was_fallback = True

    if not matches or matches[0]["score"] < 0.35:
        def no_ans():
            if mode == "shift":
                yield "NOANSWER:No shift log events found for this time range. Check that a shift log has been uploaded for this period."
            else:
                yield "NOANSWER:I could not find a confident answer in the uploaded documents. Try rephrasing your question or check that the relevant document has been uploaded."
        return Response(stream_with_context(no_ans()), mimetype="text/plain")

    # For shift mode — filter chunks by time range
    if mode == "shift" and time_from and time_to:
        matches = filter_shift_chunks(matches, time_from, time_to)

    context_parts = []
    sources       = []
    seen          = set()
    matches       = [match_to_dict(m) for m in matches]
    for m in matches:
        meta = m.get("metadata", {})
        text = meta.get("text", "")
        name = meta.get("name", "")
        rev  = meta.get("revision", "")
        key  = name + rev
        if key not in seen:
            seen.add(key)
            sources.append({
                "name":      name,
                "revision":  rev,
                "doc_type":  meta.get("doc_type",  ""),
                "equip_tag": meta.get("equip_tag", ""),
                "score":     round(m["score"], 2)
            })
        context_parts.append(f"[From {name}]:\n{text}")

    context = "\n\n".join(context_parts)

    if mode == "shift":
        time_ctx = f" between {time_from} and {time_to}" if time_from and time_to else ""
        line_ctx = f" on {line}" if line else ""
        system_prompt = (
            "You are PlantMind, a shift intelligence assistant for manufacturing plant operators. "
            "Answer questions using ONLY the provided shift log context. "
            "Format your answer as a clear bulleted list of events with timestamps where available. "
            "Group events by category: Alarms, Maintenance, Quality, Process. "
            "Be concise and factual. Never fabricate events not in the context."
        )
        user_prompt = (
            f"Shift log context{line_ctx}{time_ctx}:\n\n{context}\n\n"
            f"Question: {question}\n\n"
            "Summarise the relevant shift events as a structured list with timestamps. "
            "Group by category if multiple types of events exist."
        )
    else:
        system_prompt = (
            "You are PlantMind, an AI assistant for manufacturing plant operators. "
            "Answer questions using ONLY the provided document context. "
            "Be specific and practical. Never fabricate information not in the context."
        )
        user_prompt = (
            f"Context:\n\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer clearly and specifically based only on the context above."
        )

    sources_json = json.dumps(sources)

    def full_stream():
        if was_fallback:
            yield "FALLBACK:"
        yield f"SOURCES:{sources_json}\n\n"
        stream = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            stream=True, max_tokens=800, temperature=0.1
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    return Response(stream_with_context(full_stream()), mimetype="text/plain",
                    headers={"X-Accel-Buffering": "no"})

@app.route("/embed-all", methods=["POST"])
def embed_all():
    docs  = supabase.table("documents").select("*").eq("status", "uploaded").execute()
    total = 0
    for doc in docs.data:
        storage_path = doc.get("file_path", "")
        if storage_path:
            total += embed_document(doc["id"], storage_path, doc)
    return jsonify({"success": True, "message": f"Embedded {total} chunks from {len(docs.data)} documents"})

@app.route("/investigate", methods=["POST"])
def investigate():
    from agent_v2 import investigate_incident
    data     = request.get_json()
    incident = data.get("incident", "").strip()
    plant    = data.get("plant_site", "")
    line     = data.get("line",       "")

    if not incident:
        return jsonify({"error": "Please describe the incident"}), 400

    if plant or line:
        context  = f"[Plant: {plant}, Line: {line}] "
        incident = context + incident

    def stream():
        for chunk in investigate_incident(incident):
            yield chunk

    return Response(stream_with_context(stream()), mimetype="text/plain",
                    headers={"X-Accel-Buffering": "no"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
