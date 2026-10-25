import json
import os
import re
from flask import Blueprint, Response, redirect, render_template, request, send_from_directory
from flask_login import current_user, login_required
from app.models.models import UserData

spa_bp = Blueprint('spa', __name__)

SPA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'spa'))

# SPA pages in sidebar order: path, sidebar label, mobile tab-bar label (None = menu only), icon.
# Keep in step with the nav list in the bundle (static/spa/assets/index-*.js).
PAGES = [
    {'path': '/', 'label': 'Overview', 'short': 'Overview', 'icon': 'layout-dashboard'},
    {'path': '/profile', 'label': 'Financial Profile', 'short': 'Profile', 'icon': 'user-round'},
    {'path': '/savings', 'label': 'Savings Capacity', 'short': 'Savings', 'icon': 'piggy-bank'},
    {'path': '/planner', 'label': 'Investment Planner', 'short': 'Planner', 'icon': 'chart-line'},
    {'path': '/market', 'label': 'Market Watch', 'short': None, 'icon': 'activity'},
    {'path': '/assistant', 'label': 'AI Assistant', 'short': None, 'icon': 'message-circle'},
    {'path': '/goals', 'label': 'Goals', 'short': 'Goals', 'icon': 'target'},
]
TITLES = {page['path']: page['label'] for page in PAGES}

# Renders the assistant's Markdown replies (lists, bold, tables) inside chat bubbles.
MARKDOWN_SCRIPT = '<script src="/static/js/spa-md.js"></script>'

# Account details for the layout, read by the bundle. Until the financial profile is saved,
# every client-side navigation is forced to /profile, and the first successful save sends
# the user on to the report. Runs in <head>, before the app's module script.
CONFIG_SCRIPT = """<script>window.__beEmail=%s;window.__beDone=%s;(function(){
function target(u){try{return new URL(u,location.href).pathname}catch(e){return null}}
['pushState','replaceState'].forEach(function(k){var o=history[k];
history[k]=function(s,t,u){if(!window.__beDone&&u!=null&&target(u)!=='/profile')u='/profile';return o.call(this,s,t,u);};});
var f=window.fetch;window.fetch=function(i,o){var p=f.apply(this,arguments);
if(o&&/^(PUT|POST)$/i.test(o.method||'')&&String(i).indexOf('/api/profile')===0){p.then(function(r){
if(!r.ok)return;r.clone().json().then(function(d){if(d&&Number(d.monthlyGrossIncome)>0){
var first=!window.__beDone;window.__beDone=true;
if(first)setTimeout(function(){window.location.href='/';},800);}}).catch(function(){});}).catch(function(){});}
return p;};})();</script>"""


@spa_bp.route('/profile')
@spa_bp.route('/savings')
@spa_bp.route('/planner')
@spa_bp.route('/market')
@spa_bp.route('/assistant')
@spa_bp.route('/goals')
@spa_bp.route('/')  # registered first (decorators apply bottom-up) so url_for('spa.serve_spa') == '/'
@login_required
def serve_spa():
    """Serve the modern pixel-perfect BankEase SPA (login required)."""
    done = UserData.profile_complete(current_user.id) if current_user.is_authenticated else True
    if not done and request.path != '/profile':
        return redirect('/profile')  # no exceptions: finish the financial profile first
    email = current_user.email if current_user.is_authenticated else ''
    with open(os.path.join(SPA_DIR, 'index.html'), encoding='utf-8') as f:
        html = f.read()
    shell = render_template('spa/shell.html', pages=PAGES, path=request.path, email=email, setup=not done)
    html = html.replace('<!--be:shell-->', shell, 1)
    html = re.sub(r'<title>[^<]*</title>', f'<title>{TITLES[request.path]} — BankEase</title>', html, count=1)
    email_js = json.dumps(email).replace('<', '\\u003c')
    html = html.replace('</head>', (CONFIG_SCRIPT % (email_js, 'true' if done else 'false')) + '</head>', 1)
    html = html.replace('</body>', MARKDOWN_SCRIPT + '</body>', 1)
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
