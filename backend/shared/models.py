"""
Database models and schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Sequence, Mapping
from .database import db
from .constants import (
    RACE_STATE_IDLE, 
    RACE_STATE_STARTED,
    RACER_STATE_GRACE,
    RACER_STATE_RUNNING,
    RACER_STATE_FINISHED
)


class Race:
    """Race model"""
    
    @staticmethod
    def create_table():
        """Create the races table"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS races (
                    race_id SERIAL PRIMARY KEY,
                    race_name VARCHAR(255) NOT NULL,
                    race_date DATE NOT NULL,
                    state VARCHAR(20) DEFAULT 'idle',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT valid_state CHECK (state IN ('idle', 'started'))
                )
            """)
    
    @staticmethod
    def create(race_name: str, race_date: str) -> Optional[int]:
        """Create a new race"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO races (race_name, race_date, state)
                VALUES (%s, %s, %s)
                RETURNING race_id
            """, (race_name, race_date, RACE_STATE_IDLE))
            result = cursor.fetchone()
            if not result:
                return None
            return result['race_id']
    
    @staticmethod
    def get_by_id(race_id: int) -> Optional[Dict[str, Any]]:
        """Get race by ID"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM races WHERE race_id = %s
            """, (race_id,))
            return cursor.fetchone()
    
    @staticmethod
    def get_by_date(race_date: str) -> Optional[Dict[str, Any]]:
        """Get race by date"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM races WHERE race_date = %s
            """, (race_date,))
            return cursor.fetchone()
    
    @staticmethod
    def get_all() -> Sequence[Mapping[str, Any]]:
        """Get all races"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM races ORDER BY race_date DESC
            """)
            return cursor.fetchall()
    
    @staticmethod
    def update_state(race_id: int, state: str) -> bool:
        """Update race state"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                UPDATE races SET status = %s WHERE race_id = %s
            """, (state, race_id))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_active_race() -> Optional[Dict[str, Any]]:
        """Get the currently active (started) race"""
        with db.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM races WHERE state = %s
            """, (RACE_STATE_STARTED,))
            return cursor.fetchone()


class RaceEntry:
    """Model for per-race racer entries (dynamic tables)"""
    
    @staticmethod
    def get_table_name(race_id: int) -> str:
        """Get the table name for a race"""
        return f"race_{race_id}_entries"
    
    @staticmethod
    def create_table(race_id: int):
        """Create a per-race entries table"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    entry_id SERIAL PRIMARY KEY,
                    rfid VARCHAR(50) UNIQUE NOT NULL,
                    racer_name VARCHAR(255),
                    bib_number VARCHAR(50),
                    state VARCHAR(20) DEFAULT 'grace',
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT valid_entry_state CHECK (state IN ('grace', 'running', 'finished'))
                )
            """)
            # Create index on RFID for faster lookups
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_rfid 
                ON {table_name}(rfid)
            """)
    
    @staticmethod
    def insert(race_id: int, rfid: str, racer_name: Optional[str] = None, 
               bib_number: Optional[str] = None, state: str = RACER_STATE_GRACE,
               start_time: Optional[datetime] = None) -> Optional[int]:
        """Insert a new entry"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {table_name} (rfid, racer_name, bib_number, state, start_time)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING entry_id
            """, (rfid, racer_name, bib_number, state, start_time))
            result = cursor.fetchone()
            if not result:
                return None
            return result['entry_id']
    
    @staticmethod
    def get_by_rfid(race_id: int, rfid: str) -> Optional[Dict[str, Any]]:
        """Get entry by RFID"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM {table_name} WHERE rfid = %s
            """, (rfid,))
            return cursor.fetchone()
    
    @staticmethod
    def update_start_time(race_id: int, rfid: str, start_time: datetime, 
                          state: str = RACER_STATE_RUNNING) -> bool:
        """Update start time and state"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE {table_name}
                SET start_time = %s, state = %s
                WHERE rfid = %s
            """, (start_time, state, rfid))
            return cursor.rowcount > 0
    
    @staticmethod
    def update_end_time(race_id: int, rfid: str, end_time: datetime,
                        state: str = RACER_STATE_FINISHED) -> bool:
        """Update end time and state"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE {table_name}
                SET end_time = %s, state = %s
                WHERE rfid = %s
            """, (end_time, state, rfid))
            return cursor.rowcount > 0
    
    @staticmethod
    def get_all_grace_entries(race_id: int) -> Sequence[Mapping[str, Any]]:
        """Get all entries in grace state"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM {table_name} WHERE state = %s
            """, (RACER_STATE_GRACE,))
            return cursor.fetchall()
    
    @staticmethod
    def bulk_update_start_time(race_id: int, start_time: datetime) -> int:
        """Update all grace entries to running with start time"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE {table_name}
                SET start_time = %s, state = %s
                WHERE state = %s
            """, (start_time, RACER_STATE_RUNNING, RACER_STATE_GRACE))
            return cursor.rowcount
    
    @staticmethod
    def get_all_entries(race_id: int) -> Sequence[Mapping[str, Any]]:
        """Get all entries for a race"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT * FROM {table_name} ORDER BY entry_id
            """)
            return cursor.fetchall()
    
    @staticmethod
    def register_racer(race_id: int, rfid: str, racer_name: str, 
                       bib_number: str) -> Optional[int]:
        """Register a racer with full information"""
        table_name = RaceEntry.get_table_name(race_id)
        with db.get_cursor() as cursor:
            # Try to update existing entry
            cursor.execute(f"""
                UPDATE {table_name}
                SET racer_name = %s, bib_number = %s
                WHERE rfid = %s
                RETURNING entry_id
            """, (racer_name, bib_number, rfid))
            result = cursor.fetchone()
            
            if result:
                return result['entry_id']
            
            # Insert new entry
            cursor.execute(f"""
                INSERT INTO {table_name} (rfid, racer_name, bib_number, state)
                VALUES (%s, %s, %s, %s)
                RETURNING entry_id
            """, (rfid, racer_name, bib_number, RACER_STATE_GRACE))
            result = cursor.fetchone()
            if not result:
                return None
            return result['entry_id']
