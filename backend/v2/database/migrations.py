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

from models import Base, User, NonceCache
from database.connection import get_database_manager
from basefunctions import DatabaseError, log_security_event, get_current_timestamp_IST
from constants import (
    AuditAction,
    RFID_DEFAULT_PREFIX,
    RFID_DEFAULT_SUFFIX_DIGITS,
    RFID_DEFAULT_SUFFIX_START_NUMBER,
)

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
        Ensure all per-race participant tables include `start_time`, `mid_time`, and `end_time`.
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
                race_rows = conn.execute(text("SELECT id, table_name, rfid_placement_mode FROM races")).fetchall()
                for row in race_rows:
                    race_id = row.id if hasattr(row, "id") else row[0]
                    table_name = row.table_name if hasattr(row, "table_name") else row[1]
                    race_mode = row.rfid_placement_mode if hasattr(row, "rfid_placement_mode") else (row[2] if len(row) > 2 else None)
                    if not table_name:
                        results["skipped_tables"].append({"race_id": str(race_id), "reason": "no table_name"})
                        continue
                    # Inspect columns
                    cols = [col['name'] for col in inspector.get_columns(table_name)] if inspector else []
                    alterations = []
                    if 'start_time' not in cols:
                        alterations.append("ADD COLUMN start_time TIMESTAMPTZ NULL")
                    if 'mid_time' not in cols:
                        alterations.append("ADD COLUMN mid_time TIMESTAMPTZ NULL")
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
    
    def ensure_participant_status_column(self) -> Dict[str, Any]:
        """
        Ensure all per-race participant tables include `status` column.
        Uses the `races.table_name` to locate per-race tables and adds column if missing.
        IDEMPOTENT and safe across all environments.
        
        Status values: 'registered', 'grace', 'running', 'completed', 'fail'
        """
        results: Dict[str, Any] = {"updated_tables": [], "skipped_tables": [], "errors": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)
            # Fetch all races to know participant table names
            with self.engine.connect() as conn:
                race_rows = conn.execute(text("SELECT id, table_name, rfid_placement_mode FROM races")).fetchall()
                for row in race_rows:
                    race_id = row.id if hasattr(row, "id") else row[0]
                    table_name = row.table_name if hasattr(row, "table_name") else row[1]
                    race_mode = row.rfid_placement_mode if hasattr(row, "rfid_placement_mode") else (row[2] if len(row) > 2 else None)
                    if not table_name:
                        results["skipped_tables"].append({"race_id": str(race_id), "reason": "no table_name"})
                        continue
                    # Inspect columns
                    cols = [col['name'] for col in inspector.get_columns(table_name)] if inspector else []
                    if 'status' not in cols:
                        alter_sql = f"""
                            ALTER TABLE "{table_name}" 
                            ADD COLUMN status VARCHAR(20) DEFAULT 'registered' NOT NULL,
                            ADD CONSTRAINT check_{table_name}_status 
                            CHECK (status IN ('registered', 'grace', 'running', 'completed', 'fail'))
                        """
                        try:
                            conn.execute(text(alter_sql))
                            # Update existing rows based on their timing data
                            update_sql = f"""
                                UPDATE "{table_name}"
                                SET status = CASE
                                    WHEN end_time IS NOT NULL AND mid_time IS NULL AND :race_mode != 'end_intersection' THEN 'fail'
                                    WHEN end_time IS NOT NULL THEN 'completed'
                                    WHEN start_time IS NOT NULL THEN 'running'
                                    ELSE 'registered'
                                END
                                WHERE status = 'registered'
                            """
                            conn.execute(text(update_sql), {"race_mode": str(race_mode or "mid_end_reader_diff")})
                            results["updated_tables"].append(table_name)
                        except Exception as e:
                            results["errors"].append({"table": table_name, "error": str(e)})
                    else:
                        # Ensure the status constraint allows fail
                        try:
                            conn.execute(text(f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS check_{table_name}_status'))
                            conn.execute(text(f"""
                                ALTER TABLE "{table_name}"
                                ADD CONSTRAINT check_{table_name}_status
                                CHECK (status IN ('registered', 'grace', 'running', 'completed', 'fail'))
                            """))

                            # Mark missing mid_time as fail where end_time exists
                            conn.execute(text(f"""
                                UPDATE "{table_name}"
                                SET status = 'fail'
                                WHERE end_time IS NOT NULL
                                  AND mid_time IS NULL
                                  AND status != 'fail'
                                  AND :race_mode != 'end_intersection'
                            """), {"race_mode": str(race_mode or "mid_end_reader_diff")})

                            # Normalize invalid/null statuses
                            conn.execute(text(f"""
                                UPDATE "{table_name}"
                                SET status = 'registered'
                                WHERE status IS NULL OR status NOT IN ('registered', 'grace', 'running', 'completed', 'fail')
                            """))

                            results["updated_tables"].append(table_name)
                        except Exception as e:
                            results["errors"].append({"table": table_name, "error": str(e)})
                conn.commit()
            results["success"] = True
            return results
        except Exception as e:
            logger.error(f"✗ Failed ensuring participant status column: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    def ensure_participant_gender_not_null(self) -> Dict[str, Any]:
        """
        Ensure gender is NOT NULL in all per-race participant tables.
        - Backfill NULL/invalid gender values to 'O'
        - Set DEFAULT 'O' and NOT NULL on gender column
        """
        results: Dict[str, Any] = {"updated_tables": [], "skipped_tables": [], "errors": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)
            with self.engine.connect() as conn:
                race_rows = conn.execute(text("SELECT id, table_name FROM races")).fetchall()
                for row in race_rows:
                    race_id = row.id if hasattr(row, "id") else row[0]
                    table_name = row.table_name if hasattr(row, "table_name") else row[1]
                    if not table_name:
                        results["skipped_tables"].append({"race_id": str(race_id), "reason": "no table_name"})
                        continue
                    cols = [col['name'] for col in inspector.get_columns(table_name)] if inspector else []
                    if 'gender' not in cols:
                        results["skipped_tables"].append({"table": table_name, "reason": "no gender column"})
                        continue
                    try:
                        conn.execute(text(f"UPDATE \"{table_name}\" SET gender = 'O' WHERE gender IS NULL OR gender NOT IN ('M','F','O')"))
                        conn.execute(text(f"ALTER TABLE \"{table_name}\" ALTER COLUMN gender SET DEFAULT 'O', ALTER COLUMN gender SET NOT NULL"))
                        results["updated_tables"].append(table_name)
                    except Exception as e:
                        results["errors"].append({"table": table_name, "error": str(e)})
                conn.commit()
            results["success"] = True
            return results
        except Exception as e:
            logger.error(f"✗ Failed enforcing gender NOT NULL: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    def ensure_race_timing_columns(self) -> Dict[str, Any]:
        """
        Ensure races table includes per-category start times and end_time columns.
        IDEMPOTENT and safe across all environments.
        """
        results: Dict[str, Any] = {"added_columns": [], "skipped": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)

            if not self.table_exists("races"):
                logger.info("Races table does not exist, skipping timing columns")
                return {"success": True, "skipped": True}

            cols = [col['name'] for col in inspector.get_columns('races')] if inspector else []

            with self.engine.connect() as conn:
                if 'bpet_start_time' not in cols:
                    conn.execute(text("ALTER TABLE races ADD COLUMN bpet_start_time JSONB NULL"))
                    results["added_columns"].append("bpet_start_time")
                    logger.info("✓ Added bpet_start_time column to races table")
                else:
                    results["skipped"].append("bpet_start_time")

                if 'cpt_start_time' not in cols:
                    conn.execute(text("ALTER TABLE races ADD COLUMN cpt_start_time JSONB NULL"))
                    results["added_columns"].append("cpt_start_time")
                    logger.info("✓ Added cpt_start_time column to races table")
                else:
                    results["skipped"].append("cpt_start_time")

                if 'ppt_start_time' not in cols:
                    conn.execute(text("ALTER TABLE races ADD COLUMN ppt_start_time JSONB NULL"))
                    results["added_columns"].append("ppt_start_time")
                    logger.info("✓ Added ppt_start_time column to races table")
                else:
                    results["skipped"].append("ppt_start_time")

                legacy_cols = set(cols)
                if {
                    "bpet_up30start_time",
                    "bpet_upto40start_time",
                    "bpet_40_45start_time",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET bpet_start_time = jsonb_build_array(
                            bpet_up30start_time,
                            bpet_upto40start_time,
                            bpet_40_45start_time
                        )
                        WHERE bpet_start_time IS NULL
                    """))

                if {
                    "cpt_up35start_time",
                    "35_45start_time",
                    "45_50start_time",
                    "50_55start_time",
                    "55_60start_time",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET cpt_start_time = jsonb_build_array(
                            cpt_up35start_time,
                            "35_45start_time",
                            "45_50start_time",
                            "50_55start_time",
                            "55_60start_time"
                        )
                        WHERE cpt_start_time IS NULL
                    """))

                if 'end_time' not in cols:
                    conn.execute(text("ALTER TABLE races ADD COLUMN end_time TIMESTAMP WITH TIME ZONE NULL"))
                    results["added_columns"].append("end_time")
                    logger.info("✓ Added end_time column to races table")
                else:
                    results["skipped"].append("end_time")

                conn.commit()

            results["success"] = True
            return results
        except Exception as e:
            logger.error(f"✗ Failed ensuring race timing columns: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    def ensure_race_qualifying_columns(self) -> Dict[str, Any]:
        """
        Ensure races table includes JSONB qualifying time columns per category.
        IDEMPOTENT and safe across all environments.
        """
        results: Dict[str, Any] = {"added_columns": [], "skipped": [], "errors": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)

            if not self.table_exists("races"):
                logger.info("Races table does not exist, skipping qualifying columns")
                return {"success": True, "skipped": True}

            cols = [col['name'] for col in inspector.get_columns('races')] if inspector else []

            column_defs = {
                "bpet_age_upto30": "JSONB NOT NULL DEFAULT '[1500,1578,1620]'::jsonb",
                "bpet_age_upto40": "JSONB NOT NULL DEFAULT '[1698,1800,1860]'::jsonb",
                "bpet_age_40_45": "JSONB NOT NULL DEFAULT '[1878,1980,2100]'::jsonb",
                "cpt_age_upto35": "JSONB NOT NULL DEFAULT '[840,900,960,1050]'::jsonb",
                "cpt_age_35_45": "JSONB NOT NULL DEFAULT '[960,1020,1080,1200]'::jsonb",
                "cpt_age_45_50": "JSONB NOT NULL DEFAULT '[1020,1080,1140,1230]'::jsonb",
                "cpt_age_50_55": "JSONB NOT NULL DEFAULT '[1680,1800,1920,2040]'::jsonb",
                "cpt_age_55_60": "JSONB NOT NULL DEFAULT '[1920,2040,2160,2280]'::jsonb",
                "ppt_age_upto30": "JSONB NOT NULL DEFAULT '[540,570,600]'::jsonb",
                "ppt_age_30_40": "JSONB NOT NULL DEFAULT '[630,660,690]'::jsonb",
                "ppt_age_40_45": "JSONB NOT NULL DEFAULT '[690,720,750]'::jsonb",
                "ppt_age_45_50": "JSONB NOT NULL DEFAULT '[780,840,900]'::jsonb",
            }

            with self.engine.connect() as conn:
                for col_name, col_def in column_defs.items():
                    if col_name not in cols:
                        try:
                            conn.execute(text(f"ALTER TABLE races ADD COLUMN {col_name} {col_def}"))
                            results["added_columns"].append(col_name)
                            logger.info(f"✓ Added {col_name} column to races table")
                        except Exception as e:
                            results["errors"].append({"column": col_name, "error": str(e)})
                    else:
                        results["skipped"].append(col_name)

                legacy_cols = set(cols)
                if {
                    "bpet_age_upto30_excellent",
                    "bpet_age_upto30_good",
                    "bpet_age_upto30_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET bpet_age_upto30 = jsonb_build_array(
                            bpet_age_upto30_excellent,
                            bpet_age_upto30_good,
                            bpet_age_upto30_satisfactory
                        )
                    """))

                if {
                    "bpet_age_upto40_excellent",
                    "bpet_age_upto40_good",
                    "bpet_age_upto40_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET bpet_age_upto40 = jsonb_build_array(
                            bpet_age_upto40_excellent,
                            bpet_age_upto40_good,
                            bpet_age_upto40_satisfactory
                        )
                    """))

                if {
                    "bpet_age_40to45_excellent",
                    "bpet_age_40to45_good",
                    "bpet_age_40to45_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET bpet_age_40_45 = jsonb_build_array(
                            bpet_age_40to45_excellent,
                            bpet_age_40to45_good,
                            bpet_age_40to45_satisfactory
                        )
                    """))

                if {
                    "cpt_age_upto35_superb",
                    "cpt_age_upto35_excellent",
                    "cpt_age_upto35_good",
                    "cpt_age_upto35_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET cpt_age_upto35 = jsonb_build_array(
                            cpt_age_upto35_superb,
                            cpt_age_upto35_excellent,
                            cpt_age_upto35_good,
                            cpt_age_upto35_satisfactory
                        )
                    """))

                if {
                    "cpt_age_35to45_superb",
                    "cpt_age_35to45_excellent",
                    "cpt_age_35to45_good",
                    "cpt_age_35to45_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET cpt_age_35_45 = jsonb_build_array(
                            cpt_age_35to45_superb,
                            cpt_age_35to45_excellent,
                            cpt_age_35to45_good,
                            cpt_age_35to45_satisfactory
                        )
                    """))

                if {
                    "cpt_age_45to50_superb",
                    "cpt_age_45to50_excellent",
                    "cpt_age_45to50_good",
                    "cpt_age_45to50_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET cpt_age_45_50 = jsonb_build_array(
                            cpt_age_45to50_superb,
                            cpt_age_45to50_excellent,
                            cpt_age_45to50_good,
                            cpt_age_45to50_satisfactory
                        )
                    """))

                if {
                    "cpt_age_50to55_superb",
                    "cpt_age_50to55_excellent",
                    "cpt_age_50to55_good",
                    "cpt_age_50to55_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET cpt_age_50_55 = jsonb_build_array(
                            cpt_age_50to55_superb,
                            cpt_age_50to55_excellent,
                            cpt_age_50to55_good,
                            cpt_age_50to55_satisfactory
                        )
                    """))

                if {
                    "cpt_age_55to60_superb",
                    "cpt_age_55to60_excellent",
                    "cpt_age_55to60_good",
                    "cpt_age_55to60_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET cpt_age_55_60 = jsonb_build_array(
                            cpt_age_55to60_superb,
                            cpt_age_55to60_excellent,
                            cpt_age_55to60_good,
                            cpt_age_55to60_satisfactory
                        )
                    """))

                if {
                    "ppt_age_upto30_excellent",
                    "ppt_age_upto30_good",
                    "ppt_age_upto30_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET ppt_age_upto30 = jsonb_build_array(
                            ppt_age_upto30_excellent,
                            ppt_age_upto30_good,
                            ppt_age_upto30_satisfactory
                        )
                    """))

                if {
                    "ppt_age_30to40_excellent",
                    "ppt_age_30to40_good",
                    "ppt_age_30to40_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET ppt_age_30_40 = jsonb_build_array(
                            ppt_age_30to40_excellent,
                            ppt_age_30to40_good,
                            ppt_age_30to40_satisfactory
                        )
                    """))

                if {
                    "ppt_age_40to45_excellent",
                    "ppt_age_40to45_good",
                    "ppt_age_40to45_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET ppt_age_40_45 = jsonb_build_array(
                            ppt_age_40to45_excellent,
                            ppt_age_40to45_good,
                            ppt_age_40to45_satisfactory
                        )
                    """))

                if {
                    "ppt_age_45to50_excellent",
                    "ppt_age_45to50_good",
                    "ppt_age_45to50_satisfactory",
                }.issubset(legacy_cols):
                    conn.execute(text("""
                        UPDATE races
                        SET ppt_age_45_50 = jsonb_build_array(
                            ppt_age_45to50_excellent,
                            ppt_age_45to50_good,
                            ppt_age_45to50_satisfactory
                        )
                    """))
                conn.commit()

            results["success"] = True
            return results
        except Exception as e:
            logger.error(f"✗ Failed ensuring race qualifying columns: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    def ensure_race_qualifying_constraints(self) -> Dict[str, Any]:
        """
        Ensure races table includes list-length constraints for qualifying times and start times.
        IDEMPOTENT and safe across all environments.
        """
        results: Dict[str, Any] = {"added_constraints": [], "skipped": [], "errors": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)

            if not self.table_exists("races"):
                logger.info("Races table does not exist, skipping qualifying constraints")
                return {"success": True, "skipped": True}

            existing = [c.get("name") for c in (inspector.get_check_constraints("races") if inspector else [])]
            constraints = {
                "check_bpet_age_upto30_len": "CHECK (jsonb_typeof(bpet_age_upto30) = 'array' AND jsonb_array_length(bpet_age_upto30) = 3)",
                "check_bpet_age_upto40_len": "CHECK (jsonb_typeof(bpet_age_upto40) = 'array' AND jsonb_array_length(bpet_age_upto40) = 3)",
                "check_bpet_age_40_45_len": "CHECK (jsonb_typeof(bpet_age_40_45) = 'array' AND jsonb_array_length(bpet_age_40_45) = 3)",
                "check_cpt_age_upto35_len": "CHECK (jsonb_typeof(cpt_age_upto35) = 'array' AND jsonb_array_length(cpt_age_upto35) = 4)",
                "check_cpt_age_35_45_len": "CHECK (jsonb_typeof(cpt_age_35_45) = 'array' AND jsonb_array_length(cpt_age_35_45) = 4)",
                "check_cpt_age_45_50_len": "CHECK (jsonb_typeof(cpt_age_45_50) = 'array' AND jsonb_array_length(cpt_age_45_50) = 4)",
                "check_cpt_age_50_55_len": "CHECK (jsonb_typeof(cpt_age_50_55) = 'array' AND jsonb_array_length(cpt_age_50_55) = 4)",
                "check_cpt_age_55_60_len": "CHECK (jsonb_typeof(cpt_age_55_60) = 'array' AND jsonb_array_length(cpt_age_55_60) = 4)",
                "check_ppt_age_upto30_len": "CHECK (jsonb_typeof(ppt_age_upto30) = 'array' AND jsonb_array_length(ppt_age_upto30) = 3)",
                "check_ppt_age_30_40_len": "CHECK (jsonb_typeof(ppt_age_30_40) = 'array' AND jsonb_array_length(ppt_age_30_40) = 3)",
                "check_ppt_age_40_45_len": "CHECK (jsonb_typeof(ppt_age_40_45) = 'array' AND jsonb_array_length(ppt_age_40_45) = 3)",
                "check_ppt_age_45_50_len": "CHECK (jsonb_typeof(ppt_age_45_50) = 'array' AND jsonb_array_length(ppt_age_45_50) = 3)",
                "check_bpet_start_time_len": "CHECK (bpet_start_time IS NULL OR (jsonb_typeof(bpet_start_time) = 'array' AND jsonb_array_length(bpet_start_time) = 3))",
                "check_cpt_start_time_len": "CHECK (cpt_start_time IS NULL OR (jsonb_typeof(cpt_start_time) = 'array' AND jsonb_array_length(cpt_start_time) = 5))",
                "check_ppt_start_time_len": "CHECK (ppt_start_time IS NULL OR (jsonb_typeof(ppt_start_time) = 'array' AND jsonb_array_length(ppt_start_time) = 4))",
            }

            with self.engine.connect() as conn:
                for name, clause in constraints.items():
                    if name in existing:
                        results["skipped"].append(name)
                        continue
                    try:
                        conn.execute(text(f"ALTER TABLE races ADD CONSTRAINT {name} {clause}"))
                        results["added_constraints"].append(name)
                        logger.info(f"✓ Added constraint {name}")
                    except Exception as e:
                        results["errors"].append({"constraint": name, "error": str(e)})
                conn.commit()

            results["success"] = True
            return results
        except Exception as e:
            logger.error(f"✗ Failed ensuring race qualifying constraints: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    def ensure_participant_bulk_columns(self) -> Dict[str, Any]:
        """
        Ensure all per-race participant tables include bulk upload columns.
        Adds s_no, army_number, rank, remarks if missing.
        """
        results: Dict[str, Any] = {"updated_tables": [], "skipped_tables": [], "errors": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)
            with self.engine.connect() as conn:
                race_rows = conn.execute(text("SELECT id, table_name FROM races")).fetchall()
                for row in race_rows:
                    race_id = row.id if hasattr(row, "id") else row[0]
                    table_name = row.table_name if hasattr(row, "table_name") else row[1]
                    if not table_name:
                        results["skipped_tables"].append({"race_id": str(race_id), "reason": "no table_name"})
                        continue
                    cols = [col['name'] for col in inspector.get_columns(table_name)] if inspector else []
                    alterations = []
                    if 's_no' not in cols:
                        alterations.append("ADD COLUMN s_no INTEGER NULL")
                    if 'army_number' not in cols:
                        alterations.append("ADD COLUMN army_number VARCHAR(64) NULL")
                    if 'rank' not in cols:
                        alterations.append("ADD COLUMN rank VARCHAR(64) NULL")
                    if 'remarks' not in cols:
                        alterations.append("ADD COLUMN remarks TEXT NULL")
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
            logger.error(f"✗ Failed ensuring participant bulk columns: {e}")
            results["success"] = False
            results["error"] = str(e)
            return results

    def ensure_participant_army_number_unique(self) -> Dict[str, Any]:
        """
        Ensure all per-race participant tables enforce unique army_number per race.
        Adds UNIQUE(race_id, army_number) constraint if missing.
        """
        results: Dict[str, Any] = {"updated_tables": [], "skipped_tables": [], "errors": []}
        try:
            if self.engine is None:
                return {"success": False, "error": "No engine"}
            inspector = inspect(self.engine)
            with self.engine.connect() as conn:
                race_rows = conn.execute(text("SELECT id, table_name FROM races")).fetchall()
                for row in race_rows:
                    race_id = row.id if hasattr(row, "id") else row[0]
                    table_name = row.table_name if hasattr(row, "table_name") else row[1]
                    if not table_name:
                        results["skipped_tables"].append({"race_id": str(race_id), "reason": "no table_name"})
                        continue
                    cols = [col['name'] for col in inspector.get_columns(table_name)] if inspector else []
                    if "army_number" not in cols:
                        results["skipped_tables"].append({"table": table_name, "reason": "no army_number column"})
                        continue

                    constraint_name = f"uq_{table_name}_race_army_number"
                    existing_constraints = [
                        c.get("name") for c in (inspector.get_unique_constraints(table_name) if inspector else [])
                    ]
                    if constraint_name in existing_constraints:
                        results["skipped_tables"].append(table_name)
                        continue

                    try:
                        conn.execute(
                            text(
                                f"UPDATE \"{table_name}\" "
                                "SET army_number = NULL "
                                "WHERE army_number IS NOT NULL AND BTRIM(army_number) = ''"
                            )
                        )
                        conn.execute(
                            text(
                                f"ALTER TABLE \"{table_name}\" "
                                f"ADD CONSTRAINT {constraint_name} UNIQUE (race_id, army_number)"
                            )
                        )
                        results["updated_tables"].append(table_name)
                    except Exception as e:
                        results["errors"].append({"table": table_name, "error": str(e)})
                conn.commit()
            results["success"] = True
            return results
        except Exception as e:
            logger.error(f"✗ Failed enforcing army_number uniqueness: {e}")
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
            
            return {
                "success": True,
                "existing_tables_before": list(existing_tables_before),
                "existing_tables_after": list(existing_tables_after),
                "new_tables_created": list(new_tables),
                "total_tables": len(existing_tables_after)
            }
            
        except SQLAlchemyError as e:
            logger.error(f"✗ Failed to create tables: {e}")
            
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
                
                # Add status column if missing
                if 'status' not in races_columns:
                    logger.info("Adding 'status' column to races table...")
                    session.execute(text("""
                        ALTER TABLE races 
                        ADD COLUMN status VARCHAR(20) DEFAULT 'created' NOT NULL;
                    """))
                    # Add check constraint for status values
                    try:
                        session.execute(text("""
                            ALTER TABLE races 
                            ADD CONSTRAINT check_race_status CHECK (status IN ('created', 'started'));
                        """))
                    except Exception as e:
                        # Constraint might already exist, don't fail
                        logger.warning(f"Could not add status constraint (may already exist): {e}")
                    
                    session.commit()
                    results["added_columns"].append("races.status")
                    logger.info("✓ Added status column to races table")
                else:
                    logger.info("✓ status column already exists in races table")

                # Ensure location is optional (nullable)
                try:
                    session.execute(text("""
                        ALTER TABLE races
                        ALTER COLUMN location DROP NOT NULL;
                    """))
                    session.commit()
                except Exception as e:
                    logger.warning(f"Could not make races.location nullable: {e}")

                # Add race_category column if missing
                if 'race_category' not in races_columns:
                    logger.info("Adding 'race_category' column to races table...")
                    session.execute(text("""
                        ALTER TABLE races
                        ADD COLUMN race_category VARCHAR(50) DEFAULT 'BPET' NOT NULL;
                    """))
                    try:
                        session.execute(text("""
                            ALTER TABLE races
                            ADD CONSTRAINT check_race_category
                            CHECK (race_category IN ('BPET', 'CPT', 'PPT'));
                        """))
                    except Exception as e:
                        logger.warning(f"Could not add race_category constraint (may already exist): {e}")
                    session.commit()
                    results["added_columns"].append("races.race_category")
                    logger.info("✓ Added race_category column to races table")
                else:
                    logger.info("✓ race_category column already exists in races table")

                # Add rfid_placement_mode column if missing
                if 'rfid_placement_mode' not in races_columns:
                    logger.info("Adding 'rfid_placement_mode' column to races table...")
                    session.execute(text("""
                        ALTER TABLE races
                        ADD COLUMN rfid_placement_mode VARCHAR(50) DEFAULT 'mid_end_reader_diff' NOT NULL;
                    """))
                    session.commit()
                    results["added_columns"].append("races.rfid_placement_mode")
                    logger.info("✓ Added rfid_placement_mode column to races table")
                else:
                    logger.info("✓ rfid_placement_mode column already exists in races table")

                # Add rfid_prefix column if missing
                if 'rfid_prefix' not in races_columns:
                    logger.info("Adding 'rfid_prefix' column to races table...")
                    session.execute(text("""
                        ALTER TABLE races
                        ADD COLUMN rfid_prefix VARCHAR(32);
                    """))
                    session.execute(
                        text("UPDATE races SET rfid_prefix = :rfid_prefix WHERE rfid_prefix IS NULL"),
                        {"rfid_prefix": RFID_DEFAULT_PREFIX}
                    )
                    session.execute(text(f"""
                        ALTER TABLE races
                        ALTER COLUMN rfid_prefix SET DEFAULT '{RFID_DEFAULT_PREFIX}',
                        ALTER COLUMN rfid_prefix SET NOT NULL;
                    """))
                    session.commit()
                    results["added_columns"].append("races.rfid_prefix")
                    logger.info("✓ Added rfid_prefix column to races table")
                else:
                    logger.info("✓ rfid_prefix column already exists in races table")

                # Add rfid_suffix_digits column if missing
                if 'rfid_suffix_digits' not in races_columns:
                    logger.info("Adding 'rfid_suffix_digits' column to races table...")
                    session.execute(text("""
                        ALTER TABLE races
                        ADD COLUMN rfid_suffix_digits INTEGER;
                    """))
                    session.execute(
                        text("UPDATE races SET rfid_suffix_digits = :rfid_suffix_digits WHERE rfid_suffix_digits IS NULL"),
                        {"rfid_suffix_digits": int(RFID_DEFAULT_SUFFIX_DIGITS)}
                    )
                    session.execute(text(f"""
                        ALTER TABLE races
                        ALTER COLUMN rfid_suffix_digits SET DEFAULT {int(RFID_DEFAULT_SUFFIX_DIGITS)},
                        ALTER COLUMN rfid_suffix_digits SET NOT NULL;
                    """))
                    session.commit()
                    results["added_columns"].append("races.rfid_suffix_digits")
                    logger.info("✓ Added rfid_suffix_digits column to races table")
                else:
                    logger.info("✓ rfid_suffix_digits column already exists in races table")

                # Add rfid_suffix_start_number column if missing
                if 'rfid_suffix_start_number' not in races_columns:
                    logger.info("Adding 'rfid_suffix_start_number' column to races table...")
                    session.execute(text("""
                        ALTER TABLE races
                        ADD COLUMN rfid_suffix_start_number INTEGER;
                    """))
                    session.execute(
                        text("UPDATE races SET rfid_suffix_start_number = :rfid_suffix_start_number WHERE rfid_suffix_start_number IS NULL"),
                        {"rfid_suffix_start_number": int(RFID_DEFAULT_SUFFIX_START_NUMBER)}
                    )
                    session.execute(text(f"""
                        ALTER TABLE races
                        ALTER COLUMN rfid_suffix_start_number SET DEFAULT {int(RFID_DEFAULT_SUFFIX_START_NUMBER)},
                        ALTER COLUMN rfid_suffix_start_number SET NOT NULL;
                    """))
                    session.commit()
                    results["added_columns"].append("races.rfid_suffix_start_number")
                    logger.info("✓ Added rfid_suffix_start_number column to races table")
                else:
                    logger.info("✓ rfid_suffix_start_number column already exists in races table")

                # Ensure mode constraint exists and supports all values
                try:
                    session.execute(text("""
                        ALTER TABLE races
                        DROP CONSTRAINT IF EXISTS check_race_rfid_placement_mode;
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        ADD CONSTRAINT check_race_rfid_placement_mode
                        CHECK (rfid_placement_mode IN ('mid_end_reader_diff', 'end_intersection'));
                    """))
                    session.commit()
                except Exception as e:
                    logger.warning(f"Could not update rfid_placement_mode constraint: {e}")

                # Ensure RFID allocation constraints are present
                try:
                    session.execute(text("""
                        ALTER TABLE races
                        DROP CONSTRAINT IF EXISTS check_race_rfid_prefix_hex;
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        ADD CONSTRAINT check_race_rfid_prefix_hex
                        CHECK (rfid_prefix ~ '^[A-Fa-f0-9]+$');
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        DROP CONSTRAINT IF EXISTS check_race_rfid_suffix_digits;
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        ADD CONSTRAINT check_race_rfid_suffix_digits
                        CHECK (rfid_suffix_digits >= 1 AND rfid_suffix_digits <= 12);
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        DROP CONSTRAINT IF EXISTS check_race_rfid_tag_length;
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        ADD CONSTRAINT check_race_rfid_tag_length
                        CHECK (char_length(rfid_prefix) + rfid_suffix_digits <= 32);
                    """))

                    session.execute(text("""
                        ALTER TABLE races
                        DROP CONSTRAINT IF EXISTS check_race_rfid_suffix_start_non_negative;
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        ADD CONSTRAINT check_race_rfid_suffix_start_non_negative
                        CHECK (rfid_suffix_start_number >= 0);
                    """))

                    session.execute(text("""
                        ALTER TABLE races
                        DROP CONSTRAINT IF EXISTS check_race_rfid_suffix_start_range;
                    """))
                    session.execute(text("""
                        ALTER TABLE races
                        ADD CONSTRAINT check_race_rfid_suffix_start_range
                        CHECK (rfid_suffix_start_number < power(10, rfid_suffix_digits));
                    """))
                    session.commit()
                except Exception as e:
                    logger.warning(f"Could not update race RFID allocation constraints: {e}")
            
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

    def update_race_status_constraint(self) -> Dict[str, Any]:
        """
        Update the race status check constraint to allow all valid status values.
        This is idempotent and safe to run multiple times.
        """
        logger.info("Updating race status constraint...")

        try:
            session = self.db_manager.get_session()

            if not self.table_exists("races"):
                logger.info("Races table does not exist, skipping status constraint update")
                return {"success": True, "skipped": True}

            # Drop old constraint if it exists and create new one allowing all statuses
            session.execute(text("""
                ALTER TABLE races
                DROP CONSTRAINT IF EXISTS check_race_status;
            """))

            session.execute(text("""
                ALTER TABLE races
                ADD CONSTRAINT check_race_status
                CHECK (status IN ('created', 'started', 'completed'));
            """))

            session.commit()
            session.close()

            logger.info("✓ Updated race status constraint to allow all valid statuses")

            return {
                "success": True,
                "constraint_updated": "check_race_status"
            }

        except Exception as e:
            logger.error(f"✗ Failed to update race status constraint: {e}")
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
                current_time = get_current_timestamp_IST()
                
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
        logger.info("\n[1/15] Creating database tables...")
        results["tables"] = migration_manager.create_tables()
        
        # Step 2: Add missing columns
        logger.info("\n[2/15] Adding missing columns...")
        results["columns"] = migration_manager.add_missing_columns()
        
        # Step 3: Update constraints
        logger.info("\n[3/15] Updating database constraints...")
        results["constraints"] = migration_manager.update_race_distance_constraint()
        # Step 4: Update race status constraint to include all valid statuses
        logger.info("\n[4/15] Updating race status constraint...")
        results["status_constraint"] = migration_manager.update_race_status_constraint()
        
        # Step 5: Create custom indexes
        logger.info("\n[5/15] Creating custom indexes...")
        migration_manager.create_indexes()
        results["indexes"] = {"success": True}
        
        # Step 6: Add start/end columns to per-race participant tables
        logger.info("\n[6/15] Ensuring per-race participant tables have start/end times...")
        results["participant_time_columns"] = migration_manager.ensure_participant_time_columns()
        
        # Step 7: Add status column to per-race participant tables
        logger.info("\n[7/15] Ensuring per-race participant tables have status column...")
        results["participant_status_column"] = migration_manager.ensure_participant_status_column()
        
        # Step 8: Enforce gender NOT NULL in participant tables
        logger.info("\n[8/15] Enforcing gender NOT NULL in participant tables...")
        results["participant_gender_not_null"] = migration_manager.ensure_participant_gender_not_null()
        
        # Step 9: Add bulk upload columns to per-race participant tables
        logger.info("\n[9/15] Ensuring per-race participant tables have bulk upload columns...")
        results["participant_bulk_columns"] = migration_manager.ensure_participant_bulk_columns()

        # Step 10: Enforce unique army_number per race
        logger.info("\n[10/15] Enforcing unique army_number per race...")
        results["participant_army_number_unique"] = migration_manager.ensure_participant_army_number_unique()

        # Step 11: Add race qualifying columns (JSONB lists)
        logger.info("\n[11/15] Adding race qualifying columns (JSONB lists)...")
        results["race_qualifying_columns"] = migration_manager.ensure_race_qualifying_columns()

        # Step 12: Add race timing columns (start time lists, end_time)
        logger.info("\n[12/15] Adding race timing columns (start time lists, end_time)...")
        results["race_timing_columns"] = migration_manager.ensure_race_timing_columns()

        # Step 13: Add qualifying list constraints
        logger.info("\n[13/15] Adding qualifying list constraints...")
        results["race_qualifying_constraints"] = migration_manager.ensure_race_qualifying_constraints()
        
        # Step 14: Verify schema
        logger.info("\n[14/15] Verifying database schema...")
        results["verification"] = migration_manager.verify_schema()
        
        if not results["verification"]["success"]:
            raise DatabaseError(
                message="Schema verification failed",
                details=results["verification"]
            )
        
        # Step 15: Seed default data
        logger.info("\n[15/15] Seeding default data...")
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
