"""
Database initialization script
Run this to set up the database schema
"""
import sys
import os

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import Race, db
from shared.constants import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def init_database():
    """Initialize database tables"""
    try:
        print("🔧 Initializing RFID Marathon Database...")
        print(f"📍 Host: {DB_HOST}:{DB_PORT}")
        print(f"📊 Database: {DB_NAME}")
        
        # Create races table
        print("\n📋 Creating races table...")
        Race.create_table()
        print("✓ Races table created successfully")
        
        print("\n✅ Database initialization complete!")
        print("\nNote: Per-race entry tables will be created automatically when races are created.")
        
    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        return False
    
    return True


if __name__ == '__main__':
    success = init_database()
    sys.exit(0 if success else 1)
