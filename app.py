from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3, threading, time, os
from datetime import datetime, timedelta, timezone
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB = "game.db"
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
RETENTION_HOURS = 36

def get_db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = get_db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS inputs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        number INTEGER NOT NULL CHECK(number >= 0 AND number <= 99),
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS game_results (
        id INTEGER PRIMARY KEY CHECK(id = 1),
        winning_number INTEGER NOT NULL CHECK(winning_number >= 0 AND winning_number <= 99),
        updated_at TEXT NOT NULL
    );
    """)
    c.commit(); c.close()

def cleanup_old_inputs():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)
    c = get_db()
    c.execute("DELETE FROM inputs WHERE created_at < ?", (cutoff.isoformat(),))
    c.commit(); c.close()

def cleanup_loop():
    while True:
        try: cleanup_old_inputs()
        except Exception as e: print("Cleanup:", e)
        time.sleep(300)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*a, **kw)
    return wrapper

@app.route("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("user_login"))
    return render_template("index.html", username=session.get("username"))

@app.route("/login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not 2 <= len(username) <= 30:
            return render_template("user_login.html", error="Name must be 2–30 characters.")
        c = get_db()
        row = c.execute("SELECT id, username FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            now = datetime.now(timezone.utc).isoformat()
            cur = c.execute("INSERT INTO users(username, created_at) VALUES (?,?)", (username, now))
            c.commit()
            user_id = cur.lastrowid
        else:
            user_id = row["id"]
        c.close()
        session["user_id"] = user_id
        session["username"] = username
        return redirect(url_for("home"))
    return render_template("user_login.html")

@app.post("/logout")
def user_logout():
    session.pop("user_id", None); session.pop("username", None)
    return redirect(url_for("user_login"))

@app.post("/api/submit")
def submit_number():
    if not session.get("user_id"):
        return jsonify({"ok": False, "error": "Please login first."}), 401
    data = request.get_json(silent=True) or {}
    try: number = int(data.get("number"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Enter a whole number from 0 to 99."}), 400
    if not 0 <= number <= 99:
        return jsonify({"ok": False, "error": "Number must be between 0 and 99."}), 400
    cleanup_old_inputs()
    c = get_db()
    c.execute("INSERT INTO inputs(user_id, number, created_at) VALUES (?,?,?)",
              (session["user_id"], number, datetime.now(timezone.utc).isoformat()))
    c.commit(); c.close()
    return jsonify({"ok": True, "message": f"Number {number} submitted!"})

@app.route("/result")
def result():
    c = get_db()
    r = c.execute("SELECT winning_number, updated_at FROM game_results WHERE id=1").fetchone()
    c.close()
    return render_template("result.html", result=r)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template("admin_login.html", error="Invalid admin credentials.")
    return render_template("admin_login.html")

@app.post("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

@app.route("/admin")
@admin_required
def admin():
    cleanup_old_inputs()
    c = get_db()
    inputs = c.execute("""
        SELECT inputs.id, inputs.number, inputs.created_at, users.username
        FROM inputs LEFT JOIN users ON users.id=inputs.user_id
        ORDER BY inputs.id DESC
    """).fetchall()
    counts = c.execute("SELECT number, COUNT(*) AS count FROM inputs GROUP BY number").fetchall()
    cmap = {x["number"]: x["count"] for x in counts}
    number_counts = [{"number": n, "count": cmap.get(n, 0)} for n in range(100)]
    r = c.execute("SELECT winning_number, updated_at FROM game_results WHERE id=1").fetchone()
    total = sum(x["count"] for x in number_counts)
    c.close()
    return render_template("admin.html", inputs=inputs, number_counts=number_counts, result=r, total=total)

@app.post("/admin/refresh")
@admin_required
def refresh():
    cleanup_old_inputs()
    return redirect(url_for("admin"))

@app.post("/admin/result")
@admin_required
def set_result():
    try: n = int(request.form.get("winning_number"))
    except (TypeError, ValueError): return redirect(url_for("admin"))
    if not 0 <= n <= 99: return redirect(url_for("admin"))
    c = get_db()
    now = datetime.now(timezone.utc).isoformat()
    c.execute("""INSERT INTO game_results(id,winning_number,updated_at) VALUES(1,?,?)
                 ON CONFLICT(id) DO UPDATE SET winning_number=excluded.winning_number,
                 updated_at=excluded.updated_at""", (n, now))
    c.commit(); c.close()
    return redirect(url_for("admin"))

@app.post("/admin/reset-inputs")
@admin_required
def reset_inputs():
    c = get_db()
    c.execute("DELETE FROM inputs")
    c.commit(); c.close()
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    threading.Thread(target=cleanup_loop, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=True)
