"""Update checking for Motif CLI.

Checks PyPI for newer versions and caches the result so we only
hit the network once per day.
"""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import motif
from motif.config import get_motif_dir

PYPI_URL = "https://pypi.org/pypi/motif-cli/json"
CACHE_FILE = "update-check.json"
CHECK_INTERVAL_SECONDS = 86400  # 24 hours


def _cache_path() -> Path:
    return get_motif_dir() / CACHE_FILE


def _read_cache() -> dict | None:
    path = _cache_path()
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(latest_version: str) -> None:
    path = _cache_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "latest_version": latest_version,
                "checked_at": time.time(),
            }, f)
    except OSError:
        pass


def _fetch_latest_version() -> str | None:
    """Query PyPI for the latest motif-cli version."""
    try:
        req = urllib.request.Request(PYPI_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return data["info"]["version"]
    except Exception:
        return None


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse '0.3.0' into (0, 3, 0) for comparison."""
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


def check_for_update(force: bool = False) -> dict | None:
    """Check if a newer version is available.

    Returns a dict with 'current', 'latest', 'update_available' keys,
    or None if the check was skipped (cached and recent).
    """
    current = motif.__version__
    cache = _read_cache()

    if not force and cache:
        elapsed = time.time() - cache.get("checked_at", 0)
        if elapsed < CHECK_INTERVAL_SECONDS:
            latest = cache["latest_version"]
            return {
                "current": current,
                "latest": latest,
                "update_available": _parse_version(latest) > _parse_version(current),
            }

    latest = _fetch_latest_version()
    if latest is None:
        return None

    _write_cache(latest)
    return {
        "current": current,
        "latest": latest,
        "update_available": _parse_version(latest) > _parse_version(current),
    }


def print_update_notice(console) -> None:
    """Print an update notice if a newer version exists. Non-blocking, silent on failure."""
    try:
        result = check_for_update()
        if result and result["update_available"]:
            console.print(
                f"\n[yellow]Update available:[/yellow] {result['current']} → [bold]{result['latest']}[/bold]"
                f"  Run [cyan]motif update[/cyan] to upgrade.\n"
            )
    except Exception:
        pass


def run_upgrade() -> bool:
    """Run pip install --upgrade motif-cli. Returns True on success."""
    return subprocess.call(
        [sys.executable, "-m", "pip", "install", "--upgrade", "motif-cli"]
    ) == 0
