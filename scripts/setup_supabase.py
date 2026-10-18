"""Supabase / PostgreSQL Database Setup and Verification Script.

Usage:
    python scripts/setup_supabase.py

Reads DATABASE_URL from .env or environment, connects to Supabase,
and creates/verifies all required tables (users, financial_profiles, etc.).
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv

load_dotenv()


def main():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print("[INFO] DATABASE_URL is not set in .env. Defaulting to local SQLite.")
        db_url = "sqlite:///bankease.db"
        os.environ['DATABASE_URL'] = db_url

    if 'sqlite' in db_url.lower():
        print(f"[INFO] Current DATABASE_URL is pointing to local SQLite: {db_url}")
        print("To switch to Supabase, update DATABASE_URL in .env to your Supabase PostgreSQL URI.")

    # Fix postgres:// prefix if present
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
        os.environ['DATABASE_URL'] = db_url

    print("[INFO] Connecting to database and creating tables...")
    try:
        from app import create_app, db
        app = create_app()

        with app.app_context():
            # Create all tables (User, FinancialProfile, Goal, PlanResult, etc.)
            db.create_all()

            # Inspect created tables
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            print("\n[SUCCESS] Connected to database successfully!")
            print(f"[SUCCESS] Verified tables present in database: {', '.join(tables)}")
            print("[SUCCESS] Your database is ready to use with BankEase!")

    except Exception as e:
        print(f"\n[ERROR] connecting to database: {e}")
        print("\nTroubleshooting tips for Supabase:")
        print("1. Verify your password is correct in the DATABASE_URL.")
        print("2. If your password has special characters (@, :, %, etc.), URL-encode them.")
        print("3. Use the Connection Pooler URL (port 6543) if connecting from networks with IPv4 restrictions.")
        sys.exit(1)


if __name__ == '__main__':
    main()
