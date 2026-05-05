from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "OK"

print("Starting Flask...")
app.run(port=5000)
print("Flask started")