#!/usr/bin/env python3
"""
clear_cache.py — Clear all __pycache__ directories in the project
=================================================================

Run this script to fix stale bytecode cache issues like:
    AttributeError: module 'config.config' has no attribute 'get_settings'

Usage:
    python clear_cache.py          # Clear all caches
    python clear_cache.py --dry    # Preview what would be deleted
"""

import argparse
import shutil
import sys
from pathlib import Path


def find_pycache_dirs(root: Path) -> list[Path]:
    """Find all __pycache__ directories recursively."""
    pycache_dirs = []
    for pycache in root.rglob("__pycache__"):
        if pycache.is_dir():
            pycache_dirs.append(pycache)
    return pycache_dirs


def clear_cache(root: Path, dry_run: bool = False) -> int:
    """Clear all __pycache__ directories and return count of removed dirs."""
    pycache_dirs = find_pycache_dirs(root)
    count = 0

    for pycache in pycache_dirs:
        rel_path = pycache.relative_to(root)
        if dry_run:
            print(f"  [DRY] Would remove: {rel_path}")
        else:
            try:
                shutil.rmtree(pycache)
                print(f"  [OK] Removed: {rel_path}")
                count += 1
            except Exception as e:
                print(f"  [FAIL] Failed to remove {rel_path}: {e}")

    return count


def main():
    parser = argparse.ArgumentParser(description="Clear all __pycache__ directories in the project")
    parser.add_argument(
        "--dry", action="store_true", help="Preview what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--root", type=str, default=None, help="Root directory to search (default: script's parent directory)"
    )
    args = parser.parse_args()

    # Determine root directory
    if args.root:
        root = Path(args.root).resolve()
    else:
        root = Path(__file__).resolve().parent

    if not root.exists():
        print(f"Error: Root directory does not exist: {root}")
        sys.exit(1)

    mode = "DRY RUN" if args.dry else "LIVE"
    print(f"\n[Clearing] __pycache__ directories ({mode})")
    print(f"   Root: {root}\n")

    # Find and list all __pycache__ dirs
    pycache_dirs = find_pycache_dirs(root)
    print(f"Found {len(pycache_dirs)} __pycache__ directory(ies)\n")

    if not pycache_dirs:
        print("No __pycache__ directories found. Nothing to do!")
        return

    # Clear them
    count = clear_cache(root, args.dry)

    print(f"\n[Done] {'Would remove' if args.dry else 'Removed'} {count} item(s)")
    if args.dry:
        print("   Run without --dry to actually clear the cache.")


if __name__ == "__main__":
    main()
