from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os
import json
from datetime import datetime
from openai import OpenAI

app = Flask(__name__)
DB_NAME = "database.db"
OPENAI_MODEL = "gpt-5.6-luna"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            reason TEXT,
            expected_outcome TEXT NOT NULL,
            confidence REAL NOT NULL,
            expected_time REAL NOT NULL,
            actual_outcome TEXT,
            actual_time REAL,
            success INTEGER,
            status TEXT DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            ai_insight TEXT
        )
    """)
    # Add the AI column if an older database already exists.
    columns = [row[1] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()]
    if "ai_insight" not in columns:
        conn.execute("ALTER TABLE decisions ADD COLUMN ai_insight TEXT")

    conn.commit()
    conn.close()


def get_ai_insight(decision):
    """Generate a personalized insight with the OpenAI Responses API.
    Falls back to a local insight if no API key is configured or the API fails.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return generate_local_insight(decision)

    try:
        client = OpenAI(api_key=api_key)
        prompt = f"""
You are the personal decision coach inside a student hackathon project called Decision Diary.
Analyze this completed decision and give a short, friendly, practical insight.

Decision: {decision['title']}
Category: {decision['category']}
Reason: {decision['reason'] or 'Not provided'}
Expected outcome: {decision['expected_outcome']}
Confidence: {decision['confidence']}%
Expected time: {decision['expected_time']} days
Actual outcome: {decision['actual_outcome']}
Actual time: {decision['actual_time']} days
Successful: {'Yes' if decision['success'] == 1 else 'No'}

Include exactly three short parts:
1. What happened compared with the prediction.
2. What the confidence/result suggests about the user's decision pattern.
3. One practical suggestion for the next similar decision.
Keep it under 120 words. Do not make medical, legal, or financial claims.
"""
        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions="You are a concise and supportive decision coach.",
            input=prompt
        )
        return response.output_text.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return generate_local_insight(decision)


def generate_local_insight(decision):
    expected = float(decision["expected_time"])
    actual = float(decision["actual_time"]) if decision["actual_time"] is not None else expected
    error = ((actual - expected) / expected) * 100 if expected > 0 else 0

    if error > 15:
        timing = f"You underestimated the time by about {error:.1f}%."
    elif error < -15:
        timing = f"You finished about {abs(error):.1f}% faster than expected."
    else:
        timing = "Your time estimate was fairly close to the actual result."

    result = "The decision worked out." if decision["success"] == 1 else "The decision did not work out as expected."
    return f"{timing} {result} With {decision['confidence']:.0f}% confidence, review this result when making a similar decision next time."


def generate_insight(decisions):
    completed = [d for d in decisions if d["status"] == "Completed"]
    if not completed:
        return "Complete a few decisions and record their actual outcomes to unlock personalized insights."

    # If the latest completed decision has an AI insight, show it.
    latest = completed[-1]
    if latest["ai_insight"]:
        return latest["ai_insight"]

    return generate_local_insight(latest)


@app.route("/")
def index():
    conn = get_db()
    decisions = conn.execute(
        "SELECT * FROM decisions ORDER BY id DESC"
    ).fetchall()
    conn.close()

    completed = [d for d in decisions if d["status"] == "Completed"]
    success_count = sum(int(d["success"] or 0) for d in completed)

    accuracy = round((success_count / len(completed)) * 100, 1) if completed else 0

    avg_error = 0
    if completed:
        errors = []
        for d in completed:
            if d["expected_time"] and d["expected_time"] > 0:
                errors.append(
                    ((d["actual_time"] - d["expected_time"]) / d["expected_time"]) * 100
                )
        if errors:
            avg_error = round(sum(errors) / len(errors), 1)

    insight = generate_insight(decisions)

    return render_template(
        "index.html",
        decisions=decisions,
        total=len(decisions),
        completed=len(completed),
        accuracy=accuracy,
        avg_error=avg_error,
        insight=insight
    )


