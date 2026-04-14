import os
import threading
import json
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from dotenv import load_dotenv
from supabase import create_client
from embedder import embed_document
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer
from groq import Groq

load_dotenv()
app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

pc          = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pine_index  = pc.Index(os.getenv("PINECONE_INDEX"))
embedder    = SentenceTransformer("all-MiniLM-L6-v2")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ALLOWED = {"pdf", "docx", "txt", "csv", "mp4", "mov"}

def allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED

def parse_revision(rev_str):
    try:
        return float(rev_str.strip())
    except Exception:
        return 0.0

@app.route("/")
def index():
    docs = supabase.table("documents").select("*").order("created_at", desc=True).execute()
    return render_template("index.html", documents=docs.data)

@app.route("/chat")
def chat():
    return render_template("chat.html")

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
    new_rev    = request.form.get("revision", "1.0").strip()
    plant_site = request.form.get("plant_site", "")
    line       = request.form.get("line", "")
    doc_type   = request.form.get("doc_type", "SOP")

    existing = supabase.table("documents") \
        .select("*").eq("name", filename).eq("status", "uploaded").execute()

    if existing.data:
        existing_doc = existing.data[0]
        existing_rev = existing_doc.get("revision", "1.0")
        if parse_revision(new_rev) <= parse_revision(existing_rev):
            return jsonify({
                "error": f"'{filename}' already exists at Rev {existing_rev}. Increase the revision number to upload a new version."
            }), 409
        supabase.table("documents").update({"status": "archived"}).eq("id", existing_doc["id"]).execute()

    safe_rev  = new_rev.replace(".", "_")
    save_name = f"rev{safe_rev}_{filename}"
    save_path = os.path.join(UPLOAD_FOLDER, save_name)
    file.save(save_path)

    record = {
        "name":       filename,
        "file_type":  file_type,
        "plant_site": plant_site,
        "line":       line,
        "doc_type":   doc_type,
        "revision":   new_rev,
        "file_path":  save_path,
        "status":     "uploaded"
    }

    result = supabase.table("documents").insert(record).execute()
    saved  = result.data[0]

    was_superseded = existing.data and parse_revision(new_rev) > parse_revision(existing.data[0].get("revision", "1.0"))
    message = (
        f"Rev {new_rev} uploaded. Previous Rev {existing.data[0]['revision']} archived."
        if was_superseded else
        f"{filename} uploaded successfully."
    )

    def run_embed():
        embed_document(saved["id"], save_path, saved)
    threading.Thread(target=run_embed, daemon=True).start()

    return jsonify({"success": True, "message": message, "document": saved})

@app.route("/ask", methods=["POST"])
def ask():
    data     = request.get_json()
    question = data.get("question", "").strip()
    plant    = data.get("plant_site", "")
    line     = data.get("line", "")

    if not question:
        def err():
            yield "NOANSWER:Please enter a question."
        return Response(stream_with_context(err()), mimetype="text/plain")

    question_vec = embedder.encode(question).tolist()

    filter_dict = {}
    if plant:
        filter_dict["plant_site"] = {"$eq": plant}
    if line:
        filter_dict["line"] = {"$eq": line}

    results = pine_index.query(
        vector=question_vec,
        top_k=5,
        include_metadata=True,
        filter=filter_dict if filter_dict else None
    )

    matches = results.get("matches", [])

    if not matches or matches[0]["score"] < 0.35:
        def no_ans():
            yield "NOANSWER:I could not find a confident answer in the uploaded documents. Try rephrasing your question or check that the relevant document has been uploaded."
        return Response(stream_with_context(no_ans()), mimetype="text/plain")

    context_parts = []
    sources       = []
    seen          = set()

    for m in matches:
        meta = m.get("metadata", {})
        text = meta.get("text", "")
        name = meta.get("name", "")
        rev  = meta.get("revision", "")
        key  = name + rev
        if key not in seen:
            seen.add(key)
            sources.append({
                "name":     name,
                "revision": rev,
                "doc_type": meta.get("doc_type", ""),
                "score":    round(m["score"], 2)
            })
        context_parts.append(f"[From {name} Rev {rev}]:\n{text}")

    context = "\n\n".join(context_parts)

    system_prompt = (
        "You are PlantMind, an AI assistant for manufacturing plant operators. "
        "Answer questions using ONLY the provided document context. "
        "Be specific and practical — operators need clear actionable answers. "
        "If the context does not contain enough information to answer confidently, say so clearly. "
        "Never fabricate information not present in the context."
    )

    user_prompt = (
        f"Context from plant documents:\n\n{context}\n\n"
        f"Operator question: {question}\n\n"
        "Provide a clear, specific answer based only on the context above."
    )

    sources_json = json.dumps(sources)

    def full_stream():
        yield f"SOURCES:{sources_json}\n\n"
        stream = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            stream=True,
            max_tokens=600,
            temperature=0.1
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    return Response(
        stream_with_context(full_stream()),
        mimetype="text/plain",
        headers={"X-Accel-Buffering": "no"}
    )

@app.route("/embed-all", methods=["POST"])
def embed_all():
    docs = supabase.table("documents").select("*").eq("status", "uploaded").execute()
    base = os.path.dirname(os.path.abspath(__file__))
    total = 0
    for doc in docs.data:
        raw_path  = doc.get("file_path", "")
        full_path = os.path.join(base, raw_path)
        if os.path.exists(full_path):
            chunks = embed_document(doc["id"], full_path, doc)
            total += chunks
    return jsonify({"success": True, "message": f"Embedded {total} chunks from {len(docs.data)} documents"})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
