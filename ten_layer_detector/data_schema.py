"""Column list of simulated sessions (kept for backwards compatibility; see schema.py)."""
from .schema import CANONICAL_COLUMNS, MULTI_GNSS_COLUMNS

SIMULATED_COLUMNS = list(CANONICAL_COLUMNS) + list(MULTI_GNSS_COLUMNS)
