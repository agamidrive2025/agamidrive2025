from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import pandas as pd
import os
from datetime import datetime, timedelta
from auth import AuthManager, login_required, api_login_required

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
app.config['SESSION_COOKIE_SECURE'] = False  # লোকালে False রাখুন, প্রোডাকশনে True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

DB_PATH = 'training.db'
auth_manager = AuthManager(DB_PATH)

MONTHS_BN = {
    1: 'জানুয়ারি', 2: 'ফেব্রুয়ারি', 3: 'মার্চ', 4: 'এপ্রিল',
    5: 'মে', 6: 'জুন', 7: 'জুলাই', 8: 'আগস্ট',
    9: 'সেপ্টেম্বর', 10: 'অক্টোবর', 11: 'নভেম্বর', 12: 'ডিসেম্বর'
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # ডাটাবেজ টেবিল স্কিমা
    cur.executescript('''
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            designation TEXT,
            card_number TEXT UNIQUE NOT NULL,
            department TEXT,
            line_number TEXT,
            phone_number TEXT,
            join_date TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS training_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL,
            training_id INTEGER NOT NULL,
            month INTEGER NOT NULL,
            year INTEGER NOT NULL,
            training_date TEXT,
            status TEXT DEFAULT 'Completed',
            remarks TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (worker_id) REFERENCES workers(id),
            FOREIGN KEY (training_id) REFERENCES trainings(id),
            UNIQUE(worker_id, training_id, month, year)
        );
    ''')

    # নতুন কলাম যুক্ত করার সেফটি লজিক
    try:
        cur.execute("ALTER TABLE workers ADD COLUMN line_number TEXT;")
    except sqlite3.OperationalError:
        pass

    try:
        cur.execute("ALTER TABLE workers ADD COLUMN phone_number TEXT;")
    except sqlite3.OperationalError:
        pass

    # ডিফল্ট ট্রেনিং যোগ করুন
    default_trainings = [
        ('Fire Safety Training', 'অগ্নি নিরাপত্তা প্রশিক্ষণ'),
        ('First Aid Training', 'প্রাথমিক চিকিৎসা প্রশিক্ষণ'),
        ('Chemical Handling', 'রাসায়নিক পদার্থ পরিচালনা'),
        ('Machine Safety', 'মেশিন নিরাপত্তা'),
        ('PPE Usage', 'ব্যক্তিগত সুরক্ষা সরঞ্জাম ব্যবহার'),
        ('Emergency Evacuation', 'জরুরি সরিয়ে নেওয়া'),
        ('Electrical Safety', 'বৈদ্যুতিক নিরাপত্তা'),
        ('Manual Handling', 'ম্যানুয়াল হ্যান্ডলিং'),
        ('Health & Hygiene', 'স্বাস্থ্য ও পরিচ্ছন্নতা'),
        ('Quality Awareness', 'মান সচেতনতা'),
    ]
    for t in default_trainings:
        try:
            cur.execute("INSERT OR IGNORE INTO trainings (name, description) VALUES (?, ?)", t)
        except:
            pass

    conn.commit()
    conn.close()

# ─── AUTHENTICATION ROUTES ───────────────────────────────────────────────

@app.route('/login')
def login_page():
    """লগইন পেজ দেখান"""
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/api/login', methods=['POST'])
def login():
    """ইউজার লগইন করান"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'ইউজারনেম এবং পাসওয়ার্ড প্রয়োজন'}), 400
    
    user = auth_manager.login(username, password)
    
    if user:
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({'success': True, 'message': 'লগইন সফল'})
    else:
        return jsonify({'success': False, 'message': 'ইউজারনেম বা পাসওয়ার্ড ভুল'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """ইউজার লগআউট করান"""
    session.clear()
    return jsonify({'success': True, 'message': 'লগআউট সফল'})

@app.route('/api/user-info', methods=['GET'])
def get_user_info():
    """বর্তমান লগইনকৃত ইউজারের তথ্য"""
    if 'user_id' in session:
        return jsonify({
            'success': True,
            'user_id': session.get('user_id'),
            'username': session.get('username'),
            'role': session.get('role')
        })
    else:
        return jsonify({'success': False, 'message': 'লগইন করা হয়নি'}), 401

# ─── MAIN ROUTES ───────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    """মেইন ড্যাশবোর্ড পেজ"""
    return render_template('index.html', months=MONTHS_BN)

# ── Workers ──
@app.route('/api/workers', methods=['GET'])
@api_login_required
def get_workers():
    search = request.args.get('search', '').strip()
    conn = get_db()
    if search:
        rows = conn.execute(
            "SELECT * FROM workers WHERE is_active=1 AND (name LIKE ? OR card_number LIKE ? OR designation LIKE ? OR phone_number LIKE ?)",
            (f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%')
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM workers WHERE is_active=1 ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/workers/<int:worker_id>', methods=['GET'])
@api_login_required
def get_worker(worker_id):
    conn = get_db()
    worker = conn.execute("SELECT * FROM workers WHERE id=?", (worker_id,)).fetchone()
    conn.close()
    if not worker:
        return jsonify({'error': 'Worker not found'}), 404
    return jsonify(dict(worker))

@app.route('/api/workers', methods=['POST'])
@api_login_required
def add_worker():
    data = request.json
    if not data.get('name') or not data.get('card_number'):
        return jsonify({'success': False, 'message': 'নাম এবং কার্ড নম্বর প্রয়োজন'}), 400
    
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO workers (name, designation, card_number, department, line_number, phone_number, join_date) VALUES (?,?,?,?,?,?,?)",
            (data['name'].strip(), data.get('designation',''), data['card_number'].strip(),
             data.get('department',''), data.get('line_number',''), data.get('phone_number',''),
             data.get('join_date', datetime.now().strftime('%Y-%m-%d')))
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'শ্রমিক যোগ করা হয়েছে'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'এই কার্ড নম্বর আগেই আছে'}), 400
    finally:
        conn.close()

@app.route('/api/workers/<int:worker_id>', methods=['PUT'])
@api_login_required
def update_worker(worker_id):
    data = request.json
    conn = get_db()
    try:
        conn.execute(
            "UPDATE workers SET name=?, designation=?, department=?, line_number=?, phone_number=?, join_date=? WHERE id=?",
            (data['name'].strip(), data.get('designation',''), data.get('department',''),
             data.get('line_number',''), data.get('phone_number',''), data.get('join_date',''), worker_id)
        )
        conn.commit()
        return jsonify({'success': True, 'message': 'তথ্য আপডেট হয়েছে'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/workers/<int:worker_id>', methods=['DELETE'])
@api_login_required
def delete_worker(worker_id):
    conn = get_db()
    conn.execute("UPDATE workers SET is_active=0 WHERE id=?", (worker_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'শ্রমিক সরানো হয়েছে'})

# ── Excel Upload (শ্রমিক যোগ করা) ──
@app.route('/api/workers/upload', methods=['POST'])
@api_login_required
def upload_workers():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'ফাইল পাওয়া যায়নি'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'শুধু Excel (.xlsx/.xls) ফাইল গ্রহণযোগ্য'}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        df = pd.read_excel(filepath)
        df.columns = df.columns.str.strip().str.lower()

        # ডাইনামিক কলাম ম্যাপিং
        col_map = {}
        for col in df.columns:
            if 'name' in col or 'নাম' in col:
                col_map['name'] = col
            elif 'designation' in col or 'পদবী' in col or 'পদ' in col:
                col_map['designation'] = col
            elif 'card' in col or 'id' in col or 'কার্ড' in col:
                col_map['card_number'] = col
            elif 'dept' in col or 'বিভাগ' in col:
                col_map['department'] = col
            elif 'line' in col or 'লাইন' in col:
                col_map['line_number'] = col
            elif 'phone' in col or 'মোবাইল' in col or 'ফোন' in col:
                col_map['phone_number'] = col

        if 'name' not in col_map or 'card_number' not in col_map:
            return jsonify({'success': False, 'message': 'Excel এ "Name" ও "Card Number" কলাম থাকতে হবে'}), 400

        conn = get_db()
        added, skipped = 0, 0
        for _, row in df.iterrows():
            try:
                raw_join_date = str(row[col_map['join_date']]).strip() if col_map.get('join_date') else ''
                if raw_join_date and raw_join_date.lower() != 'nan' and raw_join_date != '':
                    join_date = raw_join_date.split(' ')[0]
                else:
                    join_date = datetime.now().strftime('%Y-%m-%d')

                def get_val(key):
                    val = str(row[col_map[key]]).strip() if col_map.get(key) else ''
                    return '' if val.lower() == 'nan' else val

                conn.execute(
                    "INSERT OR IGNORE INTO workers (name, designation, card_number, department, line_number, phone_number, join_date) VALUES (?,?,?,?,?,?,?)",
                    (get_val('name'), get_val('designation'), get_val('card_number'), 
                     get_val('department'), get_val('line_number'), get_val('phone_number'), join_date)
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    added += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'{added} জন নতুন শ্রমিক যোগ হয়েছে, {skipped} জন আগেই আছে'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'ফাইল পড়তে সমস্যা: {str(e)}'}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

# ── Trainings ──
@app.route('/api/trainings', methods=['GET'])
@api_login_required
def get_trainings():
    conn = get_db()
    rows = conn.execute("SELECT * FROM trainings WHERE is_active=1 ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/trainings', methods=['POST'])
@api_login_required
def add_training():
    data = request.json
    if not data.get('name'):
        return jsonify({'success': False, 'message': 'ট্রেনিংয়ের নাম প্রয়োজন'}), 400
    
    conn = get_db()
    try:
        conn.execute("INSERT INTO trainings (name, description) VALUES (?,?)",
                     (data['name'].strip(), data.get('description', '')))
        conn.commit()
        return jsonify({'success': True, 'message': 'ট্রেনিং যোগ করা হয়েছে'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'এই ট্রেনিং আগেই আছে'}), 400
    finally:
        conn.close()

@app.route('/api/trainings/<int:training_id>', methods=['DELETE'])
@api_login_required
def delete_training(training_id):
    conn = get_db()
    conn.execute("UPDATE trainings SET is_active=0 WHERE id=?", (training_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'ট্রেনিং সরানো হয়েছে'})

# ── Training Records ──
@app.route('/api/records', methods=['GET'])
@api_login_required
def get_records():
    worker_id = request.args.get('worker_id')
    month = request.args.get('month')
    year = request.args.get('year', datetime.now().year)
    conn = get_db()
    query = '''
        SELECT tr.*, w.name as worker_name, w.card_number, w.designation,
               t.name as training_name
        FROM training_records tr
        JOIN workers w ON tr.worker_id = w.id
        JOIN trainings t ON tr.training_id = t.id
        WHERE 1=1
    '''
    params = []
    if worker_id:
        query += " AND tr.worker_id=?"
        params.append(worker_id)
    if month:
        query += " AND tr.month=?"
        params.append(month)
    if year:
        query += " AND tr.year=?"
        params.append(year)
    query += " ORDER BY tr.year, tr.month, w.name"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/records/worker/<int:worker_id>/year/<int:year>', methods=['GET'])
@api_login_required
def get_worker_year_records(worker_id, year):
    conn = get_db()
    records = conn.execute('''
        SELECT tr.month, tr.training_id, tr.training_date, tr.status, tr.remarks,
               t.name as training_name
        FROM training_records tr
        JOIN trainings t ON tr.training_id = t.id
        WHERE tr.worker_id=? AND tr.year=?
        ORDER BY tr.month, t.name
    ''', (worker_id, year)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in records])

@app.route('/api/records', methods=['POST'])
@api_login_required
def add_record():
    data = request.json
    if not data.get('worker_id') or not data.get('training_id') or not data.get('month'):
        return jsonify({'success': False, 'message': 'প্রয়োজনীয় তথ্য সম্পূর্ণ নয়'}), 400
    
    conn = get_db()
    try:
        conn.execute('''
            INSERT OR REPLACE INTO training_records 
            (worker_id, training_id, month, year, training_date, status, remarks)
            VALUES (?,?,?,?,?,?,?)
        ''', (data['worker_id'], data['training_id'], data['month'], data.get('year', datetime.now().year),
              data.get('training_date', datetime.now().strftime('%Y-%m-%d')),
              data.get('status', 'Completed'), data.get('remarks', '')))
        conn.commit()
        return jsonify({'success': True, 'message': 'ট্রেনিং রেকর্ড সংরক্ষিত হয়েছে'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    finally:
        conn.close()

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
@api_login_required
def delete_record(record_id):
    conn = get_db()
    conn.execute("DELETE FROM training_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'রেকর্ড মুছা হয়েছে'})

@app.route('/api/dashboard', methods=['GET'])
@api_login_required
def dashboard():
    year = request.args.get('year', datetime.now().year)
    conn = get_db()
    total_workers = conn.execute("SELECT COUNT(*) FROM workers WHERE is_active=1").fetchone()[0]
    total_trainings = conn.execute("SELECT COUNT(*) FROM trainings WHERE is_active=1").fetchone()[0]
    total_records = conn.execute("SELECT COUNT(*) FROM training_records WHERE year=?", (year,)).fetchone()[0]
    monthly = conn.execute('''
        SELECT month, COUNT(*) as count FROM training_records
        WHERE year=? GROUP BY month ORDER BY month
    ''', (year,)).fetchall()
    conn.close()
    return jsonify({
        'total_workers': total_workers,
        'total_trainings': total_trainings,
        'total_records': total_records,
        'monthly': [dict(r) for r in monthly]
    })

# ── BULK TRAINING UPDATE ──
@app.route('/api/bulk-training/upload', methods=['POST'])
@api_login_required
def bulk_training_upload():
    """কার্ড নম্বর Excel আপলোড করুন এবং শ্রমিক খুঁজে বের করুন"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'ফাইল পাওয়া যায়নি'}), 400
    
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'শুধু Excel (.xlsx/.xls) ফাইল গ্রহণযোগ্য'}), 400

    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip().str.lower()
        
        # কার্ড নম্বর কলাম খুঁজুন
        card_col = None
        for col in df.columns:
            if 'card' in col or 'কার্ড' in col or 'id' in col:
                card_col = col
                break
        
        if not card_col:
            return jsonify({'success': False, 'message': 'Excel এ "Card Number" কলাম নেই'}), 400
        
        # কার্ড নম্বরগুলি সংগ্রহ করুন
        card_numbers = [str(c).strip().upper() for c in df[card_col].dropna()]
        
        if not card_numbers:
            return jsonify({'success': False, 'message': 'কোন কার্ড নম্বর পাওয়া যায়নি'}), 400
        
        # ডাটাবেসে শ্রমিক খুঁজুন
        conn = get_db()
        placeholders = ','.join('?' * len(card_numbers))
        workers = conn.execute(
            f"SELECT id, name, card_number, designation FROM workers WHERE is_active=1 AND UPPER(card_number) IN ({placeholders})",
            card_numbers
        ).fetchall()
        conn.close()
        
        found_workers = [dict(w) for w in workers]
        
        return jsonify({
            'success': True,
            'workers': found_workers,
            'total': len(card_numbers),
            'found': len(found_workers),
            'not_found': len(card_numbers) - len(found_workers)
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'ফাইল পড়তে সমস্যা: {str(e)}'}), 500


