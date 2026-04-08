from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import re
import json
import os
from openai import OpenAI

app = Flask(__name__)

# ✅ ENV VARIABLE SE API KEY LE RAHE HAIN
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")  # <-- IMPORTANT CHANGE
)

DB = "users.db"


def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


def is_valid_gmail(email: str) -> bool:
    email = str(email or "").strip()
    return bool(re.fullmatch(r"[a-z0-9._%+-]+@gmail\.com", email))


@app.route("/")
def home():
    return send_from_directory(".", "dashboard.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(".", "dashboard.html")


@app.route("/index.html")
def login_page():
    return send_from_directory(".", "index.html")


@app.route("/symptom")
def symptom():
    return send_from_directory(".", "symptom-checker.html")


@app.route("/doctor")
def doctor():
    return send_from_directory(".", "virtual-doctor.html")


@app.route("/appointments")
def appointments():
    return send_from_directory(".", "appointment.html")


@app.route("/emergency")
def emergency():
    return send_from_directory(".", "emergency.html")


@app.route("/signup", methods=["POST"])
def signup():
    data = request.json or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()

    if not name or not email or not password:
        return jsonify({"msg": "Please fill all fields"}), 400

    if email != email.lower() or not is_valid_gmail(email):
        return jsonify({"msg": "Please enter a valid gmail in small letters only"}), 400

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE email=?", (email,))
    if c.fetchone():
        conn.close()
        return jsonify({"msg": "User exists"}), 400

    c.execute(
        "INSERT INTO users(name,email,password) VALUES(?,?,?)",
        (name, email, password)
    )

    conn.commit()
    conn.close()

    return jsonify({"msg": "ok", "name": name})


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}

    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()

    if not email or not password:
        return jsonify({"msg": "Please fill all fields"}), 400

    if email != email.lower() or not is_valid_gmail(email):
        return jsonify({"msg": "Login allowed only with lowercase @gmail.com email"}), 400

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute(
        "SELECT name FROM users WHERE email=? AND password=?",
        (email, password)
    )

    user = c.fetchone()
    conn.close()

    if user:
        return jsonify({"msg": "ok", "name": user[0]})

    return jsonify({"msg": "invalid email or password"}), 401


@app.route("/doctor-chat", methods=["POST"])
def doctor_chat():
    try:
        data = request.json or {}
        history = data.get("history", [])

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=history
        )

        reply = response.choices[0].message.content
        return jsonify({"reply": reply})

    except Exception as e:
        return jsonify({"reply": "Server error"}), 500


# ✅ IMPORTANT FOR RENDER DEPLOY
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)