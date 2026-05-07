import sqlite3, hashlib, os, csv, re
from config import Config

def get_db_conn():
    """Get database connection - supports both SQLite and PostgreSQL."""
    if Config.is_postgres():
        import psycopg2
        import psycopg2.extras
        db_url = Config.DATABASE_URL
        # Fix Render's postgres:// -> postgresql:// if needed
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        return conn, 'postgres'
    else:
        os.makedirs(os.path.dirname(Config.DATABASE), exist_ok=True)
        conn = sqlite3.connect(Config.DATABASE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn, 'sqlite'

def init_db():
    """Initialize database tables."""
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    password VARCHAR(200) NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    credits INTEGER DEFAULT 0,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(200),
                    email VARCHAR(200),
                    title VARCHAR(300),
                    company VARCHAR(300),
                    linkedin_url VARCHAR(500),
                    phone VARCHAR(100),
                    location VARCHAR(200),
                    skills TEXT,
                    experience TEXT,
                    education TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS resume_views (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    resume_id INTEGER REFERENCES resumes(id),
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, resume_id)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    credits INTEGER NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    stripe_session_id VARCHAR(200),
                    status VARCHAR(50) DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    credits INTEGER DEFAULT 0,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS resumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    email TEXT,
                    title TEXT,
                    company TEXT,
                    linkedin_url TEXT,
                    phone TEXT,
                    location TEXT,
                    skills TEXT,
                    experience TEXT,
                    education TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS resume_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    resume_id INTEGER REFERENCES resumes(id),
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, resume_id)
                );
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER REFERENCES users(id),
                    credits INTEGER NOT NULL,
                    amount_cents INTEGER NOT NULL,
                    stripe_session_id TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()
    finally:
        conn.close()

def seed_database():
    """Seed resumes from CSV."""
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        csv_path = Config.DATA_CSV
        if not os.path.exists(csv_path):
            return 0
        
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                name = row.get('name', '') or ''
                email = row.get('email', '') or ''
                title = row.get('title', '') or ''
                company = row.get('company', '') or ''
                linkedin = row.get('linkedin_url', '') or ''
                phone = row.get('phone', '') or ''
                location = row.get('location', '') or ''
                skills = row.get('skills', '') or ''
                experience = row.get('experience', '') or ''
                education = row.get('education', '') or ''
                
                if db_type == 'postgres':
                    cur.execute(
                        "SELECT id FROM resumes WHERE email=%s AND name=%s",
                        (email, name)
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        "INSERT INTO resumes (name, email, title, company, linkedin_url, phone, location, skills, experience, education) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (name, email, title, company, linkedin, phone, location, skills, experience, education)
                    )
                else:
                    cur.execute(
                        "SELECT id FROM resumes WHERE email=? AND name=?",
                        (email, name)
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        "INSERT INTO resumes (name, email, title, company, linkedin_url, phone, location, skills, experience, education) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (name, email, title, company, linkedin, phone, location, skills, experience, education)
                    )
                count += 1
            conn.commit()
            return count
    finally:
        conn.close()

def create_admin(username, password, email):
    """Create admin user if not exists."""
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        if db_type == 'postgres':
            cur.execute("SELECT id FROM users WHERE username=%s", (username,))
            existing = cur.fetchone()
            if existing:
                return existing[0], False
            cur.execute(
                "INSERT INTO users (username, password, email, credits, is_admin) VALUES (%s,%s,%s,1000,TRUE)",
                (username, pw_hash, email)
            )
        else:
            cur.execute("SELECT id FROM users WHERE username=?", (username,))
            existing = cur.fetchone()
            if existing:
                return existing[0], False
            cur.execute(
                "INSERT INTO users (username, password, email, credits, is_admin) VALUES (?,?,?,1000,1)",
                (username, pw_hash, email)
            )
        conn.commit()
        return cur.lastrowid if db_type == 'sqlite' else True, True
    finally:
        conn.close()

def get_user_by_username(username):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        else:
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
        return cur.fetchone()
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("SELECT * FROM users WHERE id=%s", (user_id,))
        else:
            cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
        return cur.fetchone()
    finally:
        conn.close()

