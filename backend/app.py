from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from pypdf import PdfReader
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "backend", "uploads")
INSTANCE_FOLDER = os.path.join(BASE_DIR, "backend", "instance")
AUTH_DATABASE = os.environ.get(
    "AUTH_DATABASE_PATH",
    os.path.join(INSTANCE_FOLDER, "users.sqlite3")
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(AUTH_DATABASE), exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

MAX_UPLOAD_SIZE_BYTES = 25 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE_BYTES + 64 * 1024


@contextmanager
def auth_connection():
    connection = sqlite3.connect(AUTH_DATABASE)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_auth_database():
    with auth_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


initialize_auth_database()


def auth_user(user_id):
    if not user_id:
        return None

    with auth_connection() as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()


@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().casefold()
    password = data.get("password", "")

    if not name or len(name) > 120:
        return jsonify({"error": "Enter your name (up to 120 characters)."}), 400

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"error": "Enter a valid email address."}), 400

    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        return jsonify({"error": "Password must be between 8 and 128 characters."}), 400

    try:
        with auth_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password))
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with this email already exists."}), 409

    session.clear()
    session["user_id"] = user_id
    return jsonify({"message": "Account created.", "user": {"name": name, "email": email}}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().casefold()
    password = data.get("password", "")

    with auth_connection() as connection:
        connection.row_factory = sqlite3.Row
        user = connection.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,)
        ).fetchone()

    if not user or not isinstance(password, str) or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Email or password is incorrect."}), 401

    session.clear()
    session["user_id"] = user["id"]
    return jsonify({"message": "Signed in.", "user": {"name": user["name"], "email": user["email"]}})


@app.route("/api/auth/session", methods=["GET"])
def auth_session():
    user = auth_user(session.get("user_id"))
    if not user:
        session.clear()
        return jsonify({"authenticated": False})

    return jsonify({
        "authenticated": True,
        "user": {"name": user["name"], "email": user["email"]}
    })


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Signed out."})


@app.route("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/upload", methods=["POST"])
def upload_resume():

    if "resume" not in request.files:
        return jsonify({"error": "Please select a PDF resume."}), 400

    file = request.files["resume"]

    if file.filename == "":
        return jsonify({"error": "Please select a PDF resume."}), 400

    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed."}), 400

    filename = secure_filename(file.filename)

    if not filename:
        return jsonify({"error": "Invalid filename."}), 400

    file_path = os.path.join(UPLOAD_FOLDER, filename)

    file.save(file_path)

    try:
        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n"

        text = text.strip()

        if not text:
            return jsonify({
                "error": "Could not read text from this PDF. Please use a text-based PDF."
            }), 400

        result = analyze_resume(text)

        result["filename"] = filename
        result["pages"] = len(reader.pages)
        result["words"] = len(text.split())

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Could not analyze the PDF.",
            "details": str(e)
        }), 500


def analyze_resume(text):

    lower_text = text.lower()

    skills_database = [
        "python",
        "java",
        "javascript",
        "typescript",
        "html",
        "css",
        "c++",
        "c",
        "php",
        "sql",
        "mysql",
        "postgresql",
        "react",
        "angular",
        "node.js",
        "node",
        "git",
        "github",
        "docker",
        "api",
        "tailwind",
        "wordpress",
        "flask",
        "fastapi",
        "aws",
        "azure",
        "machine learning",
        "artificial intelligence",
        "data analysis",
        "excel"
    ]

    detected_skills = []

    for skill in skills_database:
        if skill in lower_text:
            detected_skills.append(skill.upper())

    sections = {
        "Summary": [
            "summary",
            "profile",
            "objective",
            "about me"
        ],
        "Education": [
            "education",
            "academic",
            "qualification"
        ],
        "Experience": [
            "experience",
            "work experience",
            "employment",
            "internship"
        ],
        "Skills": [
            "skills",
            "technical skills",
            "technical skill"
        ],
        "Projects": [
            "projects",
            "project"
        ],
        "Certifications": [
            "certifications",
            "certification",
            "courses"
        ]
    }

    structure = {}

    for section, keywords in sections.items():

        found = any(
            keyword in lower_text
            for keyword in keywords
        )

        structure[section] = found

    strengths = []

    if len(detected_skills) >= 5:
        strengths.append("Strong technical skill coverage")

    if structure["Projects"]:
        strengths.append("Projects section detected")

    if structure["Education"]:
        strengths.append("Education section detected")

    if structure["Experience"]:
        strengths.append("Experience section detected")

    if "linkedin" in lower_text:
        strengths.append("LinkedIn profile detected")

    if re.search(r"\d+%", text):
        strengths.append("Good use of measurable results")

    action_words = [
        "developed",
        "created",
        "implemented",
        "designed",
        "managed",
        "built",
        "improved",
        "led"
    ]

    action_count = sum(
        lower_text.count(word)
        for word in action_words
    )

    if action_count >= 3:
        strengths.append("Strong use of action-oriented language")

    improvements = []

    phone_pattern = r"(\+91[\s-]?)?[6-9]\d{9}"

    if not re.search(phone_pattern, text):
        improvements.append("Add a valid phone number")

    if not structure["Summary"]:
        improvements.append("Add a professional summary")

    if not structure["Projects"]:
        improvements.append("Add a projects section")

    if not structure["Certifications"]:
        improvements.append("Add relevant certifications")

    if not improvements:
        improvements.append("Keep improving keyword relevance for each job")

    score = 40

    score += min(len(detected_skills) * 2, 25)

    for value in structure.values():
        if value:
            score += 4

    if "linkedin" in lower_text:
        score += 3

    if re.search(r"\d+%", text):
        score += 3

    if action_count >= 3:
        score += 4

    score -= min(len(improvements) * 3, 15)

    score = max(0, min(score, 100))

    if score >= 85:
        status = "Excellent"
    elif score >= 70:
        status = "Good Potential"
    elif score >= 50:
        status = "Needs Improvement"
    else:
        status = "Needs Major Improvement"

    ats_score = max(
        0,
        min(
            100,
            55
            + len(detected_skills) * 2
            + sum(structure.values()) * 4
        )
    )

    return {
        "score": score,
        "status": status,
        "skills": detected_skills,
        "strengths": strengths,
        "improvements": improvements,
        "structure": structure,
        "ats_score": ats_score
    }


if __name__ == "__main__":
    app.run(debug=True)