import json
import os
from flask import Blueprint, Response, send_from_directory
from flask_login import current_user, login_required

spa_bp = Blueprint('spa', __name__)

SPA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'spa'))

# Small account bar added to the prebuilt SPA (its source isn't in this repo).
# It is created from script, and re-added if missing, because React hydration
# replaces the server-rendered document and drops nodes it didn't render.
ACCOUNT_SCRIPT = """<script>(function(){var email=%s;function add(){
if(!document.body||document.getElementById('be-account'))return;
var d=document.createElement('div');d.id='be-account';
d.style.cssText='position:fixed;left:12px;bottom:124px;z-index:2147483000;font:12px/1.4 system-ui,sans-serif;background:#111;color:#fff;border-radius:999px;padding:6px 12px;box-shadow:0 2px 8px rgba(0,0,0,.25)';
d.appendChild(document.createTextNode(email+' \\u00b7 '));
var a=document.createElement('a');a.href='/auth/logout';a.textContent='Log out';a.style.cssText='color:#fff;text-decoration:underline';
d.appendChild(a);document.body.appendChild(d);}
add();setInterval(add,1000);})();</script>"""


@spa_bp.route('/profile')
@spa_bp.route('/savings')
@spa_bp.route('/planner')
@spa_bp.route('/market')
@spa_bp.route('/assistant')
@spa_bp.route('/goals')
@spa_bp.route('/settings')
@spa_bp.route('/')  # registered first (decorators apply bottom-up) so url_for('spa.serve_spa') == '/'
@login_required
def serve_spa():
    """Serve the modern pixel-perfect BankEase SPA (login required)."""
    with open(os.path.join(SPA_DIR, 'index.html'), 'rb') as f:
        html = f.read()
    if current_user.is_authenticated:
        email_js = json.dumps(current_user.email).replace('<', '\\u003c')
        script = (ACCOUNT_SCRIPT % email_js).encode('utf-8')
        html = html.replace(b'</body>', script + b'</body>', 1)
    return Response(html, mimetype='text/html', headers={'Cache-Control': 'no-cache'})


@spa_bp.route('/assets/<path:filename>')
def serve_spa_assets(filename):
    """Serve SPA bundled javascript and css chunks."""
    response = send_from_directory(os.path.join(SPA_DIR, 'assets'), filename)
    # Chunks are patched in place under their original hashed names, so browsers
    # must revalidate (cheap 304s via ETag) instead of trusting a stale cached copy.
    response.headers['Cache-Control'] = 'no-cache'
    return response


@spa_bp.route('/favicon.ico')
def serve_spa_favicon():
    """Serve favicon."""
    return send_from_directory(SPA_DIR, 'favicon.ico')
