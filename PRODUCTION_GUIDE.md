# Production Deployment Guide

## 🚀 কী করার আছে Production এ যাওয়ার আগে:

### 1. **Environment Setup**
```bash
# Install dependencies
pip install -r requirements_production.txt

# Create .env file
cp .env.example .env

# Edit .env with your values
nano .env
```

### 2. **Security Checklist**
- [ ] Set strong `SECRET_KEY` in `.env`
- [ ] Set `FLASK_ENV=production`
- [ ] Enable `SESSION_COOKIE_SECURE=True` (HTTPS only)
- [ ] Disable `DEBUG=False`
- [ ] Use HTTPS certificate

### 3. **Database Migration (SQLite → PostgreSQL)**

SQLite Production-এ limited। PostgreSQL ব্যবহার করুন:

```python
# Install PostgreSQL adapter
pip install psycopg2-binary

# Update config.py
SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
```

### 4. **Run with Gunicorn**

```bash
# Development (testing)
python app_production.py

# Production (use gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 app_production:app

# With configuration
gunicorn \
  --workers 4 \
  --worker-class sync \
  --bind 0.0.0.0:5000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log \
  app_production:app
```

### 5. **Nginx Configuration**

```nginx
upstream factory_app {
    server 127.0.0.1:5000;
}

server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    # SSL certificates
    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css text/xml text/javascript 
               application/x-javascript application/xml+rss 
               application/javascript application/json;
    
    # Proxy settings
    location / {
        proxy_pass http://factory_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
    
    # Static files caching
    location /static {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 6. **Systemd Service (Ubuntu/Debian)**

Create `/etc/systemd/system/factory-app.service`:

```ini
[Unit]
Description=Factory Training Management System
After=network.target

[Service]
Type=notify
User=www-data
WorkingDirectory=/path/to/app
Environment="FLASK_ENV=production"
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/path/to/app/.env
ExecStart=/usr/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --bind 127.0.0.1:5000 \
    --timeout 120 \
    app_production:app

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable factory-app
sudo systemctl start factory-app
sudo systemctl status factory-app
```

### 7. **Monitoring & Logging**

```bash
# View logs
sudo journalctl -u factory-app -f

# Monitor processes
systemctl status factory-app

# Check disk space
df -h /path/to/app
```

### 8. **Backup Strategy**

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/factory-app"
DB_PATH="/path/to/training.db"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cp $DB_PATH $BACKUP_DIR/training_$DATE.db
gzip $BACKUP_DIR/training_$DATE.db

# Keep last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

## ⚠️ Common Issues:

| সমস্যা | সমাধান |
|--------|--------|
| `SECRET_KEY not set` | `.env` ফাইল এ `SECRET_KEY` যোগ করুন |
| `Port 5000 already in use` | `lsof -i :5000` করে অন্য প্রসেস বন্ধ করুন |
| `Database locked` | SQLite এর পরিবর্তে PostgreSQL ব্যবহার করুন |
| `404 on /api/workers` | Nginx config চেক করুন, proxy pass সঠিক আছে কি? |

## 📊 Performance Tips:

1. **Enable Caching**
   - Redis setup করুন
   - Query results cache করুন

2. **Database Optimization**
   - Indexes যোগ করুন (ইতিমধ্যে যোগ করা আছে)
   - Regular maintenance: `VACUUM`

3. **Load Balancing**
   - Multiple Gunicorn workers (4-8)
   - Nginx load balancing

4. **Monitoring**
   - Application metrics track করুন
   - Error rates monitor করুন
   - Response time track করুন

## 🔒 Security Hardening:

1. Firewall সেটআপ করুন
2. SSH keys configure করুন (password login disable)
3. Regular security updates
4. SQL injection থেকে সুরক্ষিত (parameterized queries - ✅ Done)
5. Rate limiting add করুন

---

**কোনো প্রশ্ন থাকলে GitHub issues এ খুলুন!**
