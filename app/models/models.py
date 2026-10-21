from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask_login import UserMixin
from pymongo.errors import DuplicateKeyError

from app.db import get_db


class User(UserMixin):
    """A user document in the `users` collection."""

    def __init__(self, doc):
        self.doc = doc
        self.id = str(doc['_id'])
        self.email = doc['email']
        self.password_hash = doc['password_hash']
        self.created_at = doc.get('created_at')

    @staticmethod
    def get_by_id(user_id):
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            return None
        doc = get_db().users.find_one({'_id': oid})
        return User(doc) if doc else None

    @staticmethod
    def get_by_email(email):
        doc = get_db().users.find_one({'email': email})
        return User(doc) if doc else None

    @staticmethod
    def create(email, password_hash):
        """Insert a new user. Returns None if the email is already taken."""
        doc = {
            'email': email,
            'password_hash': password_hash,
            'created_at': datetime.now(timezone.utc),
        }
        try:
            result = get_db().users.insert_one(doc)
        except DuplicateKeyError:
            return None
        doc['_id'] = result.inserted_id
        return User(doc)


class UserData:
    """Per-user SPA state (profile + goals) in the `user_data` collection."""

    @staticmethod
    def get(user_id):
        return get_db().user_data.find_one({'user_id': ObjectId(user_id)}) or {}

    @staticmethod
    def save(user_id, **fields):
        """Upsert top-level fields, e.g. save(uid, profile={...}) or save(uid, goals=[...])."""
        get_db().user_data.update_one(
            {'user_id': ObjectId(user_id)},
            {'$set': {**fields, 'updated_at': datetime.now(timezone.utc)}},
            upsert=True,
        )

    @staticmethod
    def profile_complete(user_id):
        """True once the user has saved a financial profile with an income."""
        profile = UserData.get(user_id).get('profile') or {}
        try:
            return float(profile.get('monthlyGrossIncome') or 0) > 0
        except (TypeError, ValueError):
            return False


class FinancialProfile:
    """Wizard submissions in the `financial_profiles` collection."""

    @staticmethod
    def create(user_id, wizard_data):
        doc = {
            'user_id': ObjectId(user_id),
            'created_at': datetime.now(timezone.utc),
            'wizard_data': dict(wizard_data),
        }
        return get_db().financial_profiles.insert_one(doc).inserted_id
