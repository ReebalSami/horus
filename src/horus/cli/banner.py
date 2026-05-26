"""HORUS pyfiglet banner with brand colours (ADR-026).

Renders the HORUS word-art once at sweep start using pyfiglet (FIGlet font
"slant") coloured in eagle-orange (#E8833A) with a subtitle in
hieroglyph-cyan (#3AA8C8), matching the ADR-003 brand palette.

Usage::

    from horus.cli.banner import print_banner
    print_banner()           # writes to sys.stdout via a fresh rich.Console
    print_banner(console=c)  # reuse an existing Console (e.g., inside textual)
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console as RichConsole

EAGLE_ORANGE = "#E8833A"
HIEROGLYPH_CYAN = "#3AA8C8"
BANNER_FONT = "slant"

_SUBTITLE = "  Hybrid OCR-free Reading & Understanding System"
_VERSION_LINE = "  thesis project — FH Wedel SS 2026"


def print_banner(console: RichConsole | None = None) -> None:
    """Render the HORUS ASCII-art banner to *console* (or a fresh Console).

    Safe to call from a non-TTY context — rich auto-degrades to plain text
    with no ANSI escape sequences when the output stream is not a terminal.

    Args:
        console: Optional existing :class:`rich.console.Console`.  If None,
            a new Console writing to ``sys.stdout`` is created.  Pass the
            textual app's ``Console`` object to share the same output stream.
    """
    from pyfiglet import figlet_format  # noqa: PLC0415 — defer; pyfiglet is optional at import time
    from rich.console import Console  # noqa: PLC0415
    from rich.text import Text  # noqa: PLC0415

    c: RichConsole = console or Console(file=sys.stdout)
    art = figlet_format("HORUS", font=BANNER_FONT)
    c.print(Text(art.rstrip(), style=f"bold {EAGLE_ORANGE}"))
    c.print(Text(_SUBTITLE, style=f"bold {HIEROGLYPH_CYAN}"))
    c.print(Text(_VERSION_LINE, style=f"dim {HIEROGLYPH_CYAN}"))
    c.print()
