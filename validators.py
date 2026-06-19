"""
Input Validators and Sanitizers
"""
import re
from datetime import datetime

class ValidationError(Exception):
    """Custom validation error"""
    pass

class Validator:
    """Input validation utilities"""
    
    @staticmethod
    def validate_worker_data(data):
        """Validate worker input data"""
        if not data:
            raise ValidationError("Worker data is required")
        
        # Required fields
        if not data.get('name', '').strip():
            raise ValidationError("Worker name is required")
        
        if not data.get('card_number', '').strip():
            raise ValidationError("Card number is required")
        
        # Validate name (alphanumeric + spaces, bengali chars allowed)
        name = data['name'].strip()
        if len(name) < 2 or len(name) > 100:
            raise ValidationError("Worker name must be between 2-100 characters")
        
        # Validate card number
        card = data['card_number'].strip()
        if len(card) < 2 or len(card) > 50:
            raise ValidationError("Card number must be between 2-50 characters")
        
        # Optional fields
        if data.get('phone_number'):
            phone = data['phone_number'].strip()
            if phone and not re.match(r'^[\d\s+\-()]*$', phone):
                raise ValidationError("Invalid phone number format")
        
        if data.get('join_date'):
            try:
                datetime.strptime(data['join_date'], '%Y-%m-%d')
            except ValueError:
                raise ValidationError("Invalid date format (use YYYY-MM-DD)")
        
        return True
    
    @staticmethod
    def validate_training_data(data):
        """Validate training input data"""
        if not data:
            raise ValidationError("Training data is required")
        
        if not data.get('name', '').strip():
            raise ValidationError("Training name is required")
        
        name = data['name'].strip()
        if len(name) < 2 or len(name) > 100:
            raise ValidationError("Training name must be between 2-100 characters")
        
        return True
    
    @staticmethod
    def validate_record_data(data):
        """Validate training record data"""
        if not data:
            raise ValidationError("Record data is required")
        
        # Required fields
        if not data.get('worker_id'):
            raise ValidationError("Worker ID is required")
        
        if not data.get('training_id'):
            raise ValidationError("Training ID is required")
        
        if not data.get('month'):
            raise ValidationError("Month is required")
        
        # Validate month (1-12)
        try:
            month = int(data['month'])
            if month < 1 or month > 12:
                raise ValidationError("Month must be between 1-12")
        except (ValueError, TypeError):
            raise ValidationError("Invalid month value")
        
        # Validate year
        try:
            year = int(data.get('year', datetime.now().year))
            if year < 2000 or year > 2099:
                raise ValidationError("Year must be between 2000-2099")
        except (ValueError, TypeError):
            raise ValidationError("Invalid year value")
        
        return True
    
    @staticmethod
    def validate_search_query(query):
        """Validate search query"""
        if not query:
            return ""
        
        # Limit search query length
        query = query.strip()
        if len(query) > 100:
            raise ValidationError("Search query too long (max 100 characters)")
        
        # Remove potentially dangerous characters (though parameterized queries protect us)
        query = re.sub(r'[;\'"]', '', query)
        return query
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize uploaded filename"""
        # Keep only alphanumeric, dash, underscore, dot
        filename = re.sub(r'[^\w\s\-.]', '', filename)
        filename = re.sub(r'[\s]+', '_', filename)
        return filename[:100]  # Limit length
