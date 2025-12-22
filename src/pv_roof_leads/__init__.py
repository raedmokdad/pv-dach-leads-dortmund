"""
PV-Dach-Leads Pipeline für Dortmund
Identifiziert geeignete Gewerbe-/Industriedächer >500m² für PV-Anlagen
"""

__version__ = "0.1.0"
__author__ = "Raed Mokdad"

from .paths import (
    ROOT,
    DATA,
    RAW_DORTMUND,
    STAGING_DORTMUND,
    CURATED_DORTMUND,
    EXPORTS_DORTMUND,
    ensure_dirs,
)

__all__ = [
    "ROOT",
    "DATA",
    "RAW_DORTMUND",
    "STAGING_DORTMUND",
    "CURATED_DORTMUND",
    "EXPORTS_DORTMUND",
    "ensure_dirs",
]