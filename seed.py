#!/usr/bin/env python3
"""Initialize the database and seed with resume data."""
from models import init_db, seed_database, create_admin, get_resume_count, Config

def main():
    import os
    
    print(f"Database mode: {'PostgreSQL' if Config.is_postgres() else 'SQLite'}")
    
    # Check if already seeded (for PostgreSQL - check env var)
    if Config.is_postgres():
        import psycopg2
        db_url = Config.DATABASE_URL
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM resumes")
        count = cur.fetchone()[0]
        conn.close()
        if count > 0:
            print(f"Database already has {count} resumes. Skipping seed.")
            uid, created = create_admin("admin", "admin123", "admin@levelupitresumes.com")
            print(f"Admin user: {'created' if created else 'already exists'}")
            print(f"Total resumes in DB: {count}")
            print("Done!")
            return
    
    print("Initializing database...")
    init_db()
    print("Seeding resume data...")
    count = seed_database()
    if count > 0:
        print(f"Loaded {count} resumes into database.")
    else:
        print("No new resumes loaded (may already be seeded or CSV empty).")
    
    total = get_resume_count()
    print(f"Total resumes in DB: {total}")
    
    uid, created = create_admin("admin", "admin123", "admin@levelupitresumes.com")
    if created:
        print("Created admin user: admin / admin123")
    else:
        print("Admin user already exists.")
    print()
    print("Done! Run with: gunicorn app:app --bind 0.0.0.0:$PORT")
    print("Login: admin / admin123")

if __name__ == "__main__":
    main()
