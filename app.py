from flask import Flask, request, jsonify, render_template
import sqlite3
import os

app = Flask(__name__)
DB = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "finance.db"))
# On Render, DB_PATH=/data/finance.db so data persists across deploys


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                type           TEXT    NOT NULL CHECK(type IN ('income', 'outcome')),
                amount         REAL    NOT NULL CHECK(amount > 0),
                category       TEXT,
                description    TEXT,
                payment_method TEXT,
                date           DATE    NOT NULL,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add payment_method column if upgrading an existing DB
        try:
            conn.execute("ALTER TABLE transactions ADD COLUMN payment_method TEXT")
        except Exception:
            pass


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions ORDER BY date DESC, created_at DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    data = request.get_json()
    required = ("type", "amount", "date")
    if not all(data.get(k) for k in required):
        return jsonify({"error": "type, amount and date are required"}), 400
    if data["type"] not in ("income", "outcome"):
        return jsonify({"error": "type must be income or outcome"}), 400
    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "amount must be a positive number"}), 400

    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO transactions (type, amount, category, description, payment_method, date) VALUES (?,?,?,?,?,?)",
            (data["type"], amount, data.get("category", ""), data.get("description", ""), data.get("payment_method", ""), data["date"])
        )
        row_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (row_id,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/api/transactions/<int:tid>", methods=["DELETE"])
def delete_transaction(tid):
    with get_db() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (tid,))
    return jsonify({"deleted": tid})


@app.route("/api/monthly", methods=["GET"])
def monthly_summary():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT
                strftime('%Y', date)  AS year,
                strftime('%m', date)  AS month,
                SUM(CASE WHEN type = 'income'  THEN amount ELSE 0 END) AS total_income,
                SUM(CASE WHEN type = 'outcome' THEN amount ELSE 0 END) AS total_outcome,
                COUNT(*) AS nb_transactions
            FROM transactions
            GROUP BY year, month
            ORDER BY year DESC, month DESC
        """).fetchall()
    return jsonify([dict(r) for r in rows])


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5050)
