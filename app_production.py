"""
Production-Ready Flask Application
Enhanced with error handling, logging, validation, and security
"""
from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
import os
from datetime import datetime
from config import get_config
from logger import setup_logging, log_error, log_info
from validators import Validator, ValidationError
from db_manager import DatabaseManager

# Initialize app with config
app = Flask(__name__)
config = get_config()
app.config.from_object(config)

# Setup logging
setup_logging(app)

# Initialize database manager
db_manager = DatabaseManager(app.config['DB_PATH'])

# Bengali months mapping
MONTHS_BN = {
    1: 'জানুয়ারি', 2: 'ফেব্রুয়ারি', 3: 'মার্চ', 4: 'এপ্রিল',
    5: 'মে', 6: 'জুন', 7: 'জুলাই', 8: 'আগস্ট',
    9: 'সেপ্টেম্বর', 10: 'অক্টোবর', 11: 'নভেম্বর', 12: 'ডিসেম্বর'
}

def init_db():
    """Initialize database with schema"""
    try:
        schema = '''
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

            CREATE INDEX IF NOT EXISTS idx_workers_active ON workers(is_active);
            CREATE INDEX IF NOT EXISTS idx_trainings_active ON trainings(is_active);
            CREATE INDEX IF NOT EXISTS idx_records_worker ON training_records(worker_id);
            CREATE INDEX IF NOT EXISTS idx_records_training ON training_records(training_id);
        '''
        
        db_manager.execute_script(schema)
        
        # Add default trainings
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
        
        for name, desc in default_trainings:
            try:
                db_manager.execute_update(
                    "INSERT OR IGNORE INTO trainings (name, description) VALUES (?, ?)",
                    (name, desc)
                )
            except:
                pass
        
        log_info(app, "Database initialized successfully")
    except Exception as e:
        log_error(app, e, "Database initialization")
        raise

# Error handlers
@app.errorhandler(400)
def bad_request(error):
    return jsonify({'success': False, 'message': 'Invalid request'}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({'success': False, 'message': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    log_error(app, error, "Internal server error")
    return jsonify({'success': False, 'message': 'Internal server error'}), 500

# ─── ROUTES ───────────────────────────────────────────────

@app.route('/')
def index():
    """Serve main page"""
    try:
        return render_template('index.html', months=MONTHS_BN)
    except Exception as e:
        log_error(app, e, "Index route")
        return jsonify({'success': False, 'message': 'Failed to load page'}), 500

# ── Workers API ──

@app.route('/api/workers', methods=['GET'])
def get_workers():
    """Get all active workers"""
    try:
        search = Validator.validate_search_query(request.args.get('search', ''))
        
        if search:
            query = '''
                SELECT * FROM workers 
                WHERE is_active=1 AND (
                    name LIKE ? OR card_number LIKE ? OR 
                    designation LIKE ? OR phone_number LIKE ?
                )
                ORDER BY name
            '''
            search_param = f'%{search}%'
            rows = db_manager.execute_query(query, (search_param, search_param, search_param, search_param))
        else:
            rows = db_manager.execute_query(
                "SELECT * FROM workers WHERE is_active=1 ORDER BY name"
            )
        
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log_error(app, e, "Get workers")
        return jsonify({'success': False, 'message': 'Failed to fetch workers'}), 500

@app.route('/api/workers/<int:worker_id>', methods=['GET'])
def get_worker(worker_id):
    """Get single worker"""
    try:
        worker = db_manager.execute_one(
            "SELECT * FROM workers WHERE id=?", (worker_id,)
        )
        
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404
        
        return jsonify(dict(worker))
    except Exception as e:
        log_error(app, e, f"Get worker {worker_id}")
        return jsonify({'success': False, 'message': 'Failed to fetch worker'}), 500

@app.route('/api/workers', methods=['POST'])
def add_worker():
    """Add new worker"""
    try:
        data = request.json
        Validator.validate_worker_data(data)
        
        db_manager.execute_update(
            '''INSERT INTO workers 
               (name, designation, card_number, department, line_number, phone_number, join_date) 
               VALUES (?,?,?,?,?,?,?)''',
            (
                data['name'].strip(),
                data.get('designation', '').strip(),
                data['card_number'].strip(),
                data.get('department', '').strip(),
                data.get('line_number', '').strip(),
                data.get('phone_number', '').strip(),
                data.get('join_date', datetime.now().strftime('%Y-%m-%d'))
            )
        )
        
        log_info(app, f"New worker added: {data['name']}")
        return jsonify({'success': True, 'message': 'শ্রমিক যোগ করা হয়েছে'})
    
    except ValidationError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'এই কার্ড নম্বর আগেই আছে'}), 400
    except Exception as e:
        log_error(app, e, "Add worker")
        return jsonify({'success': False, 'message': 'Failed to add worker'}), 500

@app.route('/api/workers/<int:worker_id>', methods=['PUT'])
def update_worker(worker_id):
    """Update worker"""
    try:
        data = request.json
        Validator.validate_worker_data(data)
        
        db_manager.execute_update(
            '''UPDATE workers 
               SET name=?, designation=?, department=?, line_number=?, phone_number=?, join_date=? 
               WHERE id=?''',
            (
                data['name'].strip(),
                data.get('designation', '').strip(),
                data.get('department', '').strip(),
                data.get('line_number', '').strip(),
                data.get('phone_number', '').strip(),
                data.get('join_date', ''),
                worker_id
            )
        )
        
        log_info(app, f"Worker updated: {worker_id}")
        return jsonify({'success': True, 'message': 'তথ্য আপডেট হয়েছে'})
    
    except ValidationError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        log_error(app, e, f"Update worker {worker_id}")
        return jsonify({'success': False, 'message': 'Failed to update worker'}), 500

@app.route('/api/workers/<int:worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    """Soft delete worker"""
    try:
        db_manager.execute_update(
            "UPDATE workers SET is_active=0 WHERE id=?", (worker_id,)
        )
        log_info(app, f"Worker deleted: {worker_id}")
        return jsonify({'success': True, 'message': 'শ্রমিক সরানো হয়েছে'})
    except Exception as e:
        log_error(app, e, f"Delete worker {worker_id}")
        return jsonify({'success': False, 'message': 'Failed to delete worker'}), 500

# ── Trainings API ──

@app.route('/api/trainings', methods=['GET'])
def get_trainings():
    """Get all active trainings"""
    try:
        rows = db_manager.execute_query(
            "SELECT * FROM trainings WHERE is_active=1 ORDER BY name"
        )
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log_error(app, e, "Get trainings")
        return jsonify({'success': False, 'message': 'Failed to fetch trainings'}), 500

@app.route('/api/trainings', methods=['POST'])
def add_training():
    """Add new training"""
    try:
        data = request.json
        Validator.validate_training_data(data)
        
        db_manager.execute_update(
            "INSERT INTO trainings (name, description) VALUES (?,?)",
            (data['name'].strip(), data.get('description', '').strip())
        )
        
        log_info(app, f"New training added: {data['name']}")
        return jsonify({'success': True, 'message': 'ট্রেনিং যোগ করা হয়েছে'})
    
    except ValidationError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'এই ট্রেনিং আগেই আছে'}), 400
    except Exception as e:
        log_error(app, e, "Add training")
        return jsonify({'success': False, 'message': 'Failed to add training'}), 500