@app.route("/add", methods=["GET", "POST"])
def add_decision():
    if request.method == "POST":
        title = request.form["title"]
        category = request.form["category"]
        reason = request.form.get("reason", "")
        expected_outcome = request.form["expected_outcome"]
        confidence = float(request.form["confidence"])
        expected_time = float(request.form["expected_time"])

        conn = get_db()
        conn.execute("""
            INSERT INTO decisions
            (title, category, reason, expected_outcome, confidence,
             expected_time, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?)
        """, (
            title, category, reason, expected_outcome,
            confidence, expected_time,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        conn.close()

        return redirect(url_for("index"))

    return render_template("add_decision.html")


@app.route("/decision/<int:decision_id>")
def decision(decision_id):
    conn = get_db()
    item = conn.execute(
        "SELECT * FROM decisions WHERE id = ?", (decision_id,)
    ).fetchone()
    conn.close()

    if item is None:
        return "Decision not found", 404

    difference = None
    error_percent = None

    if item["status"] == "Completed":
        difference = round(item["actual_time"] - item["expected_time"], 2)
        if item["expected_time"] > 0:
            error_percent = round(
                ((item["actual_time"] - item["expected_time"]) /
                 item["expected_time"]) * 100, 1
            )

    return render_template(
        "decision.html",
        decision=item,
        difference=difference,
        error_percent=error_percent
    )


@app.route("/outcome/<int:decision_id>", methods=["GET", "POST"])
def outcome(decision_id):
    conn = get_db()
    item = conn.execute(
        "SELECT * FROM decisions WHERE id = ?", (decision_id,)
    ).fetchone()

    if item is None:
        conn.close()
        return "Decision not found", 404

    if request.method == "POST":
        actual_outcome = request.form["actual_outcome"]
        actual_time = float(request.form["actual_time"])
        success = 1 if request.form["success"] == "yes" else 0

        conn.execute("""
            UPDATE decisions
            SET actual_outcome = ?, actual_time = ?, success = ?,
                status = 'Completed', completed_at = ?
            WHERE id = ?
        """, (
            actual_outcome,
            actual_time,
            success,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            decision_id
        ))
        conn.commit()

        updated = conn.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision_id,)
        ).fetchone()

        ai_insight = get_ai_insight(updated)
        conn.execute(
            "UPDATE decisions SET ai_insight = ? WHERE id = ?",
            (ai_insight, decision_id)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("decision", decision_id=decision_id))

    conn.close()
    return render_template("outcome.html", decision=item)


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    decisions = conn.execute(
        "SELECT * FROM decisions ORDER BY id ASC"
    ).fetchall()
    conn.close()

    completed = [d for d in decisions if d["status"] == "Completed"]

    success_count = sum(int(d["success"] or 0) for d in completed)
    accuracy = round((success_count / len(completed)) * 100, 1) if completed else 0

    errors = []
    for d in completed:
        if d["expected_time"] > 0:
            errors.append(
                ((d["actual_time"] - d["expected_time"]) /
                 d["expected_time"]) * 100
            )

    avg_error = round(sum(errors) / len(errors), 1) if errors else 0

    categories = {}
    for d in completed:
        categories.setdefault(d["category"], {"total": 0, "success": 0})
        categories[d["category"]]["total"] += 1
        categories[d["category"]]["success"] += int(d["success"] or 0)

    category_labels = list(categories.keys())
    category_accuracy = [
        round((v["success"] / v["total"]) * 100, 1)
        for v in categories.values()
    ]

    return render_template(
        "dashboard.html",
        total=len(decisions),
        completed=len(completed),
        accuracy=accuracy,
        avg_error=avg_error,
        category_labels=json.dumps(category_labels),
        category_accuracy=json.dumps(category_accuracy),
        decisions=decisions,
        insight=generate_insight(decisions)
    )


@app.route("/api/decisions")
def api_decisions():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM decisions ORDER BY id DESC"
    ).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
