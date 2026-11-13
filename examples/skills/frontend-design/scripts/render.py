# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Example Author
"""Bundle the rendered components into a single archive."""

import argparse
import zipfile
from pathlib import Path


def bundle(source: Path, target: Path) -> int:
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source))
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    print(f"bundled {bundle(args.source, args.target)} files")


if __name__ == "__main__":
    main()
