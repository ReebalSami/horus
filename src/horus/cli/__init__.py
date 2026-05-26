"""HORUS CLI utilities — display adapters and terminal branding (ADR-026).

Public surface::

    from horus.cli import get_display_adapter, print_banner
    from horus.cli.dashboard import DisplayAdapter, PlainDisplayAdapter, SilentDisplayAdapter
"""

from __future__ import annotations

from horus.cli.banner import print_banner
from horus.cli.dashboard import (
    DisplayAdapter,
    HorusDashboardApp,
    PlainDisplayAdapter,
    SilentDisplayAdapter,
    get_display_adapter,
)

__all__ = [
    "DisplayAdapter",
    "HorusDashboardApp",
    "PlainDisplayAdapter",
    "SilentDisplayAdapter",
    "get_display_adapter",
    "print_banner",
]
