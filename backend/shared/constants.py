"""
Shared constants for RFID Marathon System
"""
import os
from dotenv import load_dotenv
load_dotenv()

# Database Configuration
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_SSL_MODE = os.environ.get("DB_SSL_MODE", "prefer")
DB_CONNECTION_TIMEOUT_SECONDS = int(os.environ.get("DB_CONNECTION_TIMEOUT_SECONDS", 5))

# Admin Credentials
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "Admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123456")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@rfid-marathon.local")

# Security Keys
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
FERNET_MASTER_KEY = os.environ.get("FERNET_MASTER_KEY", "")
RSA_PRIVATE_KEY_PATH = os.environ.get("RSA_PRIVATE_KEY_PATH", "keys/rsa_private.pem")
RSA_PUBLIC_KEY_PATH = os.environ.get("RSA_PUBLIC_KEY_PATH", "keys/rsa_public.pem")

# RFID Hub Authentication
RFID_START_HUB_SECRET = os.environ.get("RFID_START_HUB_SECRET", "")
RFID_END_HUB_SECRET = os.environ.get("RFID_END_HUB_SECRET", "")

# RFID Reader Configuration
RFID_START_READER_NAMES = os.environ.get("RFID_START_READER_NAMES", "Reader 1")
RFID_END_READER_NAMES = os.environ.get("RFID_END_READER_NAMES", "Reader 2")
RFID_GRACE_PERIOD_SECONDS = int(os.environ.get("RFID_GRACE_PERIOD_SECONDS", 20))
RFID_MIN_READ_COUNT_TO_LOCK = int(os.environ.get("RFID_MIN_READ_COUNT_TO_LOCK", 3))
RFID_NO_HIT_TIMEOUT_SECONDS = int(os.environ.get("RFID_NO_HIT_TIMEOUT_SECONDS", 20))

# Race States
RACE_STATE_IDLE = "idle"
RACE_STATE_STARTED = "started"

# Racer States
RACER_STATE_GRACE = "grace"
RACER_STATE_RUNNING = "running"
RACER_STATE_FINISHED = "finished"

# Time Configuration
START_TIME_CORRECTION_THRESHOLD = 10  # seconds

# Server Configuration
SERVER_HOST = os.environ.get("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8000))
SERVER_ENV = os.environ.get("SERVER_ENV", "production")

# Server Ports
START_LINE_BACKEND_PORT = 8000
END_LINE_BACKEND_PORT = 8002
REGISTRATION_BACKEND_PORT = 8003
START_LINE_PROXY_PORT = 9090
END_LINE_PROXY_PORT = 9090

# Logging Configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE_PATH = os.environ.get("LOG_FILE_PATH", "logs/app.log")

# SSL/TLS Configuration
SSL_CERT_PATH = os.environ.get("SSL_CERT_PATH", "")
SSL_KEY_PATH = os.environ.get("SSL_KEY_PATH", "")
