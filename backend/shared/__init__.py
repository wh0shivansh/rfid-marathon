"""
Shared initialization
"""
from .constants import *
from .database import db
from .models import Race, RaceEntry
from .utils import *

__all__ = [
    'db',
    'Race',
    'RaceEntry',
    'get_current_timestamp',
    'get_current_date',
    'format_date',
    'parse_date',
    'calculate_time_diff',
    'format_duration',
    'RACE_STATE_IDLE',
    'RACE_STATE_STARTED',
    'RACER_STATE_GRACE',
    'RACER_STATE_RUNNING',
    'RACER_STATE_FINISHED',
    'START_TIME_CORRECTION_THRESHOLD'
]
