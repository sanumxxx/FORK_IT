import os
from datetime import timedelta


class Config:


    ADMIN_USERNAME = 'admin'
    ADMIN_EMAIL = 'admin@example.com'
    ADMIN_PASSWORD = 'admin123'
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///sports_calendar.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Notification settings
    NOTIFICATION_EXPIRE_TIME = timedelta(days=7)

    # PDF upload settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'pdf'}
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size

    # Cache settings
    CACHE_TYPE = "simple"
    CACHE_DEFAULT_TIMEOUT = 300