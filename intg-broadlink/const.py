"""Broadlink integration constants."""

from enum import Enum, IntEnum, StrEnum
from ucapi import MediaStates

class States(IntEnum):
    """State of a connected Broadlink device."""

    UNKNOWN = 0
    UNAVAILABLE = 1
    OFF = 2
    ON = 3
    STANDBY = 4


BROADLINK_STATE_MAPPING = {
    States.OFF: MediaStates.OFF,
    States.ON: MediaStates.ON,
    States.STANDBY: MediaStates.STANDBY,
    States.UNAVAILABLE: MediaStates.UNAVAILABLE,
    States.UNKNOWN: MediaStates.UNKNOWN,
}
