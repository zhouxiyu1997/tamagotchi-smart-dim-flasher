# tamagotchi-smart-dim-flasher

A local `macOS + CH341A` web flasher for backing up, writing, restoring, and resetting `Tamagotchi Smart` cards.

Copyright (C) 2026 `xiyu`

## User Guide

- Detailed usage guide: [`docs/USER-GUIDE.en.md`](docs/USER-GUIDE.en.md)

## Project Scope

- Platform: `macOS`
- Programmer: `CH341A`
- Main target: `Tamagotchi Smart` `DiM / TamaSma / BIM` cards
- Flash backend: `flashrom`
- Interface: local `Flask` web UI

This project is primarily organized around `Tamagotchi Smart`. Based on the underlying SPI flashing workflow, similar `Digimon` cards may also work in theory, but I have not verified them on real hardware.

## Features

- Upload a `1MB payload` or a full `BIN`
- Automatically detect the real chip model and card capacity
- Automatically back up the current card before install
- Restore the latest backup with one click
- Support full-image flashing across multiple capacities instead of assuming only `4MB`
- Reset `Tama Smart` usage counters while keeping the current card contents
- Store uploads, backups, and prepared images under `runtime/`

## Requirements

- `macOS`
- `Python 3.10+`
- Installed and working `flashrom`
- A `CH341A` programmer

If you use `Homebrew`, you can usually install `flashrom` with:

```bash
brew install flashrom
```

## Quick Start

After cloning the repository, run:

```bash
./start-web-ui.command
```

If macOS reports errors such as:

- `LIBUSB_ERROR_ACCESS`
- `root privilege`
- `Cannot detach the existing USB driver`

run it with `sudo` instead:

```bash
sudo ./start-web-ui.command
```

You can also double-click:

- `start-web-ui.command`
- `start-web-ui-root.command`

The first run will automatically create `.venv` and install dependencies.

## Typical Workflow

1. Connect the `CH341A` and insert the target card.
2. Click “Probe Current Card” first to confirm the chip and capacity.
3. Upload the `BIN` you want to flash.
4. The tool will automatically back up the current card.
5. Click “Install to Current DiM Card”.
6. If you need to revert, click “Restore Latest Backup”.
7. If you only want to keep the current contents and clear usage limits, click “Reset Current Card Usage”.

## BIN Rules

- `1MB BIN`
  Overwrites only the first `1MB`; the remaining area is kept from the current card backup.
- Full `BIN`
  The file size must match the actual detected card capacity, and the tool writes it as a full image.
- Reset usage
  The tool first backs up the current card, then scans valid `Tama Smart` headers across the image, clears usage slots, and recalculates checksums.

## Asset Policy

This repository does not bundle any card `BIN`, firmware package, or image resource.

- Use your own backups, or obtain resources yourself from places such as [Internet Archive](https://archive.org/)
- You are responsible for confirming the source, copyright status, and legality of your use
- If you want a convenient local place to keep resources, put them under `tamasmart/`; that directory is ignored by Git by default

## Project Layout

```text
.
├── dim_tool/                  # Flask app and flashing logic
├── runtime/                   # Generated uploads, backups, and prepared files
├── tamasmart/                 # Local assets directory (ignored by Git by default)
├── tools/mock_flashrom.py     # Mock flashrom for testing
├── start-web-ui.command       # Normal launcher
├── start-web-ui-root.command  # Root launcher
├── pyproject.toml             # Python project metadata
├── requirements.txt           # Dependencies used by launcher scripts
└── README.md
```

## Development

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Run locally:

```bash
python -m dim_tool
```

Basic validation:

```bash
python3 -m py_compile dim_tool/*.py
```

## Limitations

- This project has mainly been organized and verified around `Tamagotchi Smart`
- Other similar cards may be compatible, but are not comprehensively tested
- Write-protect support depends on the chip and `flashrom`
- Flashing, usage reset, and firmware operations all carry hardware risk
- This project is not affiliated with `Bandai`

## License

This repository is licensed under `GNU GPL v3.0`. See [LICENSE](LICENSE).

- When redistributing the original or a modified version, you must keep the original author attribution, copyright notice, and license text
- If you distribute a modified version, you must also provide the corresponding source code under `GPL-3.0` and mark your changes clearly
