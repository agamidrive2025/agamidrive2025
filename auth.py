"""
Authentication Module - Login/Logout System
"""
from functools import wraps
from flask import redirect, url_for, session, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from datetime import datetime

class AuthManager:
    """Handle user authentication"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_auth_db()
    
    def init_auth_db(self):
        """Create users table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                email TEXT,
                role TEXT DEFAULT 'admin',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            )
        ''')
        
        # Create default admin user if not exists
        try:
            hashed_pwd = generate_password_hash('admin123')
            cursor.execute(
                "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                ('admin', hashed_pwd, 'admin@factory.com', 'admin')
            )
            conn.commit()
            print("✅ ডিফল্ট Admin ইউজার তৈরি: admin / admin123")
        except sqlite3.IntegrityError:
            pass  # User already exists
        
        conn.close()
    
    def login(self, username, password):
        """Verify user login"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            # Update last login
            cursor.execute(
                "UPDATE users SET last_login=? WHERE id=?",
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user['id'])
            )
            conn.commit()
            conn.close()
            return dict(user)
        
        conn.close()
        return None
    
    def register(self, username, password, email):
        """Register new user"""
        try:
            conn = sqlite3.connect(self.db_path)
            hashed_pwd = generate_password_hash(password)
            
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                (username, hashed_pwd, email, 'admin')
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def change_password(self, username, old_password, new_password):
        """Change user password"""
        user = self.login(username, old_password)
        if not user:
            return False
        
        conn = sqlite3.connect(self.db_path)
        hashed_pwd = generate_password_hash(new_password)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password=? WHERE username=?", (hashed_pwd, username))
        conn.commit()
        conn.close()
        return True

# Login decorator
def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def api_login_required(f):
    """Decorator for API endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': 'প্রথমে লগইন করুন'}), 401
        return f(*args, **kwargs)
    return decorated_function
