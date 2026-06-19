"""
Database Manager with Better Error Handling
"""
import sqlite3
import os
from contextlib import contextmanager
from logger import log_error, log_info

class DatabaseManager:
    """Database operations manager"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Ensure database file exists"""
        if not os.path.exists(self.db_path):
            conn = sqlite3.connect(self.db_path)
            conn.close()
    
    @contextmanager
    def get_connection(self):
        """Get database connection with proper cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def execute_query(self, query, params=None):
        """Execute SELECT query safely"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.fetchall()
        except sqlite3.Error as e:
            raise Exception(f"Database query failed: {str(e)}")
    
    def execute_one(self, query, params=None):
        """Execute SELECT query and return one result"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.fetchone()
        except sqlite3.Error as e:
            raise Exception(f"Database query failed: {str(e)}")
    
    def execute_update(self, query, params=None):
        """Execute INSERT/UPDATE/DELETE query"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            raise Exception(f"Database update failed: {str(e)}")
    
    def execute_script(self, script):
        """Execute multiple SQL statements"""
        try:
            with self.get_connection() as conn:
                conn.executescript(script)
                conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Database script execution failed: {str(e)}")
