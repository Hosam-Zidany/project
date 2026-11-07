"""
run_all.py - run the exploration scripts of one / several / all folders.

    python run_all.py                 # every folder that has an explore.py
    python run_all.py 02 06           # only folders starting with 02_ and 06_
    python run_all.py --list          # list folders and exit
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def folders() -> list[Path]:
    return sorted(p for p in ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit() and (p / "explore.py").exists())


def main(argv: list[str]) -> int:
    all_folders = folders()
    if "--list" in argv:
        for f in all_folders:
            print(f.name)
        return 0

    wanted = [a for a in argv if not a.startswith("--")]
    selected = [f for f in all_folders if not wanted or any(f.name.startswith(w) for w in wanted)]
    if not selected:
        print("No matching folders. Use --list to see the available ones.")
        return 1

    failed = []
    for f in selected:
        print(f"\n{'#' * 90}\n>>> {f.name}\n{'#' * 90}")
        code = subprocess.call([sys.executable, str(f / "explore.py")], cwd=str(f))
        if code != 0:
            failed.append(f.name)

    print("\nSummary:", "all OK" if not failed else f"FAILED -> {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
