"""Real orbital terrain (PDS PLACES 1 m DEM) and derived traversability layers.

The DEM is a mission data product (orbital stereo, published by the Mars 2020 team in PDS);
slope, roughness, cost and risk computed here are ``derived`` and rest on stated assumptions.
"""

TERRAIN_VERSION = "1"
"""Bump when derived-layer algorithms change (part of cache keys)."""
