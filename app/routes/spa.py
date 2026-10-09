import os
from flask import Blueprint, send_from_directory

spa_bp = Blueprint('spa', __name__)

SPA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'spa'))


@spa_bp.route('/')
@spa_bp.route('/profile')
@spa_bp.route('/savings')
@spa_bp.route('/planner')
@spa_bp.route('/market')
@spa_bp.route('/assistant')
@spa_bp.route('/goals')
@spa_bp.route('/settings')
def serve_spa():
    """Serve the modern pixel-perfect BankEase SPA."""
    return send_from_directory(SPA_DIR, 'index.html')


@spa_bp.route('/assets/<path:filename>')
def serve_spa_assets(filename):
    """Serve SPA bundled javascript and css chunks."""
    return send_from_directory(os.path.join(SPA_DIR, 'assets'), filename)


@spa_bp.route('/favicon.ico')
def serve_spa_favicon():
    """Serve favicon."""
    return send_from_directory(SPA_DIR, 'favicon.ico')
