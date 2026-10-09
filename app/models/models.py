from datetime import datetime
from flask_login import UserMixin
from app import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profiles = db.relationship('FinancialProfile', backref='user', lazy=True)
    plans = db.relationship('PlanResult', backref='user', lazy=True)


class FinancialProfile(db.Model):
    __tablename__ = 'financial_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    wizard_data_json = db.Column(db.Text, default='{}')


class Goal(db.Model):
    __tablename__ = 'goals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    horizon_years = db.Column(db.Integer, nullable=False)
    priority = db.Column(db.Integer, default=1)

    user = db.relationship('User', backref=db.backref('goals', lazy=True))


class PlanResult(db.Model):
    __tablename__ = 'plan_results'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('financial_profiles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Computed results (stored as JSON)
    tax_breakdown_json = db.Column(db.Text)
    surplus_breakdown_json = db.Column(db.Text)
    allocation_safe_json = db.Column(db.Text)
    allocation_balanced_json = db.Column(db.Text)
    allocation_growth_json = db.Column(db.Text)
    ai_explanation = db.Column(db.Text)

    profile = db.relationship('FinancialProfile', backref=db.backref('results', lazy=True))
