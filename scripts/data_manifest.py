#!/usr/bin/env python3
"""
data_manifest.py — generate MANIFEST.md + sha256.txt for a downloaded HORUS dataset.

Outputs written to data/raw/<lang>/<slug>/:
  MANIFEST.md   git-tracked audit record (frontmatter + body)
  sha256.txt    per-file sha256 list (gitignored; regeneratable)

Usage:
    uv run python scripts/data_manifest.py \\
        --slug zugferd-corpus \\
        --lang german \\
        --source-url https://github.com/ZUGFeRD/corpus \\
        --source-type git_clone \\
        [--license-spdx LicenseRef-custom] \\
        [--license-url https://...] \\
        [--skip-sha256]

Invoke via Makefile:
    make data-manifest SLUG=<slug> LANG=<lang> \\
        SOURCE_URL=<url> SOURCE_TYPE=<type> \\
        LICENSE_SPDX=<spdx> LICENSE_URL=<url>
"""

import argparse
import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path

SKIP_NAMES = frozenset({"MANIFEST.md", "sha256.txt"})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_git_info(target_dir: Path) -> tuple[str, str]:
    """Return (commit_sha, commit_date_iso8601) if .git/ is present, else ('', '')."""
    git_dir = target_dir / ".git"
    if git_dir.exists():
        try:
            result = subprocess.run(
                ["git", "-C", str(target_dir), "log", "-1", "--format=%H|%cI"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            parts = result.stdout.strip().split("|", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
        except subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError:
            pass
    return "", ""


def scan_files(target_dir: Path, skip_sha256: bool) -> tuple[list[tuple[str, str]], int, int]:
    """
    Walk the target directory, optionally computing sha256 per file.

    Returns:
        entries:     list of (sha256_or_empty, relative_path) sorted by path
        total_bytes: sum of all file sizes
        file_count:  number of files (excluding MANIFEST.md, sha256.txt)
    """
    entries: list[tuple[str, str]] = []
    total_bytes = 0

    for path in sorted(target_dir.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(target_dir).parts
        # Skip .git/ directory contents — git internals are not part of the dataset.
        if rel_parts and rel_parts[0] == ".git":
            continue
        if path.name in SKIP_NAMES:
            continue
        rel = str(path.relative_to(target_dir))
        size = path.stat().st_size
        total_bytes += size
        if skip_sha256:
            entries.append(("", rel))
        else:
            entries.append((sha256_file(path), rel))

    return entries, total_bytes, len(entries)


def build_manifest(
    slug: str,
    lang: str,
    source_url: str,
    source_type: str,
    license_spdx: str,
    license_url: str,
    today: str,
    commit_sha: str,
    commit_date: str,
    file_count: int,
    total_bytes: int,
    sha256_aggregate: str,
    stub_rel: str,
) -> str:
    git_recipe = (
        f"git clone {source_url} data/raw/{lang}/{slug}"
        if source_type in ("git_clone", "hf_git_clone")
        else f"# Download from: {source_url}"
    )
    lfs_note = (
        "\n# For HF datasets with LFS: git lfs pull (before dropping .git/)"
        if source_type == "hf_git_clone"
        else ""
    )
    frontmatter = (
        "---\n"
        f"slug: {slug}\n"
        f"language: {lang}\n"
        f'source_url: "{source_url}"\n'
        f"source_type: {source_type}\n"
        f'license_spdx: "{license_spdx}"\n'
        f'license_url: "{license_url}"\n'
        f'license_verified_date: "{today}"\n'
        f'retrieved_date: "{today}"\n'
        f'commit_sha: "{commit_sha}"\n'
        f'commit_date: "{commit_date}"\n'
        f"file_count: {file_count}\n"
        f"total_bytes: {total_bytes}\n"
        f'sha256_aggregate: "{sha256_aggregate}"\n'
        "sample_load_passed: null  # set to true/false after manual verification\n"
        'sample_load_notes: ""     # brief description of what was verified\n'
        "anomalies: []\n"
        f'source_stub: "../../../../{stub_rel}"\n'
        "acquisition_status: completed\n"
        "---"
    )
    body = f"""

## Provenance

Dataset acquired as part of HORUS M2D.5 step 3 (issue #12) per
`docs/prompts/stages/02-brainstorm.md` §6.2 / §9.
See [`{stub_rel}`](../../../../{stub_rel}) for bibliographic details.

## Download recipe (reproducible)

```sh
{git_recipe}{lfs_note}
# Record commit_sha + commit_date BEFORE dropping .git/:
git -C data/raw/{lang}/{slug} log -1 --format='%H|%cI'
# Drop .git/ to reclaim disk:
rm -rf data/raw/{lang}/{slug}/.git
# Regenerate this manifest:
make data-manifest SLUG={slug} LANG={lang}
```

## Verification

```sh
# Regenerate sha256.txt + refresh file_count / total_bytes / sha256_aggregate:
make data-manifest SLUG={slug} LANG={lang}
# Set sample_load_passed and sample_load_notes in this file after manual spot-check.
```

## Sample-load notes

*(Fill in after verifying 3+ random files load without errors.)*

## Anomalies

*(None recorded.)*
"""
    return frontmatter + body


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate MANIFEST.md for a HORUS dataset corpus.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--slug", required=True, help="Dataset slug (kebab-case)")
    parser.add_argument(
        "--lang",
        required=True,
        help="Language dir (german/english/korean/multilingual)",
    )
    parser.add_argument("--source-url", default="", help="Canonical source URL")
    parser.add_argument(
        "--source-type",
        default="git_clone",
        choices=["git_clone", "hf_git_clone", "direct_zip", "author_request"],
        help="How the dataset was acquired",
    )
    parser.add_argument(
        "--license-spdx", default="", help="SPDX license identifier (e.g. CC-BY-4.0)"
    )
    parser.add_argument("--license-url", default="", help="URL to full license text")
    parser.add_argument(
        "--skip-sha256",
        action="store_true",
        help="Skip per-file hashing (fast; sha256_aggregate = 'pending'). For large datasets.",
    )
    parser.add_argument(
        "--commit-sha",
        default="",
        help="Override commit_sha (use when .git/ has been dropped and git extraction will fail).",
    )
    parser.add_argument(
        "--commit-date",
        default="",
        help="Override commit_date (use when .git/ has been dropped).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    target_dir = project_root / "data" / "raw" / args.lang / args.slug
    if not target_dir.exists():
        print(f"ERROR: Dataset directory not found: {target_dir}")
        raise SystemExit(1)

    stub_rel = f"docs/sources/datasets/{args.slug}.md"
    stub_path = project_root / stub_rel

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if args.commit_sha or args.commit_date:
        commit_sha, commit_date = args.commit_sha, args.commit_date
    else:
        commit_sha, commit_date = get_git_info(target_dir)

    print(f"Scanning {target_dir} ...")
    entries, total_bytes, file_count = scan_files(target_dir, skip_sha256=args.skip_sha256)

    if args.skip_sha256:
        sha256_aggregate = "pending"
        print("  Skipped sha256 hashing. Set sha256_aggregate manually after full hashing.")
    else:
        sha256_lines = [f"{digest}  {rel}" for digest, rel in entries]
        sha256_text_content = "\n".join(sha256_lines) + "\n"
        sha256_aggregate = sha256_text(sha256_text_content)
        sha256_txt_path = target_dir / "sha256.txt"
        sha256_txt_path.write_text(sha256_text_content, encoding="utf-8")
        print(f"  sha256.txt written ({file_count} entries).")

    manifest_content = build_manifest(
        slug=args.slug,
        lang=args.lang,
        source_url=args.source_url,
        source_type=args.source_type,
        license_spdx=args.license_spdx,
        license_url=args.license_url,
        today=today,
        commit_sha=commit_sha,
        commit_date=commit_date,
        file_count=file_count,
        total_bytes=total_bytes,
        sha256_aggregate=sha256_aggregate,
        stub_rel=stub_rel,
    )

    manifest_path = target_dir / "MANIFEST.md"
    manifest_path.write_text(manifest_content, encoding="utf-8")

    print("  MANIFEST.md written.")
    print(
        f"  file_count={file_count}  total_bytes={total_bytes:,}"
        f"  sha256_aggregate={sha256_aggregate[:16]}..."
    )
    if not stub_path.exists():
        print(
            f"  WARNING: source stub missing at {stub_path}"
            " — create it per horus-source-archival rule."
        )
    else:
        print(f"  Source stub found: {stub_rel}")
    print("Done. Set sample_load_passed + sample_load_notes in MANIFEST.md after verification.")


if __name__ == "__main__":
    main()
