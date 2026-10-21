from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.models import User, UserData

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def _landing_page(user):
    """Returning users with a saved profile see their report; everyone else sets up a profile first."""
    if UserData.profile_complete(user.id):
        return redirect(url_for('spa.serve_spa'))
    return redirect('/profile')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _landing_page(current_user)
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.get_by_email(email)

        if not user or not check_password_hash(user.password_hash, password):
            flash('Please check your login details and try again.', 'error')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        return _landing_page(user)

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return _landing_page(current_user)

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        user = User.get_by_email(email)

        if user:
            flash('Email address already exists', 'error')
            return redirect(url_for('auth.register'))

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.register'))

        new_user = User.create(email, generate_password_hash(password, method='pbkdf2:sha256'))
        if new_user is None:  # lost a race with a concurrent signup for the same email
            flash('Email address already exists', 'error')
            return redirect(url_for('auth.register'))

        login_user(new_user)
        return redirect('/profile')  # new accounts start empty: set up the financial profile first

    return render_template('auth/register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('spa.serve_spa'))
