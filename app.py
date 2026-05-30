import os
import re
import threading
import json
import tempfile
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()  # load env vars FIRST before any module that needs them
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from supabase import create_client
from embedder import embed_document
from pinecone import Pinecone
from groq import Groq
from multi_agent import investigate_incident
from llm_logger import log_streaming_call, get_today_stats

app = Flask(__name__)

# ── Knowledge graph — load on startup ────────────────────────────────────────
def _load_knowledge_graph():
    """Load graph data into Neo4j on app startup. Silent fail if unavailable."""
    try:
        from knowledge_graph import load_graph, get_graph_stats
        import os

        # Try multiple paths — works locally and on Render
        base_dir   = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, "wm101_graph.json"),
            os.path.join(base_dir, "data", "wm101_graph.json"),
            "wm101_graph.json",
        ]
        graph_file = next((p for p in candidates if os.path.exists(p)), None)

        print(f"[app] Graph file search: {candidates}")

        if not graph_file:
            print("[app] wm101_graph.json not found in any expected location")
            print(f"[app] Current dir: {os.getcwd()}")
            print(f"[app] Dir contents: {os.listdir(base_dir)[:20]}")
            return

        print(f"[app] Found graph file: {graph_file}")
        stats = get_graph_stats(equip_tag="WM-101")
        if stats.get("nodes", 0) == 0:
            print("[app] Knowledge graph empty — loading...")
            success = load_graph(graph_file)
            if success:
                stats = get_graph_stats(equip_tag="WM-101")
                print(f"[app] Graph loaded — {stats.get('nodes',0)} nodes, {stats.get('edges',0)} edges")
        else:
            print(f"[app] Graph already loaded — {stats['nodes']} nodes, {stats['edges']} edges")
    except Exception as e:
        import traceback
        print(f"[app] Knowledge graph error: {e}")
        print(traceback.format_exc())

# Load graph in background thread so startup is not blocked
import threading
threading.Thread(target=_load_knowledge_graph, daemon=True).start()

# ── Equipment ID auto-detection ──────────────────────────────────────
# Extracts equipment tags from natural language operator input.
# Pattern: letter prefix + hyphen + numbers (e.g. WR-401, P-201, CV-401)
# Also handles common variants: WR401, wr-401 → normalised to WR-401
#
# Teaching concept: entity extraction as retrieval pre-filter.
# A simple regex dramatically improves precision — operators shouldn't
# need to manually set context before every question.

import re as _re

_EQUIP_PATTERN = _re.compile(
    r'\b([A-Za-z]{1,4})-?(\d{2,4})\b'
)

def extract_equipment_id(text):
    """
    Extract and normalise equipment tag from operator input.
    Returns uppercase hyphenated tag e.g. "WR-401" or None.

    Examples:
        "P-201 is making noise"       → "P-201"
        "check wr401 alarm"           → "WR-401"
        "WR-401 just tripped"         → "WR-401"
        "what happened on line 4"     → None
    """
    match = _EQUIP_PATTERN.search(text)
    if match:
        prefix = match.group(1).upper()
        number = match.group(2)
        return f"{prefix}-{number}"
    return None


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
    # G-09 fix: return empty if no events in window — do not silently return all events
    return filtered

# ── Pages ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from flask import redirect
    return redirect("/chat")

@app.route("/chat")
def chat():
    return render_template("chat.html")

@app.route("/library")
def library():
    return render_template("library.html")

# ── API ────────────────────────────────────────────────────────────────

@app.route("/gaps")
def gaps():
    return render_template("gaps.html")

