import json
import os
from flask import Blueprint, Response, redirect, request, send_from_directory
from flask_login import current_user, login_required
from app.models.models import UserData

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

# Until the financial profile is saved, every client-side navigation is forced to
# /profile, and the first successful save sends the user on to the report.
GUARD_SCRIPT = """<script>(function(){window.__beDone=%s;
function target(u){try{return new URL(u,location.href).pathname}catch(e){return null}}
['pushState','replaceState'].forEach(function(k){var o=history[k];
history[k]=function(s,t,u){if(!window.__beDone&&u!=null&&target(u)!=='/profile')u='/profile';return o.call(this,s,t,u);};});
var f=window.fetch;window.fetch=function(i,o){var p=f.apply(this,arguments);
if(o&&/^(PUT|POST)$/i.test(o.method||'')&&String(i).indexOf('/api/profile')===0){p.then(function(r){
if(!r.ok)return;r.clone().json().then(function(d){if(d&&Number(d.monthlyGrossIncome)>0){
var first=!window.__beDone;window.__beDone=true;var b=document.getElementById('be-setup');if(b)b.remove();
if(first)setTimeout(function(){window.location.href='/';},800);}}).catch(function(){});}).catch(function(){});}
return p;};
function banner(){if(window.__beDone||location.pathname!=='/profile'||!document.body||document.getElementById('be-setup'))return;
var d=document.createElement('div');d.id='be-setup';
d.style.cssText='position:fixed;top:0;left:0;right:0;z-index:2147483000;font:14px/1.4 system-ui,sans-serif;background:#111;color:#fff;padding:10px 16px;text-align:center';
d.textContent='Welcome! Set up your financial profile (at least your monthly income) and press Save to unlock the rest of BankEase.';
document.body.appendChild(d);}
banner();setInterval(banner,1000);})();</script>"""


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
    done = UserData.profile_complete(current_user.id) if current_user.is_authenticated else True
    if not done and request.path != '/profile':
        return redirect('/profile')  # no exceptions: finish the financial profile first
    with open(os.path.join(SPA_DIR, 'index.html'), 'rb') as f:
        html = f.read()
    if current_user.is_authenticated:
        email_js = json.dumps(current_user.email).replace('<', '\\u003c')
        script = ((ACCOUNT_SCRIPT % email_js) + (GUARD_SCRIPT % ('true' if done else 'false'))).encode('utf-8')
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
