"""MongoDB connection handling.

The connection string comes from MONGODB_URI (e.g. a MongoDB Atlas
mongodb+srv:// URI). Tests use a `mongomock://` URI, which swaps in an
in-memory mongomock client so no server is needed.
"""

from flask import current_app

DEFAULT_URI = 'mongodb://localhost:27017/bankease'
DEFAULT_DB_NAME = 'bankease'


def _make_client(uri):
    if uri.startswith('mongomock://'):
        import mongomock
        return mongomock.MongoClient(uri.replace('mongomock://', 'mongodb://', 1))

    from pymongo import MongoClient
    kwargs = {'serverSelectionTimeoutMS': 5000}
    if uri.startswith('mongodb+srv://'):
        # Atlas uses TLS; certifi avoids missing-CA errors on Windows/macOS.
        import certifi
        kwargs['tlsCAFile'] = certifi.where()
    return MongoClient(uri, **kwargs)


def init_db(app):
    uri = app.config['MONGODB_URI']
    client = _make_client(uri)
    database = client.get_default_database(default=DEFAULT_DB_NAME)
    app.extensions['mongo_client'] = client
    app.extensions['mongo_db'] = database

    try:
        ensure_indexes(database)
    except Exception as e:  # don't block startup (e.g. /health) if Mongo is briefly unreachable
        app.logger.warning(f'Could not create MongoDB indexes: {e}')


def ensure_indexes(database):
    database.users.create_index('email', unique=True)
    database.financial_profiles.create_index('user_id')


def get_db():
    return current_app.extensions['mongo_db']
