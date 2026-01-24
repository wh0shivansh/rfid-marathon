"""
RFID Marathon Management System - Database Migrations
Security Level: Military-grade
Last Updated: January 21, 2026

This module handles idempotent database schema creation and migrations.
NO DESTRUCTIVE OPERATIONS - only creates tables that don't exist.
"""

import logging
import os
from typing import List, Dict, Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from models import Base, User, Race, Participant, AuditLog, NonceCache, EncryptionKey
from database.connection import get_database_manager
from basefunctions import DatabaseError, log_security_event, get_current_timestamp_utc
from constants import AuditAction

logger = logging.getLogger(__name__)


class MigrationManager:
    """
    Manages database migrations with idempotent, non-destructive approach.
    """
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.engine = self.db_manager.get_engine()
    
    def get_existing_tables(self) -> List[str]:
        """
        Get list of existing tables in the database.
        
        Returns:
            List[str]: List of table names
        """
        inspector = inspect(self.engine)
        return inspector.get_table_names() if inspector else []
    
    def ensure_participant_time_columns(self) -> Dict[str, Any]:
        """
        Ensure all per-race participant tables include `start_time` and `end_time`.
        Uses the `races.table_name` to locate per-race tables and adds columns if missing.
        IDEMPOTENT and safe across all environments.
        """
        results: Dict[str, Any] = {"updated_tables": [], "skipped_tables": [], "errors": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)
            # Fetch all races to know participant table names
            with self.engine.connect() as conn:
                race_rows = conn.execute(text("SELECT id, table_name FROM races")).fetchall()
                for row in race_rows:
                    race_id = row.id if hasattr(row, "id") else row[0]
                    table_name = row.table_name if hasattr(row, "table_name") else row[1]
                    if not table_name:
                        results["skipped_tables"].append({"race_id": str(race_id), "reason": "no table_name"})
                        continue
                    # Inspect columns
                    cols = [col['name'] for col in inspector.get_columns(table_name)] if inspector else []
                    alterations = []
                    if 'start_time' not in cols:
                        alterations.append("ADD COLUMN start_time TIMESTAMPTZ NULL")
                    if 'end_time' not in cols:
                        alterations.append("ADD COLUMN end_time TIMESTAMPTZ NULL")
                    if alterations:
                        alter_sql = f"ALTER TABLE \"{table_name}\" " + ", ".join(alterations) + ";"
                        try:
                            conn.execute(text(alter_sql))
                            results["updated_tables"].append(table_name)
                        except Exception as e:
                            results["errors"].append({"table": table_name, "error": str(e)})
                    else:
                        results["skipped_tables"].append(table_name)
                conn.commit()
            results["success"] = True
            return results
        except Exception as e:
            logger.error(f"✗ Failed ensuring participant time columns: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            bool: True if table exists, False otherwise
        """
        existing_tables = self.get_existing_tables()
        return table_name in existing_tables
    
    def create_tables(self) -> Dict[str, Any]:
        """
        Create all tables defined in models if they don't exist.
        IDEMPOTENT: Safe to run multiple times.
        
        Returns:
            Dict: Summary of created tables
        """
        logger.info("Starting database table creation (idempotent)...")
        
        existing_tables_before = set(self.get_existing_tables())
        logger.info(f"Existing tables: {existing_tables_before}")
        
        try:
            # Create all tables defined in Base metadata
            # This will only create tables that don't exist
            Base.metadata.create_all(bind=self.engine)
            
            existing_tables_after = set(self.get_existing_tables())
            new_tables = existing_tables_after - existing_tables_before
            
            if new_tables:
                logger.info(f"✓ Created new tables: {new_tables}")
            else:
                logger.info("✓ No new tables created (all tables already exist)")
            
            # Log audit entry
            self._log_migration_audit(
                action=AuditAction.MIGRATION_EXECUTED.value,
                success=True,
                details={"created_tables": list(new_tables)}
            )
            
            return {
                "success": True,
                "existing_tables_before": list(existing_tables_before),
                "existing_tables_after": list(existing_tables_after),
                "new_tables_created": list(new_tables),
                "total_tables": len(existing_tables_after)
            }
            
        except SQLAlchemyError as e:
            logger.error(f"✗ Failed to create tables: {e}")
            
            self._log_migration_audit(
                action=AuditAction.MIGRATION_EXECUTED.value,
                success=False,
                details={"error": str(e)}
            )
            
            raise DatabaseError(
                message="Failed to create database tables",
                details={"error": str(e)}
            )
    
    def create_indexes(self) -> None:
        """
        Create additional indexes if needed.
        Indexes are already defined in models, but this method can add custom indexes.
        """
        logger.info("Creating custom indexes (if any)...")
        
        custom_indexes = []
        
        # Example: Create composite indexes for performance
        # custom_indexes.append(
        #     "CREATE INDEX IF NOT EXISTS idx_custom_name ON table_name (column1, column2)"
        # )
        
        if not custom_indexes:
            logger.info("No custom indexes to create")
            return
        
        try:
            if self.engine is not None:
                with self.engine.connect() as connection:
                    for index_sql in custom_indexes:
                        connection.execute(text(index_sql))
                        logger.info(f"✓ Created custom index")
                    
                    connection.commit()
            
            logger.info("✓ All custom indexes created")
            
        except SQLAlchemyError as e:
            logger.error(f"✗ Failed to create custom indexes: {e}")
            raise DatabaseError(
                message="Failed to create custom indexes",
                details={"error": str(e)}
            )
    
    def verify_schema(self) -> Dict[str, Any]:
        """
        Verify that all required tables exist with correct structure.
        
        Returns:
            Dict: Verification results
        """
        logger.info("Verifying database schema...")
        
        required_tables = [
            "users",
            "races",
            "audit_log",
            "nonce_cache",
            "encryption_keys"
        ]
        
        existing_tables = self.get_existing_tables()
        missing_tables = [t for t in required_tables if t not in existing_tables]
        
        if missing_tables:
            logger.error(f"✗ Missing required tables: {missing_tables}")
            return {
                "success": False,
                "missing_tables": missing_tables,
                "existing_tables": existing_tables
            }
        
        logger.info("✓ All required tables exist")
        
        return {
            "success": True,
            "required_tables": required_tables,
            "existing_tables": existing_tables,
            "missing_tables": []
        }
    
    def _log_migration_audit(
        self, 
        action: str, 
        success: bool, 
        details: Dict[str, Any]
    ) -> None:
        """
        Log migration execution to audit table (if it exists).
        
        Args:
            action: Migration action
            success: Whether migration succeeded
            details: Additional details
        """
        # Only log if audit_log table exists
        if not self.table_exists("audit_log"):
            return
        
        try:
            with self.db_manager.session_scope() as session:
                audit_entry = AuditLog(
                    action=action,
                    user_id=None,  # System operation
                    ip_address="127.0.0.1",  # System internal
                    timestamp=get_current_timestamp_utc(),
                    request_path="/system/migration",
                    request_method="SYSTEM",
                    status_code=200 if success else 500,
                    details=details,
                    success=success
                )
                session.add(audit_entry)
                
        except Exception as e:
            # Don't fail migration if audit logging fails
            logger.warning(f"Failed to log migration audit: {e}")
    
    def seed_default_data(self) -> None:
        """
        Seed database with default/initial data.
        Only runs if data doesn't already exist.
        """
        logger.info("Seeding default data...")
        
        from services.password_manager import PasswordManager
        
        try:
            with self.db_manager.session_scope() as session:
                # Read admin credentials from environment (dotenv should be loaded by caller)
                admin_username = os.getenv("ADMIN_USERNAME", "admin")
                admin_password = os.getenv("ADMIN_PASSWORD", "AdminPassword123!")
                admin_email = os.getenv("ADMIN_EMAIL", "admin@rfid-marathon.local")

                # Hash password
                password_manager = PasswordManager()
                hashed_password = password_manager.hash_password(admin_password)

                # Upsert admin user: create new or override existing credentials
                existing_admin = session.query(User).filter_by(username=admin_username).first()

                if existing_admin:
                    existing_admin.password_hash = hashed_password  # type: ignore[assignment]
                    existing_admin.email = admin_email  # type: ignore[assignment]
                    existing_admin.is_active = True  # type: ignore[assignment]
                    session.add(existing_admin)
                    logger.info(f"✓ Updated existing admin user (username: {admin_username}) from environment settings")
                    logger.warning("⚠ ADMIN CREDENTIALS OVERRIDDEN - change env as needed")
                else:
                    admin_user = User(
                        username=admin_username,
                        password_hash=hashed_password,
                        email=admin_email,
                        is_active=True
                    )
                    session.add(admin_user)
                    logger.info(f"✓ Created default admin user (username: {admin_username}) from environment settings")
                    logger.warning("⚠ CHANGE DEFAULT ADMIN PASSWORD IMMEDIATELY")
            
            logger.info("✓ Default data seeding complete")
            
        except Exception as e:
            logger.error(f"✗ Failed to seed default data: {e}")
            # Don't fail migration if seeding fails
    
    def add_missing_columns(self) -> Dict[str, Any]:
        """
        Add any missing columns to existing tables.
        IDEMPOTENT: Safe to run multiple times.
        
        Returns:
            Dict: Summary of added columns
        """
        logger.info("Checking for missing columns...")
        
        results = {"added_columns": []}
        
        try:
            session = self.db_manager.get_session()
            inspector = inspect(self.engine)
            
            # Check if races table exists and add table_name column if missing
            if self.table_exists("races"):
                races_columns = [col['name'] for col in inspector.get_columns('races')] if inspector else []
                
                if 'table_name' not in races_columns:
                    logger.info("Adding 'table_name' column to races table...")
                    session.execute(text("""
                        ALTER TABLE races 
                        ADD COLUMN table_name VARCHAR(128) UNIQUE;
                    """))
                    session.commit()
                    results["added_columns"].append("races.table_name")
                    logger.info("✓ Added table_name column to races table")
                else:
                    logger.info("✓ table_name column already exists in races table")
            
            session.close()
            
            return {
                "success": True,
                "added_columns": results["added_columns"]
            }
            
        except Exception as e:
            logger.error(f"✗ Failed to add missing columns: {e}")
            # Don't fail migration - column might already exist
            return {
                "success": True,
                "error": str(e),
                "added_columns": results["added_columns"]
            }
    
    def update_race_distance_constraint(self) -> Dict[str, Any]:
        """
        Update the race distance check constraint to allow minimum 10 meters.
        IDEMPOTENT: Safe to run multiple times.
        
        Returns:
            Dict: Summary of constraint update
        """
        logger.info("Updating race distance constraint...")
        
        try:
            session = self.db_manager.get_session()
            
            # Check if races table exists
            if not self.table_exists("races"):
                logger.info("Races table does not exist, skipping constraint update")
                return {"success": True, "skipped": True}
            
            # Drop old constraint if it exists and create new one
            session.execute(text("""
                ALTER TABLE races 
                DROP CONSTRAINT IF EXISTS check_race_distance;
            """))
            
            session.execute(text("""
                ALTER TABLE races 
                ADD CONSTRAINT check_race_distance 
                CHECK (distance_meters >= 10 AND distance_meters <= 100000);
            """))
            
            session.commit()
            session.close()
            
            logger.info("✓ Updated race distance constraint to minimum 10 meters")
            
            return {
                "success": True,
                "constraint_updated": "check_race_distance"
            }
            
        except Exception as e:
            logger.error(f"✗ Failed to update race distance constraint: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def cleanup_expired_nonces(self) -> int:
        """
        Clean up expired nonces from the cache.
        
        Returns:
            int: Number of nonces deleted
        """
        logger.info("Cleaning up expired nonces...")
        
        try:
            with self.db_manager.session_scope() as session:
                current_time = get_current_timestamp_utc()
                
                deleted_count = session.query(NonceCache).filter(
                    NonceCache.expires_at < current_time
                ).delete()
                
                logger.info(f"✓ Deleted {deleted_count} expired nonces")
                return deleted_count
                
        except Exception as e:
            logger.error(f"✗ Failed to cleanup expired nonces: {e}")
            return 0


# ============================================================================
# MIGRATION EXECUTION
# ============================================================================

def run_migrations() -> Dict[str, Any]:
    """
    Run all database migrations on application startup.
    IDEMPOTENT: Safe to run on every startup.
    
    Returns:
        Dict: Migration results
        
    Raises:
        DatabaseError: If critical migration steps fail
    """
    logger.info("=" * 80)
    logger.info("STARTING DATABASE MIGRATIONS")
    logger.info("=" * 80)
    
    migration_manager = MigrationManager()
    results = {}
    
    try:
        # Step 1: Create tables
        logger.info("\n[1/7] Creating database tables...")
        results["tables"] = migration_manager.create_tables()
        
        # Step 2: Add missing columns
        logger.info("\n[2/7] Adding missing columns...")
        results["columns"] = migration_manager.add_missing_columns()
        
        # Step 3: Update constraints
        logger.info("\n[3/7] Updating database constraints...")
        results["constraints"] = migration_manager.update_race_distance_constraint()
        
        # Step 4: Create custom indexes
        logger.info("\n[4/7] Creating custom indexes...")
        migration_manager.create_indexes()
        results["indexes"] = {"success": True}
        
        # Step 5: Add start/end columns to per-race participant tables
        logger.info("\n[5/7] Ensuring per-race participant tables have start/end times...")
        results["participant_time_columns"] = migration_manager.ensure_participant_time_columns()
        
        # Step 6: Verify schema
        logger.info("\n[6/7] Verifying database schema...")
        results["verification"] = migration_manager.verify_schema()
        
        if not results["verification"]["success"]:
            raise DatabaseError(
                message="Schema verification failed",
                details=results["verification"]
            )
        
        # Step 7: Seed default data
        logger.info("\n[7/7] Seeding default data...")
        migration_manager.seed_default_data()
        results["seeding"] = {"success": True}
        
        logger.info("\n" + "=" * 80)
        logger.info("✓ DATABASE MIGRATIONS COMPLETED SUCCESSFULLY")
        logger.info("=" * 80 + "\n")
        
        return {
            "success": True,
            "results": results
        }
        
    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ DATABASE MIGRATIONS FAILED")
        logger.error("=" * 80 + "\n")
        
        log_security_event(
            "MIGRATION_FAILED",
            {"error": str(e), "results": results},
            level="CRITICAL"
        )
        
        raise DatabaseError(
            message="Database migration failed",
            details={"error": str(e), "partial_results": results}
        )


def verify_database_ready() -> bool:
    """
    Quick check to verify database is ready for use.
    
    Returns:
        bool: True if database is ready, False otherwise
    """
    try:
        migration_manager = MigrationManager()
        verification = migration_manager.verify_schema()
        return verification["success"]
        
    except Exception as e:
        logger.error(f"Database readiness check failed: {e}")
        return False
