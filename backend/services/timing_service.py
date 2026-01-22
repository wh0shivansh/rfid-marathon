"""
RFID Marathon Management System - Timing Service
Security Level: Military-grade
Last Updated: January 21, 2026

This module handles timing record creation with immutability enforcement.
Once a timing record is created, it CANNOT be modified.
"""

import logging
from typing import List, Optional, Dict, Any, cast
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models import TimingRecord, Participant, TimingPoint
from basefunctions import (
    NotFoundError,
    ConflictError,
    ValidationError,
    get_current_timestamp_utc,
    iso8601_to_timestamp,
    calculate_race_duration,
)

logger = logging.getLogger(__name__)


class TimingService:
    """
    Business logic for timing record management with IMMUTABILITY enforcement.
    """
    
    def record_timing(
        self,
        db: Session,
        race_id: str,
        rfid_tag: str,
        timing_point: TimingPoint,
        recorded_at_str: str,
        device_id: str
    ) -> TimingRecord:
        """
        Record timing event (start or end).
        IMMUTABLE: Once recorded, cannot be changed.
        
        Args:
            db: Database session
            race_id: Race ID
            rfid_tag: RFID tag
            timing_point: 'start' or 'end'
            recorded_at_str: ISO 8601 timestamp of timing event
            device_id: Device ID that recorded the timing
            
        Returns:
            TimingRecord: Created timing record
            
        Raises:
            NotFoundError: If participant not found
            ConflictError: If timing already recorded
            ValidationError: If timing point is invalid or start missing for end
        """
        # Normalize RFID tag
        rfid_tag = rfid_tag.upper()
        
        # Find participant
        participant = db.query(Participant).filter_by(
            race_id=race_id,
            rfid_tag=rfid_tag
        ).first()
        
        if not participant:
            raise NotFoundError(
                "Participant",
                f"RFID={rfid_tag}, Race={race_id}"
            )
        
        # Check if timing already recorded (IMMUTABILITY CHECK)
        existing_timing = db.query(TimingRecord).filter_by(
            race_id=race_id,
            participant_id=participant.id,
            timing_point=timing_point.value
        ).first()
        
        if existing_timing:
            logger.warning(
                f"Attempted to modify immutable timing record: "
                f"Participant={participant.id}, Point={timing_point.value}"
            )
            raise ConflictError(
                "Timing record already exists and is immutable",
                details={
                    "existing_record_id": existing_timing.id,
                    "existing_timestamp": existing_timing.recorded_at.isoformat()
                }
            )
        
        # If recording end time, verify start time exists
        if timing_point == TimingPoint.END:
            start_timing = db.query(TimingRecord).filter_by(
                race_id=race_id,
                participant_id=participant.id,
                timing_point=TimingPoint.START.value
            ).first()
            
            if not start_timing:
                raise ValidationError(
                    "Cannot record end time without start time"
                )
        
        # Parse recorded timestamp
        try:
            recorded_at = iso8601_to_timestamp(recorded_at_str)
        except ValueError:
            raise ValidationError("Invalid timestamp format")
        
        try:
            # Create timing record
            timing_record = TimingRecord(
                race_id=race_id,
                participant_id=participant.id,
                rfid_tag=rfid_tag,
                timing_point=timing_point.value,
                recorded_at=recorded_at,
                device_id=device_id,
                synced=True  # Marked as synced when created via API
            )
            
            db.add(timing_record)
            db.commit()
            db.refresh(timing_record)
            
            logger.info(
                f"✓ Recorded timing: Participant={participant.id}, "
                f"Point={timing_point.value}, Time={recorded_at_str}"
            )
            
            return timing_record
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to record timing: {e}")
            raise ConflictError("Timing record creation failed")
    
    def confirm_sync(
        self,
        db: Session,
        timing_record_ids: List[str]
    ) -> Dict[str, Any]:
        """
        Confirm that timing records have been synced.
        Used by frontend to mark local records as confirmed.
        
        Args:
            db: Database session
            timing_record_ids: List of timing record IDs to confirm
            
        Returns:
            Dict: Confirmation results
        """
        confirmed_ids = []
        failed_ids = []
        
        for record_id in timing_record_ids:
            try:
                timing_record = db.query(TimingRecord).filter_by(id=record_id).first()
                
                if timing_record:
                    timing_record.synced = True  # type: ignore[assignment]
                    confirmed_ids.append(record_id)
                else:
                    failed_ids.append(record_id)
                    
            except Exception as e:
                logger.error(f"Failed to confirm sync for record {record_id}: {e}")
                failed_ids.append(record_id)
        
        db.commit()
        
        logger.info(
            f"Sync confirmation: {len(confirmed_ids)} confirmed, "
            f"{len(failed_ids)} failed"
        )
        
        return {
            "confirmed_ids": confirmed_ids,
            "failed_ids": failed_ids,
            "timestamp": get_current_timestamp_utc().isoformat()
        }
    
    def get_participant_timings(
        self,
        db: Session,
        race_id: str,
        participant_id: str
    ) -> Dict[str, Any]:
        """
        Get all timing records for a participant.
        
        Args:
            db: Database session
            race_id: Race ID
            participant_id: Participant ID
            
        Returns:
            Dict: Timing records with duration calculation
        """
        timings = db.query(TimingRecord).filter_by(
            race_id=race_id,
            participant_id=participant_id
        ).all()
        
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None
        
        for timing in timings:
            timing_point_value = cast(str, timing.timing_point)
            if timing_point_value == TimingPoint.START.value:
                start_time = cast(datetime, timing.recorded_at)
            elif timing_point_value == TimingPoint.END.value:
                end_time = cast(datetime, timing.recorded_at)
        
        # Calculate duration if both times exist
        duration = None
        if start_time is not None and end_time is not None:
            duration = calculate_race_duration(start_time, end_time)
        
        return {
            "participant_id": participant_id,
            "race_id": race_id,
            "start_time": start_time.isoformat() if start_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "duration": duration,
            "has_started": start_time is not None,
            "has_finished": end_time is not None
        }
    
    def get_race_timings(
        self,
        db: Session,
        race_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get all timing records for a race.
        
        Args:
            db: Database session
            race_id: Race ID
            
        Returns:
            List[Dict]: List of timing records
        """
        timings = db.query(TimingRecord).filter_by(race_id=race_id).all()
        
        return [
            {
                "id": t.id,
                "participant_id": t.participant_id,
                "rfid_tag": t.rfid_tag,
                "timing_point": t.timing_point,
                "recorded_at": t.recorded_at.isoformat(),
                "device_id": t.device_id,
                "synced": t.synced
            }
            for t in timings
        ]
    
    def check_timing_exists(
        self,
        db: Session,
        race_id: str,
        participant_id: str,
        timing_point: TimingPoint
    ) -> bool:
        """
        Check if timing record exists for participant.
        
        Args:
            db: Database session
            race_id: Race ID
            participant_id: Participant ID
            timing_point: Timing point to check
            
        Returns:
            bool: True if exists, False otherwise
        """
        exists = db.query(TimingRecord).filter_by(
            race_id=race_id,
            participant_id=participant_id,
            timing_point=timing_point.value
        ).first() is not None
        
        return exists


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_timing_service = None


def get_timing_service() -> TimingService:
    """
    Get global timing service instance.
    
    Returns:
        TimingService: Singleton instance
    """
    global _timing_service
    
    if _timing_service is None:
        _timing_service = TimingService()
    
    return _timing_service