@app.route('/api/trainings/<int:training_id>', methods=['DELETE'])
def delete_training(training_id):
    """Soft delete training"""
    try:
        db_manager.execute_update(
            "UPDATE trainings SET is_active=0 WHERE id=?", (training_id,)
        )
        log_info(app, f"Training deleted: {training_id}")
        return jsonify({'success': True, 'message': 'ট্রেনিং সরানো হয়েছে'})
    except Exception as e:
        log_error(app, e, f"Delete training {training_id}")
        return jsonify({'success': False, 'message': 'Failed to delete training'}), 500

# ── Training Records API ──

@app.route('/api/records', methods=['GET'])
def get_records():
    """Get training records with filters"""
    try:
        worker_id = request.args.get('worker_id')
        month = request.args.get('month')
        year = request.args.get('year', datetime.now().year)
        
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
        
        query += " AND tr.year=? ORDER BY tr.year, tr.month, w.name"
        params.append(year)
        
        rows = db_manager.execute_query(query, params)
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log_error(app, e, "Get records")
        return jsonify({'success': False, 'message': 'Failed to fetch records'}), 500

@app.route('/api/records', methods=['POST'])
def add_record():
    """Add training record"""
    try:
        data = request.json
        Validator.validate_record_data(data)
        
        db_manager.execute_update(
            '''INSERT OR REPLACE INTO training_records 
               (worker_id, training_id, month, year, training_date, status, remarks)
               VALUES (?,?,?,?,?,?,?)''',
            (
                int(data['worker_id']),
                int(data['training_id']),
                int(data['month']),
                int(data.get('year', datetime.now().year)),
                data.get('training_date', datetime.now().strftime('%Y-%m-%d')),
                data.get('status', 'Completed'),
                data.get('remarks', '')
            )
        )
        
        log_info(app, f"Training record added for worker {data['worker_id']}")
        return jsonify({'success': True, 'message': 'ট্রেনিং রেকর্ড সংরক্ষিত হয়েছে'})
    
    except ValidationError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        log_error(app, e, "Add record")
        return jsonify({'success': False, 'message': 'Failed to add record'}), 500

