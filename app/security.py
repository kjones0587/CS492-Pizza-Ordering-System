import secrets
from flask import session, request, jsonify, flash, redirect, url_for, current_app

def generate_csrf_token():
    """Task T2-10 (PB-11: Ayden Lotter): Generate or retrieve session CSRF token."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

def validate_csrf():
    """Task T2-10 (PB-11: Ayden Lotter): Intercept and validate state-changing POST requests."""
    # Bypass in testing mode or if CSRF explicitly disabled
    if not current_app.config.get('WTF_CSRF_ENABLED', True) or current_app.config.get('TESTING'):
        return None

    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        session_token = session.get('_csrf_token')
        if not session_token or not token or not secrets.compare_digest(token, session_token):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': 'CSRF verification failed. Please refresh the page.'}), 403
            flash('Your session token has expired or is invalid. Please try again.', 'danger')
            return redirect(request.referrer or url_for('menu.index'))
    return None