@app.route('/api/bulk-training/confirm', methods=['POST'])
@api_login_required
def bulk_training_confirm():
    """নির্বাচিত শ্রমিকদের জন্য ট্রেনিং রেকর্ড মার্ক করুন"""
    data = request.json
    worker_ids = data.get('worker_ids', [])
    training_id = data.get('training_id')
    month = data.get('month')
    year = data.get('year', datetime.now().year)
    training_date = data.get('training_date', datetime.now().strftime('%Y-%m-%d'))
    remarks = data.get('remarks', '')
    
    if not worker_ids or not training_id or not month:
        return jsonify({'success': False, 'message': 'প্রয়োজনীয় তথ্য সম্পূর্ণ নয়'}), 400
    
    try:
        conn = get_db()
        success_count = 0
        
        for worker_id in worker_ids:
            try:
                conn.execute('''
                    INSERT OR REPLACE INTO training_records 
                    (worker_id, training_id, month, year, training_date, status, remarks)
                    VALUES (?,?,?,?,?,?,?)
                ''', (worker_id, training_id, month, year, training_date, 'Completed', remarks))
                success_count += 1
            except Exception as e:
                print(f"Worker {worker_id} error: {str(e)}")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'{success_count} জন শ্রমিকের ট্রেনিং রেকর্ড সংরক্ষিত হয়েছে',
            'count': success_count
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'ত্রুটি: {str(e)}'}), 500


# Error handlers
@app.errorhandler(401)
def unauthorized(error):
    return redirect(url_for('login_page'))

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'পাওয়া যায়নি'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'success': False, 'message': 'সার্ভার ত্রুটি'}), 500


if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    init_db()
    print("\n" + "="*60)
    print("✅ Factory Training Management System চালু হচ্ছে...")
    print("="*60)
    print("🌐 Local:   http://localhost:5000")
    print("🌐 Network: http://0.0.0.0:5000")
    print("\n📝 Demo Login:")
    print("   ইউজারনেম: admin")
    print("   পাসওয়ার্ড: admin123")
    print("="*60 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