@app.route('/api/records/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    """Delete training record"""
    try:
        db_manager.execute_update(
            "DELETE FROM training_records WHERE id=?", (record_id,)
        )
        log_info(app, f"Record deleted: {record_id}")
        return jsonify({'success': True, 'message': 'রেকর্ড মুছা হয়েছে'})
    except Exception as e:
        log_error(app, e, f"Delete record {record_id}")
        return jsonify({'success': False, 'message': 'Failed to delete record'}), 500

# ── Dashboard API ──

@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    """Get dashboard statistics"""
    try:
        year = request.args.get('year', datetime.now().year)
        
        total_workers = db_manager.execute_one(
            "SELECT COUNT(*) as count FROM workers WHERE is_active=1"
        )
        
        total_trainings = db_manager.execute_one(
            "SELECT COUNT(*) as count FROM trainings WHERE is_active=1"
        )
        
        total_records = db_manager.execute_one(
            "SELECT COUNT(*) as count FROM training_records WHERE year=?", (year,)
        )
        
        monthly = db_manager.execute_query(
            '''SELECT month, COUNT(*) as count FROM training_records
               WHERE year=? GROUP BY month ORDER BY month''',
            (year,)
        )
        
        return jsonify({
            'total_workers': total_workers['count'] if total_workers else 0,
            'total_trainings': total_trainings['count'] if total_trainings else 0,
            'total_records': total_records['count'] if total_records else 0,
            'monthly': [dict(r) for r in monthly]
        })
    except Exception as e:
        log_error(app, e, "Dashboard")
        return jsonify({'success': False, 'message': 'Failed to fetch dashboard data'}), 500

# ── File Upload API ──

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/api/workers/upload', methods=['POST'])
def upload_workers():
    """Bulk upload workers from Excel"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'ফাইল পাওয়া যায়নি'}), 400
        
        file = request.files['file']
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'message': 'শুধু Excel (.xlsx/.xls) ফাইল গ্রহণযোগ্য'}), 400
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], Validator.sanitize_filename(file.filename))
        file.save(filepath)
        
        try:
            df = pd.read_excel(filepath)
            df.columns = df.columns.str.strip().str.lower()
            
            # Column mapping
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
                elif 'join' in col or 'যোগদান' in col:
                    col_map['join_date'] = col
            
            if 'name' not in col_map or 'card_number' not in col_map:
                return jsonify({
                    'success': False,
                    'message': 'Excel এ "Name" ও "Card Number" কলাম থাকতে হবে'
                }), 400
            
            added, skipped = 0, 0
            for _, row in df.iterrows():
                try:
                    raw_join_date = str(row.get(col_map.get('join_date'), '')).strip() if col_map.get('join_date') else ''
                    join_date = datetime.now().strftime('%Y-%m-%d')
                    
                    if raw_join_date and raw_join_date.lower() != 'nan':
                        try:
                            join_date = raw_join_date.split(' ')[0]
                        except:
                            pass
                    
                    def get_val(key):
                        val = str(row.get(col_map.get(key), '')).strip() if col_map.get(key) else ''
                        return '' if val.lower() == 'nan' else val
                    
                    result = db_manager.execute_update(
                        '''INSERT OR IGNORE INTO workers 
                           (name, designation, card_number, department, line_number, phone_number, join_date)
                           VALUES (?,?,?,?,?,?,?)''',
                        (
                            get_val('name'),
                            get_val('designation'),
                            get_val('card_number'),
                            get_val('department'),
                            get_val('line_number'),
                            get_val('phone_number'),
                            join_date
                        )
                    )
                    
                    if result > 0:
                        added += 1
                    else:
                        skipped += 1
                except Exception as row_error:
                    log_error(app, row_error, f"Processing row in upload")
                    skipped += 1
            
            log_info(app, f"Workers uploaded: {added} added, {skipped} skipped")
            return jsonify({
                'success': True,
                'message': f'{added} জন নতুন শ্রমিক যোগ হয়েছে, {skipped} জন আগেই আছে'
            })
        
        finally:
            # Clean up uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)
    
    except Exception as e:
        log_error(app, e, "Upload workers")
        return jsonify({'success': False, 'message': f'ফাইল পড়তে সমস্যা: {str(e)}'}), 500

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('logs', exist_ok=True)
    
    try:
        init_db()
        print("\n✅ Factory Training Management System চালু হচ্ছে...")
        print(f"🌐 Environment: {os.getenv('FLASK_ENV', 'development')}")
        print("📱 Local: http://localhost:5000")
        print("⚠️  Debug Mode:", app.debug)
        print()
        
        # In production, use a proper WSGI server like gunicorn
        app.run(debug=app.debug, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"❌ Failed to start application: {str(e)}")
        exit(1)
