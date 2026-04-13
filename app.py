from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

@app.route("/")
def home():
    groq    = os.getenv("GROQ_API_KEY")
    supa_u  = os.getenv("SUPABASE_URL")
    supa_k  = os.getenv("SUPABASE_KEY")
    pine_k  = os.getenv("PINECONE_API_KEY")
    pine_i  = os.getenv("PINECONE_INDEX")

    def row(label, val):
        status = "YES" if val else "MISSING"
        color  = "green" if val else "red"
        return f"<tr><td>{label}</td><td style='color:{color}'><b>{status}</b></td></tr>"

    table  = row("Groq API key",     groq)
    table += row("Supabase URL",     supa_u)
    table += row("Supabase key",     supa_k)
    table += row("Pinecone API key", pine_k)
    table += row("Pinecone index",   pine_i)

    all_ok = all([groq, supa_u, supa_k, pine_k, pine_i])

    if all_ok:
        msg = "<p style='color:green'><b>All systems ready - lets build PM-001!</b></p>"
    else:
        msg = "<p style='color:red'><b>Some keys missing - check your .env file</b></p>"

    html  = "<html><body>"
    html += "<h2>PlantMind setup check</h2>"
    html += "<table>" + table + "</table>"
    html += msg
    html += "</body></html>"
    return html

if __name__ == "__main__":
    app.run(debug=True, port=5000)