def search_resumes(query, page=1, per_page=20):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        offset = (page - 1) * per_page
        like_pattern = f'%{query}%'
        if query:
            if db_type == 'postgres':
                cur.execute(
                    "SELECT * FROM resumes WHERE name ILIKE %s OR title ILIKE %s OR company ILIKE %s ORDER BY name LIMIT %s OFFSET %s",
                    (like_pattern, like_pattern, like_pattern, per_page, offset)
                )
                cur_count = conn.cursor()
                cur_count.execute("SELECT COUNT(*) FROM resumes WHERE name ILIKE %s OR title ILIKE %s OR company ILIKE %s", (like_pattern, like_pattern, like_pattern))
            else:
                cur.execute(
                    "SELECT * FROM resumes WHERE name LIKE ? OR title LIKE ? OR company LIKE ? ORDER BY name LIMIT ? OFFSET ?",
                    (like_pattern, like_pattern, like_pattern, per_page, offset)
                )
                cur_count = conn.cursor()
                cur_count.execute("SELECT COUNT(*) FROM resumes WHERE name LIKE ? OR title LIKE ? OR company LIKE ?", (like_pattern, like_pattern, like_pattern))
        else:
            if db_type == 'postgres':
                cur.execute("SELECT * FROM resumes ORDER BY name LIMIT %s OFFSET %s", (per_page, offset))
                cur_count = conn.cursor()
                cur_count.execute("SELECT COUNT(*) FROM resumes")
            else:
                cur.execute("SELECT * FROM resumes ORDER BY name LIMIT ? OFFSET ?", (per_page, offset))
                cur_count = conn.cursor()
                cur_count.execute("SELECT COUNT(*) FROM resumes")
        
        rows = cur.fetchall()
        total = cur_count.fetchone()[0]
        return [dict(r) for r in rows], total
    finally:
        conn.close()

def get_resume(resume_id):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("SELECT * FROM resumes WHERE id=%s", (resume_id,))
        else:
            cur.execute("SELECT * FROM resumes WHERE id=?", (resume_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def has_viewed_resume(user_id, resume_id):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("SELECT id FROM resume_views WHERE user_id=%s AND resume_id=%s", (user_id, resume_id))
        else:
            cur.execute("SELECT id FROM resume_views WHERE user_id=? AND resume_id=?", (user_id, resume_id))
        return cur.fetchone() is not None
    finally:
        conn.close()

def record_view(user_id, resume_id):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("INSERT INTO resume_views (user_id, resume_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, resume_id))
        else:
            cur.execute("INSERT OR IGNORE INTO resume_views (user_id, resume_id) VALUES (?, ?)", (user_id, resume_id))
        conn.commit()
    finally:
        conn.close()

def deduct_credit(user_id):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("UPDATE users SET credits = credits - 1 WHERE id=%s AND credits > 0", (user_id,))
        else:
            cur.execute("UPDATE users SET credits = credits - 1 WHERE id=? AND credits > 0", (user_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()

def add_credits(user_id, credits):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("UPDATE users SET credits = credits + %s WHERE id=%s", (credits, user_id))
        else:
            cur.execute("UPDATE users SET credits = credits + ? WHERE id=?", (credits, user_id))
        conn.commit()
    finally:
        conn.close()

def get_user_stats(user_id):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("SELECT COUNT(*) as total FROM resume_views WHERE user_id=%s", (user_id,))
            views_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(amount_cents), 0) as total FROM orders WHERE user_id=%s", (user_id,))
            spent = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(credits), 0) as total FROM orders WHERE user_id=%s", (user_id,))
            total_credits = cur.fetchone()[0]
        else:
            cur.execute("SELECT COUNT(*) as total FROM resume_views WHERE user_id=?", (user_id,))
            views_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(amount_cents), 0) as total FROM orders WHERE user_id=?", (user_id,))
            spent = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(credits), 0) as total FROM orders WHERE user_id=?", (user_id,))
            total_credits = cur.fetchone()[0]
        return views_count, spent, total_credits
    finally:
        conn.close()

def get_all_users():
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("SELECT id, username, email, credits, is_admin, created_at FROM users ORDER BY id")
        else:
            cur.execute("SELECT id, username, email, credits, is_admin, created_at FROM users ORDER BY id")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def record_order(user_id, credits, amount_cents, stripe_session_id='', status='completed'):
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute(
                "INSERT INTO orders (user_id, credits, amount_cents, stripe_session_id, status) VALUES (%s,%s,%s,%s,%s)",
                (user_id, credits, amount_cents, stripe_session_id, status)
            )
        else:
            cur.execute(
                "INSERT INTO orders (user_id, credits, amount_cents, stripe_session_id, status) VALUES (?,?,?,?,?)",
                (user_id, credits, amount_cents, stripe_session_id, status)
            )
        conn.commit()
    finally:
        conn.close()

def get_resume_count():
    conn, db_type = get_db_conn()
    try:
        cur = conn.cursor()
        if db_type == 'postgres':
            cur.execute("SELECT COUNT(*) FROM resumes")
        else:
            cur.execute("SELECT COUNT(*) FROM resumes")
        return cur.fetchone()[0]
    finally:
        conn.close()