@app.route("/api/gaps")
def api_gaps():
    """
    Knowledge gap analysis — which equipment has coverage gaps.
    Groups documents by equip_tag and shows which doc_types are missing.

    Teaching note: this is a pure Supabase aggregation — no LLM needed.
    The query answers "what can PlantMind actually investigate?" before
    an operator wastes time asking a question with no data behind it.
    """
    docs = supabase.table("documents")        .select("equip_tag,doc_type,plant_site,line,name,embed_status")        .eq("status", "uploaded")        .execute()

    # Derive required types dynamically from what exists in the index.
    # Any doc_type uploaded for at least 2 different equipment tags is
    # considered a "standard" type expected across all equipment.
    # This means adding a new category automatically updates gap analysis
    # without any code change.
    all_type_counts = {}
    for doc in (docs.data or []):
        tag   = (doc.get("equip_tag") or "").strip()
        dtype = doc.get("doc_type", "")
        if tag and dtype:
            if dtype not in all_type_counts:
                all_type_counts[dtype] = set()
            all_type_counts[dtype].add(tag)

    # A type is "required" if it appears for 2+ equipment tags
    # (avoids one-off uploads creating phantom requirements)
    required_types = sorted([
        dt for dt, tags in all_type_counts.items()
        if len(tags) >= 2
    ])

    # Always include core types even if only 1 equipment has them
    core_types = ["SOP", "Work Instruction", "Shift Log", "NCR"]
    for ct in core_types:
        if ct not in required_types:
            required_types.append(ct)

    # Group by equip_tag
    coverage = {}
    for doc in (docs.data or []):
        tag   = (doc.get("equip_tag") or "").strip()
        dtype = doc.get("doc_type", "Other")
        if not tag:
            continue
        if tag not in coverage:
            coverage[tag] = {
                "equip_tag":   tag,
                "plant_site":  doc.get("plant_site", ""),
                "line":        doc.get("line", ""),
                "doc_types":   [],
                "docs":        [],
                "missing":     []
            }
        if dtype not in coverage[tag]["doc_types"]:
            coverage[tag]["doc_types"].append(dtype)
        coverage[tag]["docs"].append(doc.get("name", ""))

    # Calculate missing doc types per equipment
    for tag, info in coverage.items():
        info["missing"] = [t for t in required_types if t not in info["doc_types"]]
        info["coverage_pct"] = round(
            (len([t for t in required_types if t in info["doc_types"]]) / len(required_types)) * 100
        )
        info["status"] = (
            "full"    if info["coverage_pct"] == 100 else
            "partial" if info["coverage_pct"] >= 50  else
            "minimal"
        )

    # Also find equipment mentioned in investigations with no documents
    equipment_list = list(coverage.values())
    equipment_list.sort(key=lambda x: x["coverage_pct"])

    return jsonify({
        "equipment":       equipment_list,
        "total_equipment": len(equipment_list),
        "full_coverage":   sum(1 for e in equipment_list if e["status"] == "full"),
        "partial":         sum(1 for e in equipment_list if e["status"] == "partial"),
        "minimal":         sum(1 for e in equipment_list if e["status"] == "minimal"),
        "required_types":  required_types
    })

@app.route("/api/plant-sites", methods=["GET"])
def get_plant_sites():
    result = supabase.table("plant_sites").select("*").order("name").execute()
    return jsonify({"plant_sites": result.data})

@app.route("/api/plant-sites", methods=["POST"])
def add_plant_site():
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    existing = supabase.table("plant_sites").select("id").eq("name", name).execute()
    if existing.data:
        return jsonify({"error": f"'{name}' already exists"}), 409
    result = supabase.table("plant_sites").insert({"name": name}).execute()
    return jsonify({"success": True, "plant_site": result.data[0]})


@app.route("/plant-setup")
def plant_setup():
    return render_template("plant_setup.html")

# ── Lines API ──────────────────────────────────────────────────────────────────

@app.route("/api/lines", methods=["GET"])
def get_lines():
    plant_site = request.args.get("plant_site", "")
    q = supabase.table("lines").select("*").order("name")
    if plant_site:
        q = q.eq("plant_site", plant_site)
    result = q.execute()
    return jsonify({"lines": result.data})

@app.route("/api/lines", methods=["POST"])
def add_line():
    data = request.get_json()
    name       = (data.get("name") or "").strip()
    plant_site = (data.get("plant_site") or "").strip()
    if not name or not plant_site:
        return jsonify({"error": "Name and plant_site are required"}), 400
    existing = supabase.table("lines").select("id").eq("name", name).eq("plant_site", plant_site).execute()
    if existing.data:
        return jsonify({"error": f"'{name}' already exists for this site"}), 409
    result = supabase.table("lines").insert({"name": name, "plant_site": plant_site, "active": True}).execute()
    return jsonify({"success": True, "line": result.data[0]})

