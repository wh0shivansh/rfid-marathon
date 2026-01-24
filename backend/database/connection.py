"""
RFID Marathon Management System - Database Connection Manager
Security Level: Military-grade
Last Updated: January 21, 2026

This module manages PostgreSQL connections to Supabase with:
- SSL enforcement
- Connection pooling
- Fail-fast validation
- Automatic reconnection
"""

import logging
from typing import Generator
from contextlib import contextmanager
import os

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError, DatabaseError

from constants import (
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_POOL_TIMEOUT_SECONDS,
    DB_POOL_RECYCLE_SECONDS,
    DB_SSL_MODE,
    DB_CONNECTION_TIMEOUT_SECONDS,
    EnvVars,
    ErrorMessages,
)
from basefunctions import (
    get_env_variable,
    validate_required_env_vars,
    log_security_event,
    DatabaseError as AppDatabaseError,
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Singleton database connection manager with enterprise-grade features.
    Handles connection pooling, SSL enforcement, and fail-fast validation.
    """
    
    _instance = None
    _engine = None
    _session_factory = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one connection manager exists"""
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize database manager (called only once due to singleton)"""
        if self._engine is None:
            self._validate_configuration()
            self._create_engine()
            self._create_session_factory()
            self._test_connection()
    
    def _validate_configuration(self) -> None:
        """
        Validate all required environment variables are present.
        FAIL-FAST approach: if configuration is invalid, crash immediately.
        """
        required_vars = [
            EnvVars.DB_HOST,
            EnvVars.DB_PORT,
            EnvVars.DB_NAME,
            EnvVars.DB_USER,
            EnvVars.DB_PASSWORD,
        ]
        
        try:
            validate_required_env_vars(required_vars)
            logger.info("✓ Database configuration validated")
        except ValueError as e:
            logger.critical(f"✗ Database configuration validation failed: {e}")
            raise
    
    def _build_connection_string(self) -> str:
        """
        Build PostgreSQL connection string with SSL enforcement.
        
        Returns:
            str: PostgreSQL connection URL
        """
        host = get_env_variable(EnvVars.DB_HOST)
        port = get_env_variable(EnvVars.DB_PORT)
        dbname = get_env_variable(EnvVars.DB_NAME)
        user = get_env_variable(EnvVars.DB_USER)
        password = get_env_variable(EnvVars.DB_PASSWORD)
        
        # Build connection string with SSL enforcement
        connection_string = (
            f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
            f"?sslmode={DB_SSL_MODE}"
            f"&connect_timeout={DB_CONNECTION_TIMEOUT_SECONDS}"
        )
        
        # Log connection attempt (without password)
        safe_connection_string = (
            f"postgresql://{user}:****@{host}:{port}/{dbname}"
            f"?sslmode={DB_SSL_MODE}"
        )
        logger.info(f"Building connection to: {safe_connection_string}")
        
        return connection_string
    
    def _create_engine(self) -> None:
        """
        Create SQLAlchemy engine with connection pooling and SSL.
        """
        connection_string = self._build_connection_string()
        
        try:
            self._engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=DB_POOL_SIZE,
                max_overflow=DB_MAX_OVERFLOW,
                pool_timeout=DB_POOL_TIMEOUT_SECONDS,
                pool_recycle=DB_POOL_RECYCLE_SECONDS,
                pool_pre_ping=True,  # Verify connections before using
                echo=False,  # Set to True for SQL query logging
                future=True,  # Use SQLAlchemy 2.0 style
            )
            
            # Register connection event listeners
            self._register_event_listeners()
            
            logger.info("✓ Database engine created successfully")
            
        except Exception as e:
            logger.critical(f"✗ Failed to create database engine: {e}")
            raise AppDatabaseError(
                message=ErrorMessages.DB_CONNECTION_FAILED,
                details={"error": str(e)}
            )
    
    def _register_event_listeners(self) -> None:
        """
        Register SQLAlchemy event listeners for connection lifecycle.
        """
        @event.listens_for(self._engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """Called when a new database connection is established"""
            logger.debug("New database connection established")

            cursor = dbapi_connection.cursor()

            # Verify SSL is enabled
            cursor.execute("SHOW ssl;")
            ssl_status = cursor.fetchone()[0]

            cursor.close()

            if ssl_status != "on":
                log_security_event(
                    "SSL_NOT_ENABLED",
                    {"ssl_status": ssl_status},
                    level="CRITICAL"
                )
                raise AppDatabaseError(
                    message="SSL is not enabled on database connection",
                    details={"ssl_status": ssl_status}
                )
        
        @event.listens_for(self._engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Called when a connection is retrieved from the pool"""
            logger.debug("Connection checked out from pool")
        
        @event.listens_for(self._engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Called when a connection is returned to the pool"""
            logger.debug("Connection returned to pool")
    
    def _create_session_factory(self) -> None:
        """
        Create session factory for database operations.
        """
        self._session_factory = sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        
        logger.info("✓ Session factory created")
    
    def _test_connection(self) -> None:
        """
        Test database connection to ensure it's working.
        FAIL-FAST: if connection fails, crash immediately.
        """
        try:
            if self._engine is not None:
                with self._engine.connect() as connection:
                    result = connection.execute(text("SELECT 1"))
                    assert result.scalar() == 1
                
            logger.info("✓ Database connection test successful")
            
        except Exception as e:
            logger.critical(f"✗ Database connection test failed: {e}")
            log_security_event(
                "DB_CONNECTION_FAILED",
                {"error": str(e)},
                level="CRITICAL"
            )
            raise AppDatabaseError(
                message=ErrorMessages.DB_CONNECTION_FAILED,
                details={"error": str(e)}
            )
    
    def get_session(self) -> Session:
        """
        Get a new database session.
        
        Returns:
            Session: SQLAlchemy session
        """
        if self._session_factory is None:
            raise AppDatabaseError(
                message="Session factory not initialized",
                details={}
            )
        
        return self._session_factory()
    
    @contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Provide a transactional scope for database operations.
        Automatically commits on success, rolls back on failure.
        
        Yields:
            Session: Database session
            
        Example:
            with db_manager.session_scope() as session:
                session.add(new_record)
                # Automatically committed on exit
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
            logger.debug("Transaction committed successfully")
        except Exception as e:
            session.rollback()
            logger.error(f"Transaction rolled back due to error: {e}")
            raise
        finally:
            session.close()
            logger.debug("Session closed")
    
    def dispose(self) -> None:
        """
        Dispose of all connections in the pool.
        Used during shutdown or testing.
        """
        if self._engine:
            self._engine.dispose()
            logger.info("✓ Database connections disposed")
    
    def get_engine(self):
        """
        Get the SQLAlchemy engine instance.
        
        Returns:
            Engine: SQLAlchemy engine
        """
        return self._engine


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

# Global database manager instance
_db_manager = None


def get_database_manager() -> DatabaseManager:
    """
    Get the global database manager instance.
    
    Returns:
        DatabaseManager: Singleton database manager
    """
    global _db_manager
    
    if _db_manager is None:
        _db_manager = DatabaseManager()
    
    return _db_manager


def get_admin_credentials() -> dict:
    """
    Read admin credentials from environment variables and return them.

    Environment variables read:
      - ADMIN_USERNAME (defaults to 'admin')
      - ADMIN_PASSWORD (defaults to 'AdminPassword123!')
      - ADMIN_EMAIL (defaults to 'admin@rfid-marathon.local')

    Returns:
        dict: {"username": str, "password": str, "email": str}
    """
    return {
        "username": os.getenv("ADMIN_USERNAME", "admin"),
        "password": os.getenv("ADMIN_PASSWORD", "AdminPassword123!"),
        "email": os.getenv("ADMIN_EMAIL", "admin@rfid-marathon.local"),
    }


def get_db_session() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to provide database sessions.
    
    Yields:
        Session: Database session
        
    Example:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db_session)):
            return db.query(Item).all()
    """
    db_manager = get_database_manager()
    session = db_manager.get_session()
    
    try:
        yield session
    finally:
        session.close()


def initialize_database() -> None:
    """
    Initialize database connection on application startup.
    Called by main.py during app initialization.
    """
    logger.info("Initializing database connection...")
    db_manager = get_database_manager()
    logger.info("✓ Database initialized successfully")


def shutdown_database() -> None:
    """
    Shutdown database connections on application shutdown.
    Called by main.py during app shutdown.
    """
    logger.info("Shutting down database connections...")
    db_manager = get_database_manager()
    db_manager.dispose()
    logger.info("✓ Database shutdown complete")
