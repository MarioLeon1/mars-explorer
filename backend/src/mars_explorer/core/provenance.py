"""Scientific-integrity classification attached to every data object."""

from enum import StrEnum


class Provenance(StrEnum):
    REAL_OBSERVATION = "real_observation"
    """Data exactly as published by NASA/JPL (or partners)."""
    DERIVED = "derived"
    """Computed by this application from real observations."""
    SIMULATED = "simulated"
    """Produced by a simulation; never a mission measurement."""
    USER_GENERATED = "user_generated"
    """Created by the user (annotations, chosen targets, etc.)."""
