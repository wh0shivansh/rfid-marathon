"""
Shared utilities
"""
from datetime import datetime, date
from typing import Optional


def get_current_timestamp() -> datetime:
    """Get current timestamp"""
    return datetime.now()


def get_current_date() -> date:
    """Get current date"""
    return date.today()


def format_date(date_obj: date) -> str:
    """Format date as string"""
    return date_obj.strftime("%Y-%m-%d")


def parse_date(date_str: str) -> date:
    """Parse date string"""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def calculate_time_diff(time1: datetime, time2: datetime) -> float:
    """Calculate time difference in seconds"""
    delta = abs(time1 - time2)
    return delta.total_seconds()


def format_duration(start_time: Optional[datetime], end_time: Optional[datetime]) -> Optional[str]:
    """Format duration between two times"""
    if not start_time or not end_time:
        return None
    
    delta = end_time - start_time
    total_seconds = int(delta.total_seconds())
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
