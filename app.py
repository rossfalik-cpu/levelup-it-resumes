#!/usr/bin/env python3
"""Level Up IT Resumes - Flask Web Application"""
import os, sys, hashlib, stripe
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config
import os
from models import get_db, init_db, seed_database, create_admin

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
if Config.STRIPE_SECRET_KEY:
    stripe.api_key = Config.STRIPE_SECRET_KEY

def login_required(f):
    @wraps(f)
    def decorated(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "info")
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return decorated

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*a, **kw):
        if not session.get("is_admin"):
            flash("Admin access required.", "error")
            return redirect(url_for("dashboard"))
        return f(*a, **kw)
    return decorated

@app.route("/")
def index():
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
    db.close()
    return render_template("index.html", resume_count=count, packs=Config.CREDIT_PACKS)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")
        db = get_db()
        try:
            pw_hash = hashlib.sha256(password.encode()).hexdigest()
            db.execute("INSERT INTO users (username, password_hash, email, credits) VALUES (?, ?, ?, 0)",
                       (username, pw_hash, email))
            db.commit()
            user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            db.execute("UPDATE users SET credits = credits + 5 WHERE id = ?", (user["id"],))
            db.commit()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["credits"] = user["credits"] + 5
            session["is_admin"] = bool(user["is_admin"])
            db.close()
            flash("Account created! You received 5 free credits.", "success")
            return redirect(url_for("dashboard"))
        except Exception as e:
            if "UNIQUE" in str(e):
                flash("Username or email already taken.", "error")
            else:
                flash("Registration failed.", "error")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        db.close()
        if user and hashlib.sha256(password.encode()).hexdigest() == user["password_hash"]:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["credits"] = user["credits"]
            session["is_admin"] = bool(user["is_admin"])
            flash("Welcome back!", "success")
            return redirect(request.args.get("next", url_for("dashboard")))
        flash("Invalid username or password.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    db = get_db()
    recent = db.execute(
        "SELECT r.name, r.title, r.company, rp.credits_spent FROM resume_purchases rp "
        "JOIN resumes r ON r.id = rp.resume_id WHERE rp.user_id = ? ORDER BY rp.purchased_at DESC LIMIT 20",
        (uid,)).fetchall()
    views_count = db.execute("SELECT COUNT(*) FROM resume_purchases WHERE user_id = ?", (uid,)).fetchone()[0]
    total_credits = db.execute(
        "SELECT COALESCE(SUM(credits), 0) FROM credit_orders WHERE user_id = ? AND status = 'completed'",
        (uid,)).fetchone()[0]
    total_spent = db.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM credit_orders WHERE user_id = ? AND status = 'completed'",
        (uid,)).fetchone()[0] / 100
    db.close()
    return render_template("dashboard.html", username=session["username"],
                           credits=session["credits"], resumes_viewed=views_count,
                           total_credits_bought=total_credits, total_spent="{:.2f}".format(total_spent),
                           recent_purchases=recent, is_admin=session.get("is_admin", False))

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    field = request.args.get("field", "all")
    page = int(request.args.get("page", 1))
    pp = 30
    db = get_db()
    if query:
        like = "%" + query + "%"
        if field == "name":
            total = db.execute("SELECT COUNT(*) FROM resumes WHERE name LIKE ?", (like,)).fetchone()[0]
            results = db.execute("SELECT * FROM resumes WHERE name LIKE ? ORDER BY name LIMIT ? OFFSET ?",
                                 (like, pp, (page-1)*pp)).fetchall()
        elif field == "title":
            total = db.execute("SELECT COUNT(*) FROM resumes WHERE title LIKE ?", (like,)).fetchone()[0]
            results = db.execute("SELECT * FROM resumes WHERE title LIKE ? ORDER BY title LIMIT ? OFFSET ?",
                                 (like, pp, (page-1)*pp)).fetchall()
        elif field == "company":
            total = db.execute("SELECT COUNT(*) FROM resumes WHERE company LIKE ?", (like,)).fetchone()[0]
            results = db.execute("SELECT * FROM resumes WHERE company LIKE ? ORDER BY company LIMIT ? OFFSET ?",
                                 (like, pp, (page-1)*pp)).fetchall()
        else:
            total = db.execute("SELECT COUNT(*) FROM resumes WHERE name LIKE ? OR title LIKE ? OR company LIKE ?",
                               (like, like, like)).fetchone()[0]
            results = db.execute(
                "SELECT * FROM resumes WHERE name LIKE ? OR title LIKE ? OR company LIKE ? ORDER BY name LIMIT ? OFFSET ?",
                (like, like, like, pp, (page-1)*pp)).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
        results = db.execute("SELECT * FROM resumes ORDER BY name LIMIT ? OFFSET ?",
                             (pp, (page-1)*pp)).fetchall()
    db.close()
    tp = max(1, (total + pp - 1) // pp)
    return render_template("search.html", results=results, query=query, field=field,
                           page=page, total_pages=tp, total_count=total, total_results=total)

@app.route("/resume/<int:rid>")
def resume_detail(rid):
    db = get_db()
    resume = db.execute("SELECT * FROM resumes WHERE id = ?", (rid,)).fetchone()
    if not resume:
        db.close()
        flash("Resume not found.", "error")
        return redirect(url_for("search"))
    unlocked = False
    if session.get("user_id"):
        p = db.execute("SELECT * FROM resume_purchases WHERE user_id = ? AND resume_id = ?",
                       (session["user_id"], rid)).fetchone()
        unlocked = p is not None
    db.close()
    return render_template("resume_detail.html", resume=resume, unlocked=unlocked,
                           credits=session.get("credits", 0))

@app.route("/resume/<int:rid>/unlock", methods=["POST"])
@login_required
def unlock_resume(rid):
    db = get_db()
    resume = db.execute("SELECT * FROM resumes WHERE id = ?", (rid,)).fetchone()
    if not resume:
        db.close()
        flash("Resume not found.", "error")
        return redirect(url_for("search"))
    existing = db.execute("SELECT * FROM resume_purchases WHERE user_id = ? AND resume_id = ?",
                          (session["user_id"], rid)).fetchone()
    if existing:
        db.close()
        return redirect(url_for("resume_detail", rid=rid))
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    cost = Config.COST_PER_RESUME
    if user["credits"] < cost:
        db.close()
        flash("Not enough credits. You need " + str(cost) + " credits.", "error")
        return redirect(url_for("buy_credits"))
    db.execute("UPDATE users SET credits = credits - ? WHERE id = ?", (cost, session["user_id"]))
    db.execute("INSERT INTO resume_purchases (user_id, resume_id, credits_spent) VALUES (?, ?, ?)",
               (session["user_id"], rid, cost))
    db.commit()
    session["credits"] = user["credits"] - cost
    db.close()
    flash("Resume unlocked! Contact details are now visible.", "success")
    return redirect(url_for("resume_detail", rid=rid))

@app.route("/buy-credits")
def buy_credits():
    return render_template("buy_credits.html", packs=Config.CREDIT_PACKS,
                           credits=session.get("credits", 0))

@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    pack_key = request.form.get("pack")
    packs = Config.CREDIT_PACKS
    if pack_key not in packs:
        flash("Invalid credit pack.", "error")
        return redirect(url_for("buy_credits"))
    pack = packs[pack_key]

    if not Config.STRIPE_SECRET_KEY:
        db = get_db()
        db.execute(
            "INSERT INTO credit_orders (user_id, pack_key, credits, amount_cents, status, completed_at) "
            "VALUES (?, ?, ?, ?, 'completed', datetime())",
            (session["user_id"], pack_key, pack["credits"], pack["price_cents"]))
        db.execute("UPDATE users SET credits = credits + ? WHERE id = ?",
                   (pack["credits"], session["user_id"]))
        db.commit()
        session["credits"] = db.execute("SELECT credits FROM users WHERE id = ?",
                                        (session["user_id"],)).fetchone()["credits"]
        db.close()
        flash(str(pack["credits"]) + " credits added! (Demo mode)", "success")
        return redirect(url_for("dashboard"))

    try:
        cs = stripe.checkout.Session.create(
            line_items=[{"price_data": {
                "currency": "usd",
                "product_data": {
                    "name": pack["name"] + " - " + str(pack["credits"]) + " Credits",
                    "description": "View " + str(pack["credits"]) + " IT professional resumes.",
                },
                "unit_amount": pack["price_cents"],
            }, "quantity": 1}],
            mode="payment",
            success_url=request.host_url.rstrip("/") + url_for("payment_success", session_id="{CHECKOUT_SESSION_ID}"),
            cancel_url=request.host_url.rstrip("/") + url_for("buy_credits"),
            metadata={
                "user_id": str(session["user_id"]),
                "pack_key": pack_key,
                "credits": str(pack["credits"]),
            },
        )
        db = get_db()
        db.execute(
            "INSERT INTO credit_orders (user_id, pack_key, credits, amount_cents, stripe_session_id, status) "
            "VALUES (?, ?, ?, ?, ?, 'pending')",
            (session["user_id"], pack_key, pack["credits"], pack["price_cents"], cs.id))
        db.commit()
        db.close()
        return redirect(cs.url, code=303)
    except Exception as e:
        flash("Payment error: " + str(e), "error")
        return redirect(url_for("buy_credits"))

@app.route("/payment-success")
@login_required
def payment_success():
    sid = request.args.get("session_id", "")
    if Config.STRIPE_SECRET_KEY and sid:
        try:
            cs = stripe.checkout.Session.retrieve(sid)
            if cs.payment_status == "paid":
                uid = int(cs.metadata["user_id"])
                if uid != session["user_id"]:
                    flash("Session mismatch.", "error")
                    return redirect(url_for("dashboard"))
                db = get_db()
                order = db.execute(
                    "SELECT * FROM credit_orders WHERE stripe_session_id = ? AND status = 'pending'",
                    (sid,)).fetchone()
                if order:
                    db.execute("UPDATE credit_orders SET status = 'completed', completed_at = datetime() WHERE id = ?",
                               (order["id"],))
                    db.execute("UPDATE users SET credits = credits + ? WHERE id = ?",
                               (int(cs.metadata["credits"]), uid))
                    db.commit()
                    session["credits"] = db.execute("SELECT credits FROM users WHERE id = ?",
                                                    (uid,)).fetchone()["credits"]
                    flash("Credits added successfully!", "success")
                db.close()
        except Exception as e:
            flash("Could not verify payment: " + str(e), "error")
    return redirect(url_for("dashboard"))

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    if not Config.STRIPE_SECRET_KEY:
        return jsonify({"status": "demo_mode"}), 200
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header,
                                                os.environ.get("STRIPE_WEBHOOK_SECRET", ""))
    except Exception:
        return jsonify({"error": "Invalid signature"}), 400
    if event["type"] == "checkout.session.completed":
        sd = event["data"]["object"]
        db = get_db()
        order = db.execute(
            "SELECT * FROM credit_orders WHERE stripe_session_id = ? AND status = 'pending'",
            (sd["id"],)).fetchone()
        if order:
            db.execute("UPDATE credit_orders SET status = 'completed', completed_at = datetime() WHERE id = ?",
                       (order["id"],))
            db.execute("UPDATE users SET credits = credits + ? WHERE id = ?",
                       (int(sd["metadata"]["credits"]), int(sd["metadata"]["user_id"])))
            db.commit()
        db.close()
    return jsonify({"status": "ok"}), 200