@app.route("/api/lines/<line_id>", methods=["PATCH"])
def update_line(line_id):
    data = request.get_json()
    allowed = {"name", "plant_site", "active"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields"}), 400
    result = supabase.table("lines").update(updates).eq("id", line_id).execute()
    return jsonify({"success": True, "line": result.data[0]})

# ── Equipment API ──────────────────────────────────────────────────────────────

@app.route("/api/equipment", methods=["GET"])
def get_equipment():
    plant_site = request.args.get("plant_site", "")
    line       = request.args.get("line", "")
    q = supabase.table("equipment").select("*").order("equip_tag")
    if plant_site:
        q = q.eq("plant_site", plant_site)
    if line:
        q = q.eq("line", line)
    result = q.execute()
    return jsonify({"equipment": result.data})

@app.route("/api/equipment", methods=["POST"])
def add_equipment():
    data = request.get_json()
    equip_tag    = (data.get("equip_tag") or "").strip().upper().replace(" ", "-")
    name         = (data.get("name") or "").strip()
    plant_site   = (data.get("plant_site") or "").strip()
    line         = (data.get("line") or "").strip()
    eq_type      = (data.get("type") or "").strip()
    manufacturer = (data.get("manufacturer") or "").strip()
    if not equip_tag or not name or not plant_site or not line:
        return jsonify({"error": "equip_tag, name, plant_site and line are required"}), 400
    existing = supabase.table("equipment").select("id").eq("equip_tag", equip_tag).execute()
    if existing.data:
        return jsonify({"error": f"'{equip_tag}' already exists"}), 409
    result = supabase.table("equipment").insert({
        "equip_tag": equip_tag, "name": name, "plant_site": plant_site,
        "line": line, "type": eq_type, "manufacturer": manufacturer, "active": True
    }).execute()
    return jsonify({"success": True, "equipment": result.data[0]})

@app.route("/api/equipment/<equip_id>", methods=["PATCH"])
def update_equipment(equip_id):
    data = request.get_json()
    allowed = {"name", "type", "plant_site", "line", "manufacturer", "active"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields"}), 400
    result = supabase.table("equipment").update(updates).eq("id", equip_id).execute()
    return jsonify({"success": True, "equipment": result.data[0]})


@app.route("/api/plant-sites/<site_id>", methods=["PATCH"])
def update_plant_site(site_id):
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    result = supabase.table("plant_sites").update({"name": name}).eq("id", site_id).execute()
    return jsonify({"success": True, "plant_site": result.data[0]})

@app.route("/api/plant-sites/<site_id>", methods=["DELETE"])
def delete_plant_site(site_id):
    try:
        supabase.table("plant_sites").delete().eq("id", site_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/lines/<line_id>", methods=["DELETE"])
def delete_line(line_id):
    try:
        supabase.table("lines").delete().eq("id", line_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/equipment/<equip_id>", methods=["DELETE"])
def delete_equipment(equip_id):
    try:
        supabase.table("equipment").delete().eq("id", equip_id).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        doc_id       = saved["id"]
        storage_path = saved.get("file_path", "")
        if not storage_path:
            return
        try:
            supabase.table("documents").update({
                "embed_status": "pending"
            }).eq("id", doc_id).execute()
            embed_document(doc_id, storage_path, saved)
            supabase.table("documents").update({
                "embed_status": "done",
                "last_embedded_at": datetime.utcnow().isoformat()
            }).eq("id", doc_id).execute()
        except Exception as e:
            supabase.table("documents").update({
                "embed_status": "failed"
            }).eq("id", doc_id).execute()
            print(f"  Re-embed failed for {doc_id}: {e}")
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
        doc_id = saved["id"]
        try:
            supabase.table("documents").update({
                "embed_status": "pending"
            }).eq("id", doc_id).execute()
            embed_document(doc_id, storage_path, saved)
            supabase.table("documents").update({
                "embed_status": "done",
                "last_embedded_at": datetime.utcnow().isoformat()
            }).eq("id", doc_id).execute()
        except Exception as e:
            supabase.table("documents").update({
                "embed_status": "failed"
            }).eq("id", doc_id).execute()
            print(f"  Embed failed for {doc_id}: {e}")
    threading.Thread(target=run_embed, daemon=True).start()

    return jsonify({"success": True, "message": message, "document": saved})

@app.route("/ask", methods=["POST"])
def ask():
    data      = request.get_json()
    question  = data.get("question",   "").strip()
    plant     = data.get("plant_site", "")
    line      = data.get("line",       "")
    equip_tag = data.get("equip_tag", "")

    # Auto-detect equipment ID from question if not explicitly set
    # Teaching note: operators often mention equipment in natural language
    # e.g. "P-201 is making noise" — extract and use as Pinecone filter
    if not equip_tag:
        detected = extract_equipment_id(question)
        if detected:
            equip_tag = detected
    mode      = data.get("mode",       "doc")
    time_from = data.get("time_from",  "")
    time_to   = data.get("time_to",    "")

    if not question:
        def err():
            yield "NOANSWER:Please enter a question."
        return Response(stream_with_context(err()), mimetype="text/plain")

    try:
        question_vec = get_embedding(question)
    except Exception as e:
        def err_stream():
            yield "NOANSWER:Search service temporarily unavailable. Please try again in a few seconds."
        return Response(stream_with_context(err_stream()), mimetype="text/plain",
                        headers={"X-Accel-Buffering": "no"})

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
        vector=question_vec, top_k=12, include_metadata=True,
        filter=filter_dict
    )
    matches      = results.get("matches", [])
    was_fallback = False

    # Fallback — only relax plant/line filters, NEVER drop equip_tag
    low_confidence   = not matches or matches[0]["score"] < 0.35
    has_equip_filter = bool(filter_dict.get("equip_tag"))

    if low_confidence and not has_equip_filter and len(filter_dict) > 1:
        fallback_filter = {"file_type": filter_dict["file_type"]}
        results  = pine_index.query(vector=question_vec, top_k=12, include_metadata=True, filter=fallback_filter)
        matches  = results.get("matches", [])
        was_fallback = True

    # Lower threshold when equip filter active — spec chunks score lower than procedure chunks
    score_threshold = 0.30 if has_equip_filter else 0.35
    if not matches or matches[0]["score"] < score_threshold:
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
        import time as _t
        if was_fallback:
            yield "FALLBACK:"
        yield f"SOURCES:{sources_json}\n\n"
        _start = _t.time()
        _output = []
        try:
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
                    _output.append(delta.content)
                    yield delta.content
            log_streaming_call(
                call_type  = data.get("mode", "qa"),
                model      = "llama-3.1-8b-instant",
                input_text = system_prompt + user_prompt,
                output_text= "".join(_output),
                latency_ms = int((_t.time() - _start) * 1000),
                plant_site = data.get("plant_site", ""),
                equip_tag  = data.get("equip_tag", "")
            )
        except Exception as e:
            log_streaming_call(
                call_type="qa", model="llama-3.1-8b-instant",
                input_text=system_prompt, output_text="",
                latency_ms=int((_t.time()-_start)*1000), error=e
            )
            yield f"Error: {e}"

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

@app.route("/api/history", methods=["POST"])
def save_history():
    data = request.get_json()
    record = {
        "mode":       data.get("mode",       "doc"),
        "question":   data.get("question",   ""),
        "answer":     data.get("answer",     ""),
        "sources":    json.dumps(data.get("sources", [])),
        "plant_site": data.get("plant_site", ""),
        "line":       data.get("line",       ""),
        "equip_tag":  data.get("equip_tag",  ""),
    }
    result = supabase.table("chat_history").insert(record).execute()
    return jsonify({"success": True, "id": result.data[0]["id"] if result.data else None})

@app.route("/api/recent-equipment")
def recent_equipment():
    """
    Returns the 4 most recently investigated equipment tags
    for the current plant site, from chat_history.

    Falls back to all equipment tags from documents table
    if no investigation history exists yet.
    """
    plant = request.args.get("plant_site", "")
    line  = request.args.get("line", "")

    # Try chat_history first — most recently used equipment
    try:
        query = supabase.table("chat_history")            .select("equip_tag, created_at")            .eq("mode", "agent")            .neq("equip_tag", "")            .order("created_at", desc=True)            .limit(50)            .execute()

        seen = []
        recent = []
        for row in (query.data or []):
            tag = (row.get("equip_tag") or "").strip()
            if tag and tag not in seen:
                seen.append(tag)
                recent.append({"equip_tag": tag, "source": "history"})
            if len(recent) >= 4:
                break

        if recent:
            return jsonify({"equipment": recent, "source": "history"})
    except Exception as e:
        print(f"  recent-equipment history query failed: {e}")

    # Fallback — equipment from documents table filtered by context
    docs_query = supabase.table("documents")        .select("equip_tag, line, plant_site")        .eq("status", "uploaded")        .neq("equip_tag", "")

    if plant:
        docs_query = docs_query.eq("plant_site", plant)
    if line:
        docs_query = docs_query.eq("line", line)

    docs = docs_query.execute()
    seen = []
    fallback = []
    for doc in (docs.data or []):
        tag = (doc.get("equip_tag") or "").strip()
        if tag and tag not in seen:
            seen.append(tag)
            fallback.append({
                "equip_tag": tag,
                "line":      doc.get("line", ""),
                "source":    "documents"
            })
        if len(fallback) >= 4:
            break

    return jsonify({"equipment": fallback, "source": "documents"})

@app.route("/api/history", methods=["GET"])
def get_history():
    limit = request.args.get("limit", 30)
    result = supabase.table("chat_history")         .select("id, mode, question, answer, sources, plant_site, line, created_at")         .order("created_at", desc=True)         .limit(limit)         .execute()
    return jsonify({"history": result.data})

@app.route("/investigate", methods=["POST"])
def investigate():
    data     = request.get_json()
    incident = data.get("incident", "").strip()
    plant    = data.get("plant_site", "")
    line     = data.get("line", "")

    if not incident:
        return jsonify({"error": "Please describe the incident"}), 400

    # Auto-detect equipment if not passed from UI
    equip = data.get("equip_tag", "") or extract_equipment_id(incident)

    if plant or line:
        context  = f"[Plant: {plant}, Line: {line}] "
        incident = context + incident

    def stream():
        try:
            for chunk in investigate_incident(incident, equipment_id=equip):
                yield chunk
        except Exception as e:
            err = str(e)
            if "rate_limit" in err.lower() or "429" in err:
                yield "\n\nRate limit reached — Groq TPM limit hit. Please wait 60 seconds and try again."
            else:
                yield f"\n\nInvestigation error: {err}"

    return Response(stream_with_context(stream()), mimetype="text/plain",
                    headers={"X-Accel-Buffering": "no"})

@app.route("/api/llm-stats", methods=["GET"])
def llm_stats():
    """
    Returns today's LLM usage stats.
    Call this anytime to see token consumption before hitting limits.
    Example: GET http://localhost:5000/api/llm-stats
    """
    return jsonify(get_today_stats())

# ─────────────────────────────────────────────────────────────────────────────
# ALERTS ROUTES — Session 11
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/alerts")
def alerts_page():
    return render_template("alerts.html")

@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    try:
        result = supabase.table("chat_history")            .select("*")            .eq("mode", "proactive")            .eq("read", False)            .order("created_at", desc=True)            .limit(20)            .execute()
        return jsonify({"alerts": result.data or []})
    except Exception as e:
        return jsonify({"alerts": [], "error": str(e)})

@app.route("/api/alerts/count", methods=["GET"])
def get_alerts_count():
    try:
        result = supabase.table("chat_history")            .select("id", count="exact")            .eq("mode", "proactive")            .eq("read", False)            .execute()
        return jsonify({"count": result.count or 0})
    except Exception as e:
        return jsonify({"count": 0})

@app.route("/api/alerts/<alert_id>/dismiss", methods=["POST"])
def dismiss_alert(alert_id):
    try:
        supabase.table("chat_history")            .update({"read": True})            .eq("id", alert_id)            .execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/live-events", methods=["GET"])
def get_live_events():
    try:
        equip = request.args.get("equip_tag", "")
        limit = int(request.args.get("limit", 20))
        q = supabase.table("live_events")            .select("*")            .order("created_at", desc=True)            .limit(limit)
        if equip:
            q = q.eq("equip_tag", equip)
        result = q.execute()
        return jsonify({"events": result.data or []})
    except Exception as e:
        return jsonify({"events": []})


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GRAPH ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/graph")
def graph_page():
    """Serves the graph explorer page."""
    return render_template("graph.html")


@app.route("/api/graph/fault-chain", methods=["GET"])
def graph_fault_chain():
    """
    Returns fault chain for an equipment and optional fault type.
    Used by chat.html to render the fault chain below investigation report.
    Used by multi_agent.py to enrich orchestrator context.

    Query params:
      ?equip=WM-101
      ?fault=wire_feed_overload (optional)
    """
    equip = request.args.get("equip", "").strip()
    fault = request.args.get("fault", "").strip()

    if not equip:
        return jsonify({"error": "equip parameter required"}), 400

    try:
        from knowledge_graph import get_fault_chain
        chain = get_fault_chain(equip, fault or None)
        return jsonify(chain)
    except Exception as e:
        print(f"  [graph] fault-chain error: {e}")
        return jsonify({"has_data": False, "chain_nodes": [], "chain_edges": [],
                        "chain_text": "", "warnings": [], "downtime": ""})


@app.route("/api/graph/nodes", methods=["GET"])
def graph_nodes():
    """
    Returns all nodes and edges for the graph explorer.
    Used by graph.html to render the vis.js interactive diagram.

    Query params:
      ?equip=WM-101       (optional — filter by equipment)
      ?plant=greenfield   (optional — filter by plant)
      ?type=Fault         (optional — filter by node type)
    """
    equip      = request.args.get("equip", "").strip() or None
    plant_site = request.args.get("plant", "").strip() or None
    node_type  = request.args.get("type", "").strip()  or None

    try:
        from knowledge_graph import get_full_graph
        graph = get_full_graph(
            equip_tag  = equip,
            plant_site = plant_site,
            node_type  = node_type
        )
        return jsonify(graph)
    except Exception as e:
        print(f"  [graph] nodes error: {e}")
        return jsonify({"nodes": [], "edges": [], "count": {"nodes": 0, "edges": 0}})


@app.route("/api/graph/debug", methods=["GET"])
def graph_debug():
    """Debug endpoint to check graph status on Render."""
    import os
    results = {}
    # Check JSON file
    graph_file = os.path.join(os.path.dirname(__file__), "wm101_graph.json")
    results["json_path"]   = graph_file
    results["json_exists"] = os.path.exists(graph_file)
    # Check Neo4j env vars
    results["neo4j_uri"]      = bool(os.getenv("NEO4J_URI"))
    results["neo4j_username"] = bool(os.getenv("NEO4J_USERNAME"))
    results["neo4j_password"] = bool(os.getenv("NEO4J_PASSWORD"))
    # Check graph stats
    try:
        from knowledge_graph import get_graph_stats, get_graphed_equipment
        stats = get_graph_stats(equip_tag="WM-101")
        results["graph_stats"] = stats
        results["graphed_equipment"] = get_graphed_equipment()
    except Exception as e:
        results["graph_error"] = str(e)
    return jsonify(results)


@app.route("/api/graph/equipment", methods=["GET"])
def graph_equipment():
    """
    Returns list of equipment that have graph data.
    Used by graph.html to populate the equipment dropdown.
    """
    try:
        from knowledge_graph import get_graphed_equipment
        equipment = get_graphed_equipment()
        return jsonify({"equipment": equipment})
    except Exception as e:
        print(f"  [graph] equipment error: {e}")
        return jsonify({"equipment": []})


if __name__ == "__main__":
    app.run(debug=True, port=5000)