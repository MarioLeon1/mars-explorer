"""Classical computer vision on raw rover images.

Everything here is *algorithmic* (deterministic, parameterised, explainable). Results are
``derived`` data: they describe image structure, not confirmed geology, and never physical
sizes or distances (raw images are uncalibrated and a single 2D view has no scale).
"""

ALGORITHM_VERSION = "1"
"""Bump when any algorithm changes so cached analyses are recomputed."""
