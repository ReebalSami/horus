"""Cross-tool ZUGFeRD validator wrapper (ADR-005).

Invokes the Mustang Project (Java) CLI via subprocess to validate that a
Factur-X / ZUGFeRD PDF produced by another tool (e.g., `factur-x` Python
library via `scripts/generate_zugferd_smoke.py`) is spec-compliant.

Rationale (per ADR-005 §"Decision + integration thoughts"):
- factur-x's built-in checks validate against the same XSDs that ship
  with the library → single-source compliance trust.
- Mustang is an independent codebase (Java, FeRD-affiliated) with its
  own XSD + Schematron validation pipeline → independent cross-tool
  verification of compliance.

Usage:
    uv run python scripts/validate_zugferd.py <path-to-pdf-or-xml>

Exit code: 0 if Mustang returns OK; 1 if invalid; 2 if execution failed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MUSTANG_JAR_GLOB = "tools/mustangproject/Mustang-CLI-*.jar"


def find_mustang_jar() -> Path:
    """Locate the Mustang JAR fetched via `make mustang-jar`."""
    matches = sorted(REPO_ROOT.glob(MUSTANG_JAR_GLOB))
    if not matches:
        print(
            f"ERROR: no Mustang JAR found under {MUSTANG_JAR_GLOB}.\n"
            "       Run `make mustang-jar` first (downloads + SHA-256-verifies "
            "the JAR per ADR-005).",
            file=sys.stderr,
        )
        sys.exit(2)
    # If multiple versions, prefer the highest (lexicographic sort works for
    # semver-like Mustang-CLI-X.Y.Z.jar).
    return matches[-1]


def validate(target: Path, jar: Path) -> int:
    cmd = [
        "java",
        "-jar",
        str(jar),
        "--action",
        "validate",
        "--source",
        str(target),
        "--no-notices",
        "--disable-file-logging",
    ]
    print(f"Invoking: {' '.join(cmd)}")
    print()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print(
            "ERROR: 'java' not found on PATH. Mustang requires a JRE/JDK.\n"
            "       Install via `brew install openjdk` (or use system Java).",
            file=sys.stderr,
        )
        return 2

    print("--- Mustang stdout ---")
    print(result.stdout)
    if result.stderr.strip():
        print("--- Mustang stderr ---")
        print(result.stderr)
    print(f"--- Mustang exit code: {result.returncode} ---")

    # Mustang prints "<validation><summary status=\"valid\">" / "invalid"
    # in its XML output. Parse from stdout for the canonical verdict.
    stdout_lower = result.stdout.lower()
    if 'status="valid"' in stdout_lower or '<summary status="valid"' in stdout_lower:
        print()
        print("=" * 60)
        print("CROSS-TOOL VALIDATION — Mustang verdict: VALID")
        print("=" * 60)
        return 0
    if 'status="invalid"' in stdout_lower:
        print()
        print("=" * 60)
        print("CROSS-TOOL VALIDATION — Mustang verdict: INVALID")
        print("=" * 60)
        return 1
    # Fall back to exit code if Mustang's output format changes.
    return result.returncode


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: uv run python scripts/validate_zugferd.py <path-to-pdf-or-xml>",
            file=sys.stderr,
        )
        return 2
    target = Path(sys.argv[1])
    if not target.is_absolute():
        target = (REPO_ROOT / target).resolve()
    if not target.exists():
        print(f"ERROR: file not found: {target}", file=sys.stderr)
        return 2

    jar = find_mustang_jar()
    print(f"Validating {target.relative_to(REPO_ROOT)} via {jar.relative_to(REPO_ROOT)}")
    return validate(target, jar)


if __name__ == "__main__":
    sys.exit(main())
