"""
RFID Marathon Management System - RFID Service
Security Level: Military-grade
Last Updated: January 21, 2026

This module handles RFID tag mapping and participant lookups.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, cast

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

from models import Participant, Race
from services.fernet_manager import get_fernet_manager
from services.rsa_manager import get_rsa_manager
from basefunctions import (
    NotFoundError,
    ConflictError,
    ValidationError,
    validate_rfid_tag,
)

logger = logging.getLogger(__name__)


class RFIDService:
    """
    Business logic for RFID tag management and participant lookups.
    """
    
    def __init__(self):
        self.fernet_manager = get_fernet_manager()
        self.rsa_manager = get_rsa_manager()
    
    def _calculate_category(self, age: Optional[int]) -> Optional[str]:
        """Calculate age category based on participant's age."""
        if age is None:
            return None
        
        if age <= 30:
            return "Up to 30 years"
        elif age <= 40:
            return "Up to 40 years"
        elif age <= 45:
            return "40-45 years"
        else:
            return "Above 45 years"
    
    def register_participant_with_rfid(
        self,
        db: Session,
        race_id: str,
        rfid_tag: str,
        name: str,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        category: Optional[str] = None,
        encryption_key_id: Optional[str] = None
    ) -> Participant:
        """
        Register participant with RFID tag.
        Name is encrypted using Fernet before storage.
        
        Args:
            db: Database session
            race_id: Race ID
            rfid_tag: RFID tag (plaintext)
            name: Participant name (will be encrypted)
            age: Optional age
            gender: Optional gender
            category: Optional category
            encryption_key_id: Encryption key ID
            
        Returns:
            Participant: Created participant object
            
        Raises:
            ValidationError: If input validation fails
            ConflictError: If RFID already registered for this race
        """
        # Validate RFID format
        if not validate_rfid_tag(rfid_tag):
            raise ValidationError("Invalid RFID tag format")
        
        # Normalize RFID tag to uppercase
        rfid_tag = rfid_tag.upper()
        
        # Validate gender (must be provided)
        if not gender:
            raise ValidationError("Gender is required and must be one of M, F, O")
        if gender not in ["M", "F", "O"]:
            raise ValidationError("Gender is invalid; must be M, F, or O")

        # Auto-calculate category from age if not provided
        if not category and age is not None:
            category = self._calculate_category(age)
        
        # Encrypt participant name using Fernet
        encrypted_name = self.fernet_manager.encrypt(name)
        
        # Get or create active encryption key
        if not encryption_key_id:
            key_record = self.fernet_manager.get_or_create_active_key(db)
            encryption_key_id = cast(str, key_record.id)
        
        # Get race to find participant table name
        race = db.query(Race).filter_by(id=race_id).first()
        if not race:
            raise NotFoundError("Race", race_id)
        
        participant_table = cast(Optional[str], race.table_name)
        if participant_table is None or participant_table.strip() == "":
            raise ValidationError("Race does not have a participant table configured")
        
        # Check per-race table for duplicate RFID registration in this race
        check_sql = text(f"""
            SELECT COUNT(*) as count FROM \"{participant_table}\"
            WHERE race_id = :race_id AND rfid_tag = :rfid_tag
        """)
        result = db.execute(check_sql, {"race_id": race_id, "rfid_tag": rfid_tag}).fetchone()
        if result and result[0] > 0:
            raise ConflictError(
                f"Duplicate Entry: RFID tag {rfid_tag} is already registered for this race",
                details={"rfid_tag": rfid_tag, "race_id": race_id}
            )
        
        try:
            # Generate participant ID upfront
            participant_id = str(uuid.uuid4())
            
            # Insert into per-race participant table ONLY
            # The ORM model is just a template for schema - actual data is in per-race tables
            insert_sql = text(f"""
                INSERT INTO \"{participant_table}\" 
                (id, race_id, rfid_tag, encrypted_name, age, gender, category, encryption_key_id, registered_at)
                VALUES (:id, :race_id, :rfid_tag, :encrypted_name, :age, :gender, :category, :encryption_key_id, NOW())
                RETURNING id, race_id, rfid_tag, encrypted_name, age, gender, category, registered_at, encryption_key_id
            """)
            
            result = db.execute(insert_sql, {
                "id": participant_id,
                "race_id": race_id,
                "rfid_tag": rfid_tag,
                "encrypted_name": encrypted_name,
                "age": age,
                "gender": gender,
                "category": category,
                "encryption_key_id": encryption_key_id
            }).fetchone()

            # Prefer the value returned by the database; fall back to a safe default
            registered_at = None
            if result is not None:
                registered_at = getattr(result, "registered_at", None)
            if registered_at is None:
                registered_at = datetime.now(timezone.utc)
            
            db.commit()
            
            # Construct a Participant object to return (not persisted to main table)
            participant = Participant(
                id=participant_id,
                race_id=race_id,
                rfid_tag=rfid_tag,
                encrypted_name=encrypted_name,
                age=age,
                gender=gender,
                category=category,
                encryption_key_id=encryption_key_id,
                registered_at=registered_at
            )
            
            logger.info(f"✓ Registered participant with RFID: {rfid_tag} in table: {participant_table}")
            return participant
            
        except IntegrityError as e:
            db.rollback()
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            logger.error(f"Failed to register participant: {e}")
            
            # Provide more specific error message
            if 'duplicate key' in error_msg.lower() or 'unique constraint' in error_msg.lower():
                raise ConflictError(
                    f"Duplicate Entry: RFID tag {rfid_tag} is already registered for this race",
                    details={"rfid_tag": rfid_tag, "race_id": race_id}
                )
            else:
                raise ConflictError("Participant registration failed - database constraint violation")
    
    def lookup_participant_by_rfid(
        self,
        db: Session,
        race_id: str,
        rfid_tag: str,
        encrypt_response: bool = True
    ) -> dict:
        """
        Lookup participant by RFID tag in the per-race participant table.
        Returns encrypted name using RSA for frontend decryption.
        
        Args:
            db: Database session
            race_id: Race ID
            rfid_tag: RFID tag
            encrypt_response: Whether to RSA-encrypt the name in response
            
        Returns:
            dict: Participant data with encrypted name
            
        Raises:
            NotFoundError: If participant not found
        """
        # Validate RFID format
        if not validate_rfid_tag(rfid_tag):
            raise ValidationError("Invalid RFID tag format")
        
        # Normalize RFID tag
        rfid_tag = rfid_tag.upper()
        
        # Get race to find participant table name
        race = db.query(Race).filter_by(id=race_id).first()
        if not race:
            raise NotFoundError("Race", race_id)
        
        participant_table = cast(Optional[str], race.table_name)
        if participant_table is None or participant_table.strip() == "":
            raise ValidationError("Race does not have a participant table configured")
        
        # Query the per-race participant table (not the ORM template table)
        lookup_sql = text(f"""
            SELECT id, race_id, rfid_tag, encrypted_name, age, gender, category, registered_at
            FROM "{participant_table}"
            WHERE race_id = :race_id AND rfid_tag = :rfid_tag
        """)
        result = db.execute(lookup_sql, {"race_id": race_id, "rfid_tag": rfid_tag}).fetchone()
        
        if not result:
            raise NotFoundError("Participant", f"RFID={rfid_tag}, Race={race_id}")
        
        # Extract participant data from query result
        participant_id = result[0] if hasattr(result, '__getitem__') else getattr(result, 'id')
        encrypted_name_stored = result[3] if hasattr(result, '__getitem__') else getattr(result, 'encrypted_name')
        age = result[4] if hasattr(result, '__getitem__') else getattr(result, 'age')
        gender = result[5] if hasattr(result, '__getitem__') else getattr(result, 'gender')
        category = result[6] if hasattr(result, '__getitem__') else getattr(result, 'category')
        registered_at = result[7] if hasattr(result, '__getitem__') else getattr(result, 'registered_at')
        
        # Decrypt name from database (Fernet encrypted)
        try:
            decrypted_name = self.fernet_manager.decrypt(cast(str, encrypted_name_stored))
        except Exception as e:
            logger.error(f"Failed to decrypt participant name: {e}")
            raise ValidationError("Failed to decrypt participant data")
        
        # Re-encrypt name with RSA for frontend
        if encrypt_response:
            rsa_encrypted_name = self.rsa_manager.encrypt_with_public_key(decrypted_name)
        else:
            rsa_encrypted_name = decrypted_name  # For testing/backend use
        
        return {
            "id": str(participant_id),
            "race_id": str(race_id),
            "rfid_tag": rfid_tag,
            "encrypted_name": rsa_encrypted_name,  # RSA encrypted
            "age": age,
            "gender": gender,
            "category": category,
            "registered_at": registered_at.isoformat() if hasattr(registered_at, 'isoformat') else str(registered_at)
        }
    
    def get_participant_by_id(
        self,
        db: Session,
        participant_id: str,
        decrypt_name: bool = False
    ) -> dict:
        """
        Get participant by ID.
        
        Args:
            db: Database session
            participant_id: Participant ID
            decrypt_name: Whether to decrypt name
            
        Returns:
            dict: Participant data
            
        Raises:
            NotFoundError: If participant not found
        """
        # Search each per-race participant table for the participant ID
        try:
            race_rows = db.execute(text("SELECT id, table_name FROM races")).fetchall()
        except Exception:
            raise NotFoundError("Participant", participant_id)

        for row in race_rows:
            table_name = row.table_name if hasattr(row, 'table_name') else row[1]
            if not table_name:
                continue
            try:
                lookup_sql = text(f'''
                    SELECT id, race_id, rfid_tag, encrypted_name, age, gender, category, registered_at
                    FROM "{table_name}"
                    WHERE id = :participant_id
                ''')
                res = db.execute(lookup_sql, {"participant_id": participant_id}).fetchone()
            except Exception:
                # Table may not exist or be inaccessible; skip
                continue

            if res:
                # Extract fields
                pid = res[0]
                race_id = res[1]
                rfid_tag = res[2]
                encrypted_name_stored = res[3]
                age = res[4]
                gender = res[5]
                category = res[6]
                registered_at = res[7]

                name_field = encrypted_name_stored
                if decrypt_name:
                    try:
                        name_field = self.fernet_manager.decrypt(cast(str, encrypted_name_stored))
                    except Exception as e:
                        logger.error(f"Failed to decrypt participant name: {e}")
                        name_field = "<DECRYPTION_FAILED>"

                return {
                    "id": str(pid),
                    "race_id": str(race_id),
                    "rfid_tag": rfid_tag,
                    "name": name_field,
                    "age": age,
                    "gender": gender,
                    "category": category,
                    "registered_at": registered_at.isoformat() if hasattr(registered_at, 'isoformat') else str(registered_at)
                }

        # Not found in any per-race table
        raise NotFoundError("Participant", participant_id)
    
    def check_rfid_exists(
        self,
        db: Session,
        race_id: str,
        rfid_tag: str
    ) -> bool:
        """
        Check if RFID tag is already registered for a specific race in that race's participant table.
        
        Args:
            db: Database session
            race_id: Race ID
            rfid_tag: RFID tag
            
        Returns:
            bool: True if exists in this race, False otherwise
        """
        rfid_tag = rfid_tag.upper()
        
        # Get race to find participant table name
        race = db.query(Race).filter_by(id=race_id).first()
        if not race:
            return False
        
        participant_table = cast(Optional[str], race.table_name)
        if participant_table is None or participant_table.strip() == "":
            return False
        
        # Check the per-race participant table
        check_sql = text(f"""
            SELECT COUNT(*) as count FROM "{participant_table}"
            WHERE race_id = :race_id AND rfid_tag = :rfid_tag
        """)
        result = db.execute(check_sql, {"race_id": race_id, "rfid_tag": rfid_tag}).fetchone()
        
        if not result:
            return False
        # support both Row objects with attribute 'count' and tuple-like rows
        count_value = getattr(result, 'count', None)
        if count_value is None:
            count_value = result[0]
        try:
            return int(count_value) > 0
        except Exception:
            return bool(count_value)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_rfid_service = None


def get_rfid_service() -> RFIDService:
    """
    Get global RFID service instance.
    
    Returns:
        RFIDService: Singleton instance
    """
    global _rfid_service
    
    if _rfid_service is None:
        _rfid_service = RFIDService()
    
    return _rfid_service
