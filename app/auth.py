"""Authentication: login/logout with bcrypt password hashing."""
import os
import functools
import hashlib
import hmac
import time

from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template, flash, current_app
)

auth_bp = Blueprint('auth', __name__)

# Simple rate limiting: track failed attempts in memory
_failed_attempts = {}  # ip -> (count, last_attempt_time)
MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 300  # 5 minutes


def _check_password(password):
    """Check password against stored hash or env var.

    Supports two modes:
    1. AUTH_PASSWORD_HASH env var set: compare using bcrypt
    2. AUTH_PASSWORD env var set: compare directly (simpler setup)
    """
    stored_hash = current_app.config.get('AUTH_PASSWORD_HASH', '')
    if stored_hash:
        try:
            import bcrypt
            return bcrypt.checkpw(
                password.encode('utf-8'),
                stored_hash.encode('utf-8')
            )
        except Exception:
            return False

    # Fallback: plain text comparison (for dev/simple setups)
    stored_plain = os.environ.get('AUTH_PASSWORD', 'admin')
    return hmac.compare_digest(password, stored_plain)


def _is_rate_limited(ip):
    """Check if an IP is rate-limited due to failed login attempts."""
    if ip not in _failed_attempts:
        return False
    count, last_time = _failed_attempts[ip]
    if time.time() - last_time > LOCKOUT_SECONDS:
        del _failed_attempts[ip]
        return False
    return count >= MAX_ATTEMPTS


def _record_failed_attempt(ip):
    """Record a failed login attempt."""
    now = time.time()
    if ip in _failed_attempts:
        count, _ = _failed_attempts[ip]
        _failed_attempts[ip] = (count + 1, now)
    else:
        _failed_attempts[ip] = (1, now)


def _clear_failed_attempts(ip):
    """Clear failed attempts after successful login."""
    _failed_attempts.pop(ip, None)


def login_required_middleware():
    """Before-request middleware: redirect to login if not authenticated."""
    # Allow the login page and static files
    if request.endpoint in ('auth.login', 'static', None):
        return None
    if not session.get('authenticated'):
        return redirect(url_for('auth.login'))
    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('dashboard.index'))

    error = None
    if request.method == 'POST':
        ip = request.remote_addr
        if _is_rate_limited(ip):
            error = 'Too many failed attempts. Please try again in 5 minutes.'
        else:
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            expected_username = os.environ.get('AUTH_USERNAME', 'admin')

            if (hmac.compare_digest(username, expected_username)
                    and _check_password(password)):
                session['authenticated'] = True
                session['username'] = username
                session.permanent = True
                _clear_failed_attempts(ip)
                return redirect(url_for('dashboard.index'))
            else:
                _record_failed_attempt(ip)
                error = 'Invalid username or password.'

    return render_template('login.html', error=error)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
