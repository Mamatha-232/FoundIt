import re
import sqlite3
from pathlib import Path
from uuid import uuid4
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "campus_lost_found.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.secret_key = "demo-secret-key"


def get_db_connection():
    """Create a SQLite connection that returns rows like dictionaries."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the items table when the app starts for the first time."""
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('lost', 'found')),
                location TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                image_filename TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """
        )

        # Add the image column for databases created before image support existed.
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(items)").fetchall()
        }
        if "image_filename" not in existing_columns:
            connection.execute("ALTER TABLE items ADD COLUMN image_filename TEXT")
        if "phone" not in existing_columns:
            connection.execute("ALTER TABLE items ADD COLUMN phone TEXT")
        if "created_by" not in existing_columns:
            connection.execute("ALTER TABLE items ADD COLUMN created_by TEXT")

        connection.commit()


def normalize_words(text):
    """Lowercase the text and split it into clean words for simple matching."""
    cleaned_text = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return set(word for word in cleaned_text.split() if word)


def build_item_text(item):
    """Combine the item name and description before comparing keywords."""
    return f"{item['name']} {item['description']}"


def serialize_item(row):
    """Convert a database row into a JSON-friendly dictionary."""
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "type": row["type"],
        "location": row["location"],
        "phone": (row["phone"] if "phone" in row.keys() else "") or "",
        "created_by": (row["created_by"] if "created_by" in row.keys() else "") or "",
        "status": row["status"],
        "image_url": f"/static/uploads/{row['image_filename']}" if row["image_filename"] else "",
    }


def is_valid_phone(phone):
    """Allow simple prototype phone numbers with 5 to 10 digits."""
    return phone.isdigit() and 5 <= len(phone) <= 10


def login_required(view_function):
    """Redirect users to login if they are not signed in."""
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return wrapped_view


def allowed_file(filename):
    """Check whether the uploaded file has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_image(uploaded_file):
    """Save an uploaded image with a unique filename and return that filename."""
    if not uploaded_file or not uploaded_file.filename:
        return ""

    if not allowed_file(uploaded_file.filename):
        raise ValueError("Please upload a valid image file: png, jpg, jpeg, gif, or webp.")

    safe_name = secure_filename(uploaded_file.filename)
    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix.lower()
    unique_name = f"{stem}_{uuid4().hex}{suffix}"
    file_path = UPLOAD_FOLDER / unique_name
    uploaded_file.save(file_path)
    return unique_name


def fetch_items(search_query=""):
    """Fetch all items, optionally filtered by a simple search query."""
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM items ORDER BY id DESC"
        ).fetchall()

    items = [serialize_item(row) for row in rows]

    if not search_query:
        return items

    # Split the search text into words so "black wallet" can match
    # items like "wallet leather black".
    search_words = normalize_words(search_query)
    filtered_items = []

    for item in items:
        combined_text = f"{item['name']} {item['description']} {item['location']}".lower()
        item_words = normalize_words(combined_text)

        # Show the item if at least one searched word is present.
        if search_words & item_words:
            filtered_items.append(item)

    return filtered_items


def find_matches(items):
    """
    Compare lost and found items using both name and description.
    If at least one word overlaps, treat it as a simple AI match.
    """
    lost_items = [item for item in items if item["type"] == "lost" and item["status"] != "recovered"]
    found_items = [item for item in items if item["type"] == "found" and item["status"] != "recovered"]
    matches = []

    for lost_item in lost_items:
        # Combine name + description so short names like "bracelet" can still match.
        lost_words = normalize_words(build_item_text(lost_item))
        for found_item in found_items:
            found_words = normalize_words(build_item_text(found_item))
            common_words = sorted(lost_words & found_words)

            if len(common_words) >= 1:
                matches.append(
                    {
                        "lost_item": lost_item,
                        "found_item": found_item,
                        "common_words": common_words,
                        "message": "Match Found",
                    }
                )

    return matches


@app.route("/")
@login_required
def index():
    """Serve the main frontend page."""
    return render_template("index.html", username=session.get("username", "User"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Create a new user account."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not username or not password:
            return render_template("register.html", error="Username and password are required.")

        try:
            with get_db_connection() as connection:
                connection.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, password),
                )
                connection.commit()
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username already exists.")

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Allow an existing user to log in."""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        with get_db_connection() as connection:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username, password),
            ).fetchone()

        if user is None:
            return render_template("login.html", error="Invalid username or password.")

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log out the current user by clearing the session."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/add_lost", methods=["POST"])
@login_required
def add_lost():
    """Save a lost item into the database."""
    return add_item("lost")


@app.route("/add_found", methods=["POST"])
@login_required
def add_found():
    """Save a found item into the database."""
    return add_item("found")


def add_item(item_type):
    """Shared helper for adding both lost and found items."""
    data = request.form if request.form else (request.get_json(silent=True) or {})
    name = (data.get("name") or "").strip()
    description = (data.get("description") or "").strip()
    location = (data.get("location") or "").strip()
    phone = (data.get("phone") or "").strip()
    created_by = session.get("username", "")
    image_file = request.files.get("image")

    if not name or not description or not location or not phone:
        return jsonify({"error": "Name, description, location, and phone are required."}), 400

    if not is_valid_phone(phone):
        return jsonify({"error": "Enter valid phone number (minimum 5 digits)"}), 400

    if item_type == "found" and (image_file is None or not image_file.filename):
        return jsonify({"error": "An image is required for found items."}), 400

    try:
        image_filename = save_uploaded_image(image_file)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO items (name, description, type, location, image_filename, phone, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, description, item_type, location, image_filename, phone, created_by),
        )
        connection.commit()

        new_item = connection.execute(
            "SELECT * FROM items WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return jsonify(
        {
            "message": f"{item_type.title()} item added successfully.",
            "item": serialize_item(new_item),
        }
    ), 201


@app.route("/items", methods=["GET"])
@login_required
def get_items():
    """Return lost and found items, with optional search support."""
    search_query = request.args.get("search", "").strip()
    items = fetch_items(search_query)

    return jsonify(
        {
            "lost_items": [item for item in items if item["type"] == "lost"],
            "found_items": [item for item in items if item["type"] == "found"],
        }
    )


@app.route("/match", methods=["GET"])
@login_required
def match_items():
    """Return all matched lost/found pairs based on keyword overlap."""
    items = fetch_items()
    matches = find_matches(items)
    return jsonify({"matches": matches})


@app.route("/mark_recovered/<int:item_id>", methods=["POST"])
@login_required
def mark_recovered(item_id):
    """Allow an admin-like action to mark an item as recovered."""
    with get_db_connection() as connection:
        connection.execute(
            "UPDATE items SET status = 'recovered' WHERE id = ?",
            (item_id,),
        )
        connection.commit()

        updated_item = connection.execute(
            "SELECT * FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()

    if updated_item is None:
        return jsonify({"error": "Item not found."}), 404

    return jsonify(
        {
            "message": "Item marked as recovered.",
            "item": serialize_item(updated_item),
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
else:
    init_db()
