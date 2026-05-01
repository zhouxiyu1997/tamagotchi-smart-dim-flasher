#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

CARD_SIZE = 4 * 1024 * 1024
MOCK_CARD_PATH = Path(os.environ.get("DIM_MOCK_CARD", "/tmp/dim-mock-card.bin"))


def ensure_mock_card() -> None:
    if MOCK_CARD_PATH.exists():
        return
    MOCK_CARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    MOCK_CARD_PATH.write_bytes(b"\xFF" * CARD_SIZE)


def main() -> int:
    ensure_mock_card()
    args = sys.argv[1:]

    if "--flash-name" in args:
        print('Found Macronix flash chip "MX25L3205(A)" (4096 kB, SPI) on ch341a_spi.')
        return 0

    if "-r" in args:
        target = Path(args[args.index("-r") + 1])
        shutil.copyfile(MOCK_CARD_PATH, target)
        print("Reading flash... done.")
        return 0

    if "-w" in args:
        source = Path(args[args.index("-w") + 1])
        shutil.copyfile(source, MOCK_CARD_PATH)
        print("Reading old flash chip contents... done.")
        print("Updating flash chip contents... done.")
        print("Erase/write done from 0 to 3fffff")
        print("Verifying flash... VERIFIED.")
        return 0

    print("Unsupported mock flashrom arguments:", " ".join(args), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
