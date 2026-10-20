"""MongoDB Database Setup and Verification Script.

Usage:
    python scripts/setup_mongodb.py

Reads MONGODB_URI from .env or environment, connects to MongoDB (e.g. Atlas),
and creates the required indexes (unique users.email, financial_profiles.user_id).
Collections themselves are created automatically on first insert.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv

load_dotenv()


def main():
    if not os.environ.get('MONGODB_URI'):
        print("[INFO] MONGODB_URI is not set in .env. Defaulting to local MongoDB (mongodb://localhost:27017/bankease).")

    print("[INFO] Connecting to MongoDB and creating indexes...")
    try:
        from app import create_app
        from app.db import ensure_indexes
        app = create_app()
        database = app.extensions['mongo_db']

        database.client.admin.command('ping')
        ensure_indexes(database)

        print("\n[SUCCESS] Connected to MongoDB successfully!")
        print(f"[SUCCESS] Using database: {database.name}")
        print(f"[SUCCESS] Collections present: {', '.join(database.list_collection_names()) or '(none yet - created on first signup)'}")
        print("[SUCCESS] Your database is ready to use with BankEase!")

    except Exception as e:
        print(f"\n[ERROR] connecting to MongoDB: {e}")
        print("\nTroubleshooting tips for MongoDB Atlas:")
        print("1. Verify the username/password in MONGODB_URI (Atlas -> Database Access).")
        print("2. If your password has special characters (@, :, /, %, etc.), URL-encode them.")
        print("3. Allow your IP in Atlas -> Network Access (use 0.0.0.0/0 for Render).")
        sys.exit(1)


if __name__ == '__main__':
    main()
