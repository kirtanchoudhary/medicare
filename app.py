from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import re
import json
import os
from openai import OpenAI

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "users.db")


def get_openrouter_client():
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is missing")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key
    )


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
    return send_from_directory(BASE_DIR, "dashboard.html")


@app.route("/dashboard")
def dashboard():
    return send_from_directory(BASE_DIR, "dashboard.html")


@app.route("/index.html")
def login_page():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/symptom")
def symptom():
    return send_from_directory(BASE_DIR, "symptom-checker.html")


@app.route("/doctor")
def doctor():
    return send_from_directory(BASE_DIR, "virtual-doctor.html")


@app.route("/appointments")
def appointments():
    return send_from_directory(BASE_DIR, "appointment.html")


@app.route("/emergency")
def emergency():
    return send_from_directory(BASE_DIR, "emergency.html")


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/debug-env")
def debug_env():
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    return jsonify({
        "openrouter_key_present": bool(key)
    })


@app.route("/debug-openrouter")
def debug_openrouter():
    try:
        _client = get_openrouter_client()
        return jsonify({"status": "ok", "message": "OpenRouter key found"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/signup", methods=["POST"])
def signup():
    try:
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

    except Exception as e:
        print("SIGNUP ERROR:", repr(e))
        return jsonify({"msg": f"Server error: {str(e)}"}), 500


@app.route("/login", methods=["POST"])
def login():
    try:
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

    except Exception as e:
        print("LOGIN ERROR:", repr(e))
        return jsonify({"msg": f"Server error: {str(e)}"}), 500


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        client = get_openrouter_client()

        data = request.json or {}
        symptoms = str(data.get("symptoms", "")).strip()
        age = str(data.get("age", "")).strip()
        gender = str(data.get("gender", "")).strip()

        if not symptoms:
            return jsonify({"error": "Symptoms are required"}), 400

        prompt = f"""
Patient details:
Age: {age}
Gender: {gender}
Symptoms: {symptoms}

You are a medical assistant for general educational guidance only.
Do not claim certainty, do not provide a final diagnosis.
Give response in VALID JSON only with these exact keys:
possible_conditions
general_medicines
tips
when_to_see_doctor

Rules:
- possible_conditions: array of objects with keys "name" and "details"
- general_medicines: array of short strings
- tips: array of short strings
- when_to_see_doctor: array of short strings
"""

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        reply = response.choices[0].message.content.strip()

        try:
            parsed = json.loads(reply)
            return jsonify(parsed)
        except Exception:
            return jsonify({
                "possible_conditions": [
                    {
                        "name": "General response",
                        "details": reply
                    }
                ],
                "general_medicines": [],
                "tips": [],
                "when_to_see_doctor": []
            })

    except Exception as e:
        print("ANALYZE ERROR:", repr(e))
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/doctor-chat", methods=["POST"])
def doctor_chat():
    try:
        client = get_openrouter_client()

        data = request.json or {}
        history = data.get("history", [])

        if not isinstance(history, list):
            return jsonify({"reply": "Invalid chat history"}), 400

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful virtual doctor assistant for general educational guidance only. "
                    "Do not claim certainty and do not provide a final diagnosis."
                )
            }
        ] + history

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages
        )

        reply = response.choices[0].message.content.strip()
        return jsonify({"reply": reply})

    except Exception as e:
        print("DOCTOR CHAT ERROR:", repr(e))
        return jsonify({"reply": f"Server error: {str(e)}"}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
