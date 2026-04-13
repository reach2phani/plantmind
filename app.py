import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

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

    return jsonify({"success": True, "message": message, "document": saved})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
