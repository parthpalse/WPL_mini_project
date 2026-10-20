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
