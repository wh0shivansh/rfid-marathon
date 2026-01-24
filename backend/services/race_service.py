"""
RFID Marathon Management System - Race Service
Security Level: Military-grade
Last Updated: January 21, 2026

This module handles race management operations.
"""

import logging
from typing import List, Optional
from datetime import datetime
import uuid
import re

from sqlalchemy import text

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import Race, Participant, RaceStatus
from basefunctions import (
    NotFoundError,
    ConflictError,
    ValidationError,
    get_current_timestamp_utc,
    iso8601_to_timestamp,
)
from constants import RACE_MIN_DISTANCE_METERS, RACE_MAX_DISTANCE_METERS

logger = logging.getLogger(__name__)


class RaceService:
    """
    Business logic for race management.
    """
    
    def create_race(
        self,
        db: Session,
        name: str,
        distance_meters: int,
        location: str,
        scheduled_date_str: str,
        created_by: str,
        description: Optional[str] = None,
        age_upto30_excellent: Optional[float] = None,
        age_upto30_good: Optional[float] = None,
        age_upto30_satisfactory: Optional[float] = None,
        age_upto40_excellent: Optional[float] = None,
        age_upto40_good: Optional[float] = None,
        age_upto40_satisfactory: Optional[float] = None,
        age_40to45_excellent: Optional[float] = None,
        age_40to45_good: Optional[float] = None,
        age_40to45_satisfactory: Optional[float] = None
    ) -> Race:
        """
        Create a new race.
        
        Args:
            db: Database session
            name: Race name
            distance_meters: Race distance in meters
            location: Race location
            scheduled_date_str: ISO 8601 scheduled date
            created_by: User ID who created the race
            description: Optional description
            
        Returns:
            Race: Created race object
            
        Raises:
            ValidationError: If input validation fails
        """
        # Validate distance
        if distance_meters < RACE_MIN_DISTANCE_METERS or distance_meters > RACE_MAX_DISTANCE_METERS:
            raise ValidationError(
                f"Distance must be between {RACE_MIN_DISTANCE_METERS} and {RACE_MAX_DISTANCE_METERS} meters"
            )
        
        # Parse scheduled date
        try:
            scheduled_date = iso8601_to_timestamp(scheduled_date_str)
        except ValueError:
            raise ValidationError("Invalid scheduled date format")
        
        try:
            # Create a deterministic UUIDv5 based on race name + scheduled date
            # This ensures the race ID is stable for the same name+date combination
            name_key = name.strip().lower()
            date_key = scheduled_date.isoformat()
            deterministic_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{name_key}|{date_key}"))
            
            # Generate table name from race name
            table_name = self._build_table_name(name)

            race = Race(
                id=deterministic_uuid,
                name=name,
                distance_meters=distance_meters,
                location=location,
                scheduled_date=scheduled_date,
                description=description,
                status=RaceStatus.CREATED.value,
                created_by=created_by,
                table_name=table_name,
                age_upto30_excellent=age_upto30_excellent,
                age_upto30_good=age_upto30_good,
                age_upto30_satisfactory=age_upto30_satisfactory,
                age_upto40_excellent=age_upto40_excellent,
                age_upto40_good=age_upto40_good,
                age_upto40_satisfactory=age_upto40_satisfactory,
                age_40to45_excellent=age_40to45_excellent,
                age_40to45_good=age_40to45_good,
                age_40to45_satisfactory=age_40to45_satisfactory
            )
            
            db.add(race)
            db.commit()
            db.refresh(race)
            
            # Create per-race participant table
            self._create_per_race_participant_table(db, table_name, str(race.id))
            
            logger.info(f"✓ Created race: {race.id} ({name}) - participants table: {table_name}")
            return race
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to create race: {e}")
            raise ConflictError("Race creation failed due to constraint violation")
        except Exception as exc:
            db.rollback()
            logger.error(f"Unexpected error creating race: {exc}")
            raise

    def _build_table_name(self, name: str) -> str:
        # Remove non-alphanumeric, camel-case words, and ensure starts with letter
        parts = re.split(r"[^A-Za-z0-9]+", name.strip())
        parts = [p for p in parts if p]
        if not parts:
            parts = ["Race"]
        camel = "".join(p.capitalize() for p in parts)
        # Ensure starts with a letter (prepend R if needed)
        if not camel[0].isalpha():
            camel = "R" + camel
        return camel

    def _create_per_race_participant_table(self, db: Session, table_name: str, race_id: str) -> None:
        """
        Create a per-race participant table using the FiveKmRaceParticipants schema.
        
        Schema includes:
        - id (UUID, primary key)
        - race_id (UUID, foreign key to races)
        - rfid_tag (String, indexed)
        - encrypted_name (Text)
        - age (Integer, 5-120)
        - gender (String, M/F/O)
        - category (String)
        - registered_at (DateTime with timezone)
        - encryption_key_id (UUID, foreign key to encryption_keys)
        
        Args:
            db: Database session
            table_name: Name of the table to create
            race_id: ID of the race this table belongs to
        """
        try:
            # Create table with exact schema from Participant model
            create_table_sql = text(f"""
                CREATE TABLE IF NOT EXISTS "{table_name}" (
                    id UUID PRIMARY KEY,
                    race_id UUID NOT NULL REFERENCES races(id) ON DELETE CASCADE,
                    rfid_tag VARCHAR(32) NOT NULL,
                    encrypted_name TEXT NOT NULL,
                    age INTEGER,
                    gender VARCHAR(1) NOT NULL,
                    category VARCHAR(50),
                    registered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                    encryption_key_id UUID NOT NULL REFERENCES encryption_keys(id),
                    
                    CONSTRAINT uq_{table_name}_race_rfid UNIQUE (race_id, rfid_tag),
                    CONSTRAINT check_{table_name}_age CHECK (age >= 5 AND age <= 120),
                    CONSTRAINT check_{table_name}_gender CHECK (gender IN ('M', 'F', 'O'))
                );
            """)
            
            db.execute(create_table_sql)
            
            # Create indexes for performance
            create_indexes_sql = text(f"""
                CREATE INDEX IF NOT EXISTS idx_{table_name}_race_id ON "{table_name}" (race_id);
                CREATE INDEX IF NOT EXISTS idx_{table_name}_rfid_tag ON "{table_name}" (rfid_tag);
            """)
            
            db.execute(create_indexes_sql)
            db.commit()
            
            logger.info(f"✓ Created per-race participant table: {table_name}")
            
        except Exception as exc:
            db.rollback()
            logger.error(f"Failed to create per-race participant table {table_name}: {exc}")
            raise ConflictError(f"Failed to create participant table for race: {exc}")
    
    def get_race(self, db: Session, race_id: str) -> Race:
        """
        Get race by ID.
        
        Args:
            db: Database session
            race_id: Race ID
            
        Returns:
            Race: Race object
            
        Raises:
            NotFoundError: If race not found
        """
        race = db.query(Race).filter_by(id=race_id).first()
        
        if not race:
            raise NotFoundError("Race", race_id)
        
        return race
    
    def list_races(
        self, 
        db: Session, 
        status: Optional[RaceStatus] = None
    ) -> List[Race]:
        """
        List all races, optionally filtered by status.
        
        Args:
            db: Database session
            status: Optional status filter
            
        Returns:
            List[Race]: List of races
        """
        query = db.query(Race)
        
        if status:
            query = query.filter_by(status=status.value)
        
        races = query.order_by(Race.scheduled_date.desc()).all()
        
        logger.debug(f"Retrieved {len(races)} races")
        return races
    
    def update_race(
        self,
        db: Session,
        race_id: str,
        **updates
    ) -> Race:
        """
        Update race details.
        
        Args:
            db: Database session
            race_id: Race ID
            **updates: Fields to update
            
        Returns:
            Race: Updated race object
            
        Raises:
            NotFoundError: If race not found
        """
        race = self.get_race(db, race_id)
        
        # Update allowed fields
        allowed_fields = [
            'name', 'distance_meters', 'location', 
            'scheduled_date', 'description', 'status'
        ]
        
        for field, value in updates.items():
            if field in allowed_fields and value is not None:
                # Convert scheduled_date if it's a string
                if field == 'scheduled_date' and isinstance(value, str):
                    value = iso8601_to_timestamp(value)
                
                setattr(race, field, value)
        
        race.updated_at = get_current_timestamp_utc()  # type: ignore[assignment]
        
        db.commit()
        db.refresh(race)
        
        logger.info(f"✓ Updated race: {race_id}")
        return race
    
    def update_race_status(
        self,
        db: Session,
        race_id: str,
        new_status: RaceStatus
    ) -> Race:
        """
        Update race status with validation.
        
        Args:
            db: Database session
            race_id: Race ID
            new_status: New status
            
        Returns:
            Race: Updated race object
            
        Raises:
            ValidationError: If status transition is invalid
        """
        race = self.get_race(db, race_id)
        
        # Validate status transitions
        current_status = RaceStatus(race.status)
        
        # Define valid transitions
        valid_transitions = {
            RaceStatus.CREATED: [RaceStatus.REGISTRATION_OPEN, RaceStatus.CANCELLED],
            RaceStatus.REGISTRATION_OPEN: [RaceStatus.IN_PROGRESS, RaceStatus.CANCELLED],
            RaceStatus.IN_PROGRESS: [RaceStatus.COMPLETED],
            RaceStatus.COMPLETED: [],  # Final state
            RaceStatus.CANCELLED: []  # Final state
        }
        
        if new_status not in valid_transitions.get(current_status, []):
            raise ValidationError(
                f"Invalid status transition: {current_status.value} -> {new_status.value}"
            )
        
        race.status = new_status.value  # type: ignore[assignment]
        race.updated_at = get_current_timestamp_utc()  # type: ignore[assignment]
        
        db.commit()
        db.refresh(race)
        
        logger.info(f"✓ Updated race status: {race_id} -> {new_status.value}")
        return race
    
    def get_race_participant_count(self, db: Session, race_id: str) -> int:
        """
        Get number of participants registered for a race.
        
        Args:
            db: Database session
            race_id: Race ID
            
        Returns:
            int: Number of participants
        """
        count = db.query(Participant).filter_by(race_id=race_id).count()
        return count
    
    def get_race_statistics(self, db: Session, race_id: str) -> dict:
        """
        Get race statistics.
        
        Args:
            db: Database session
            race_id: Race ID
            
        Returns:
            dict: Race statistics
        """
        race = self.get_race(db, race_id)
        
        # Get participant table name
        table_name_value = getattr(race, "table_name", None)
        table_name = table_name_value if isinstance(table_name_value, str) and table_name_value else f"race_{race.name}_participants"
        
        try:
            # Count total participants in per-race table
            total_participants = db.execute(
                text(f"SELECT COUNT(*) FROM \"{table_name}\"")
            ).scalar() or 0
            
            # Count participants who have started (have start_time)
            started_count = db.execute(
                text(f"SELECT COUNT(*) FROM \"{table_name}\" WHERE start_time IS NOT NULL")
            ).scalar() or 0
            
            # Count participants who have finished (have end_time)
            finished_count = db.execute(
                text(f"SELECT COUNT(*) FROM \"{table_name}\" WHERE end_time IS NOT NULL")
            ).scalar() or 0
            
        except Exception as e:
            logger.debug(f"Could not query statistics for race {race_id} table {table_name}: {e}")
            total_participants = 0
            started_count = 0
            finished_count = 0
        
        return {
            "race_id": race_id,
            "race_name": race.name,
            "status": race.status,
            "total_participants": total_participants,
            "started_count": started_count,
            "finished_count": finished_count,
            "in_progress_count": started_count - finished_count
        }


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_race_service = None


def get_race_service() -> RaceService:
    """
    Get global race service instance.
    
    Returns:
        RaceService: Singleton instance
    """
    global _race_service
    
    if _race_service is None:
        _race_service = RaceService()
    
    return _race_service
