"""
Database connection and utilities
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional
import os

from .constants import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


class DatabaseConnection:
    """Manages database connections"""
    
    def __init__(self):
        self.host = os.getenv("DB_HOST", DB_HOST)
        self.port = os.getenv("DB_PORT", DB_PORT)
        self.dbname = os.getenv("DB_NAME", DB_NAME)
        self.user = os.getenv("DB_USER", DB_USER)
        self.password = os.getenv("DB_PASSWORD", DB_PASSWORD)
    
    @contextmanager
    def get_connection(self):
        """Get a database connection context manager"""
        conn = psycopg2.connect(
            host=self.host,
            port=self.port,
            dbname=self.dbname,
            user=self.user,
            password=self.password
        )
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    @contextmanager
    def get_cursor(self, cursor_factory=RealDictCursor):
        """Get a cursor context manager"""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
            finally:
                cursor.close()


# Global database instance
db = DatabaseConnection()
