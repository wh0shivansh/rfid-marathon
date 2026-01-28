"""
Race State Manager - In-Memory Group Management
Security Level: Military-grade
Last Updated: January 24, 2026

Manages races and grace periods for RFID timing:
- Groups: Collections of RFIDs that start together
- Grace periods: Time windows allowing late arrivals to join started groups
- Locking: Prevents new RFIDs from joining started groups after grace expires
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from threading import Lock

from basefunctions import get_current_timestamp_utc

logger = logging.getLogger("rfid-marathon.race-state")


class RaceStateManager:
    """
    Thread-safe in-memory manager for race state.
    
    Data structure:
    {
        "race_id": {
            "grace_period_ends_at": "ISO timestamp or None",
            "groups": [
                {
                    "group_number": 1,
                    "rfids": ["RFID001", "RFID002"],
                    "locked": True,
                    "created_at": "ISO timestamp",
                    "locked_at": "ISO timestamp or None"
                },
                {
                    "group_number": 2,
                    "rfids": ["RFID003"],
                    "locked": False,
                    "created_at": "ISO timestamp",
                    "locked_at": None
                }
            ]
        }
    }
    """
    
    def __init__(self):
        self._state: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        logger.info("✓ RaceStateManager initialized")
    
    def _ensure_race_exists(self, race_id: str) -> None:
        """Ensure race exists in state with initial structure."""
        if race_id not in self._state:
            self._state[race_id] = {
                "grace_period_ends_at": None,
                "groups": []
            }
            logger.debug(f"Created new race state: {race_id}")
    
    def _get_or_create_unlocked_group(self, race_id: str) -> Dict[str, Any]:
        """
        Get current unlocked group or create a new one.
        
        Returns:
            Current unlocked group dict
        """
        self._ensure_race_exists(race_id)
        
        groups = self._state[race_id]["groups"]
        
        # Find existing unlocked group
        for group in groups:
            if not group["locked"]:
                return group
        
        # Create new group
        new_group_number = len(groups) + 1
        new_group = {
            "group_number": new_group_number,
            "rfids": [],
            "locked": False,
            "created_at": get_current_timestamp_utc().isoformat(),
            "locked_at": None
        }
        groups.append(new_group)
        
        logger.info(f"✓ Created new group {new_group_number} for race {race_id}")
        return new_group
    
    def add_rfid_to_current_group(self, race_id: str, rfid_tag: str) -> bool:
        """
        Add RFID to current unlocked group.
        
        Args:
            race_id: Race identifier
            rfid_tag: RFID tag to add
            
        Returns:
            True if added, False if already exists in any group
        """
        with self._lock:
            self._ensure_race_exists(race_id)
            
            # Check if RFID already exists in any group
            groups = self._state[race_id]["groups"]
            for group in groups:
                if rfid_tag in group["rfids"]:
                    logger.debug(f"RFID {rfid_tag} already in group {group['group_number']}")
                    return False
            
            # Add to current unlocked group
            current_group = self._get_or_create_unlocked_group(race_id)
            current_group["rfids"].append(rfid_tag)
            
            logger.info(
                f"✓ Added RFID {rfid_tag} to race {race_id}, "
                f"group {current_group['group_number']}"
            )
            return True
    
    def get_current_group(self, race_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current unlocked group for a race.
        
        Returns:
            Current group dict or None if no unlocked group
        """
        with self._lock:
            self._ensure_race_exists(race_id)
            
            groups = self._state[race_id]["groups"]
            for group in groups:
                if not group["locked"]:
                    return group.copy()
            
            return None
    
    def get_all_groups(self, race_id: str) -> List[Dict[str, Any]]:
        """
        Get all groups for a race.
        
        Returns:
            List of all groups (copies)
        """
        with self._lock:
            self._ensure_race_exists(race_id)
            return [g.copy() for g in self._state[race_id]["groups"]]
    
    def start_race(self, race_id: str, grace_seconds: int = 120) -> None:
        """
        Start a race by locking current group and starting grace period.
        
        Args:
            race_id: Race identifier
            grace_seconds: Grace period duration in seconds
        """
        with self._lock:
            self._ensure_race_exists(race_id)
            
            # Lock current unlocked group
            groups = self._state[race_id]["groups"]
            current_group = None
            for group in groups:
                if not group["locked"]:
                    group["locked"] = True
                    group["locked_at"] = get_current_timestamp_utc().isoformat()
                    current_group = group
                    break
            
            if not current_group:
                logger.warning(f"No unlocked group to start for race {race_id}")
                return
            
            # Set grace period end time
            grace_end = get_current_timestamp_utc() + timedelta(seconds=grace_seconds)
            self._state[race_id]["grace_period_ends_at"] = grace_end.isoformat()
            
            logger.info(
                f"✓ Started race {race_id}: locked group {current_group['group_number']}, "
                f"grace ends at {grace_end.isoformat()}"
            )
    
    def lock_expired_groups(self, race_id: str) -> None:
        """
        Lock all unlocked groups after grace period expires.
        
        Args:
            race_id: Race identifier
        """
        with self._lock:
            if race_id not in self._state:
                return
            
            # Clear grace period
            self._state[race_id]["grace_period_ends_at"] = None
            
            # Lock all unlocked groups
            locked_count = 0
            groups = self._state[race_id]["groups"]
            for group in groups:
                if not group["locked"]:
                    group["locked"] = True
                    group["locked_at"] = get_current_timestamp_utc().isoformat()
                    locked_count += 1
            
            if locked_count > 0:
                logger.info(f"✓ Locked {locked_count} groups for race {race_id} (grace expired)")
    
    def get_all_races(self) -> Dict[str, Dict[str, Any]]:
        """
        Get state for all races.
        
        Returns:
            Complete state dictionary (deep copy)
        """
        with self._lock:
            # Return deep copy to prevent external modification
            import copy
            return copy.deepcopy(self._state)
    
    def clear_race_state(self, race_id: str) -> None:
        """
        Clear all state for a race (useful for testing/reset).
        
        Args:
            race_id: Race identifier
        """
        with self._lock:
            if race_id in self._state:
                del self._state[race_id]
                logger.info(f"✓ Cleared state for race {race_id}")


# Singleton instance
_race_state_manager_instance: Optional[RaceStateManager] = None


def get_race_state_manager() -> RaceStateManager:
    """
    Get singleton RaceStateManager instance.
    
    Returns:
        RaceStateManager singleton
    """
    global _race_state_manager_instance
    if _race_state_manager_instance is None:
        _race_state_manager_instance = RaceStateManager()
    return _race_state_manager_instance