@app.route("/admin")
@admin_required
def admin():
    db = get_db()
    users = db.execute("SELECT id, username, email, credits, is_admin FROM users ORDER BY id").fetchall()
    orders = db.execute(
        "SELECT co.*, u.username FROM credit_orders co JOIN users u ON u.id = co.user_id "
        "ORDER BY co.created_at DESC LIMIT 50").fetchall()
    stats = {
        "total_users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "total_resumes": db.execute("SELECT COUNT(*) FROM resumes").fetchone()[0],
        "total_views": db.execute("SELECT COUNT(*) FROM resume_purchases").fetchone()[0],
        "total_revenue": db.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM credit_orders WHERE status='completed'"
        ).fetchone()[0] / 100,
    }
    db.close()
    return render_template("admin.html", users=users, orders=orders, stats=stats)

@app.route("/admin/add-credits", methods=["POST"])
@admin_required
def admin_add_credits():
    user_id = int(request.form["user_id"])
    amount = int(request.form["amount"])
    if amount <= 0:
        flash("Amount must be positive.", "error")
        return redirect(url_for("admin"))
    db = get_db()
    db.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (amount, user_id))
    db.execute("INSERT INTO credit_orders (user_id, pack_key, credits, amount_cents, status, completed_at) "
               "VALUES (?, ?, ?, 0, 'completed', datetime())",
               (user_id, "admin_add", amount))
    db.commit()
    db.close()
    flash("Added " + str(amount) + " credits to user #" + str(user_id) + ".", "success")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    if not os.path.exists(Config.DATABASE):
        print("First run: Initializing database...")
        init_db()
        count = seed_database()
        print("Seeded", count, "resumes.")
        create_admin("admin", "admin123", "admin@levelupitresumes.com")
        print("Admin: admin / admin123")
    print()
    print("Level Up IT Resumes is starting!")
    print("  Open http://127.0.0.1:5050")
    print("  Admin: admin / admin123")
    mode = "LIVE" if Config.STRIPE_SECRET_KEY else "DEMO MODE - credits auto-added"
    print("  Stripe:", mode)
    print()
    app.run(host="127.0.0.1", port=5050, debug=True)
