# tamagotchi-smart-dim-flasher User Guide

This guide is for first-time users. It focuses on how to start the tool, what each button does, the recommended workflow, and how to handle common errors.

## Scope

- OS: `macOS`
- Programmer: `CH341A`
- Target cards: `Tamagotchi Smart` `DiM / TamaSma / BIM`
- Flash backend: `flashrom`
- Interface: local `Web UI`

This project is primarily organized and tested around `Tamagotchi Smart`. Similar cards may work, but you should verify that yourself.

## Before You Start

Make sure you have:

- `Python 3.10+`
- a working `flashrom` installation
- a connected `CH341A`
- the target card inserted into the programmer
- the `BIN` file you want to use

If you use `Homebrew`, you can usually install `flashrom` with:

```bash
brew install flashrom
```

## Start the Web UI

Run this in the repository root:

```bash
./start-web-ui.command
```

On the first run, the launcher will:

- create `.venv`
- install dependencies from `requirements.txt`
- start the local web server

You should see output like:

```text
DiM tool web UI: http://127.0.0.1:8765
```

The browser should open automatically. If it does not, open the printed URL manually.

If you see permission errors such as:

- `LIBUSB_ERROR_ACCESS`
- `root privilege`
- `Cannot detach the existing USB driver`

restart with:

```bash
sudo ./start-web-ui.command
```

You can also double-click:

- `start-web-ui.command`
- `start-web-ui-root.command`

## What Each Button Does

### `Upload and back up current card`

- Select a `BIN`
- The file is saved under `runtime/uploads/`
- The tool then backs up the current card into `runtime/backups/`
- If that succeeds, the file becomes the current upload in the UI

### `Install to current DiM card`

- Uses the current uploaded file as the source
- Backs up the current card again before writing
- Prepares the final image based on the BIN type
- Writes and verifies the image

### `Back up current card only`

- Reads the card and creates a backup
- Does not change card contents
- Good for making a clean backup before anything else

### `Probe current card size`

- Uses `flashrom` to detect chip model and capacity
- Updates the most recent detected chip and size in the UI
- Recommended whenever you swap cards

### `Reset current card usage count`

- Backs up the current card first
- Scans the card for valid `Tama Smart` headers
- Clears usage slots and recalculates checksums
- Tries to enable full-card write protection when supported

### `Restore latest backup`

- Writes the most recent backup back to the card
- Useful for reverting to the pre-install state

## Recommended Workflow

For a normal flash workflow:

1. Connect the `CH341A` and insert the target card.
2. Start the Web UI.
3. Click `Probe current card size`.
4. Click `Back up current card only` to keep a manual backup.
5. Click `Upload and back up current card` and select your `BIN`.
6. Confirm that the upload and backup panels updated.
7. Click `Install to current DiM card`.
8. If needed, click `Restore latest backup`.

If you only want to reset usage without changing contents:

1. Click `Probe current card size`.
2. Click `Reset current card usage count`.
3. Check the operation summary and log to see whether write protection was enabled.

## BIN Rules

The tool supports two input types.

### `1MB BIN`

- This is treated as a `payload`
- Only the first `1MB` is replaced
- The remaining area is kept from the current card backup

### Full `BIN`

- The file size must match the real detected card capacity
- Supported range is `2MB` to `16MB`
- The tool writes the whole image

If the file is neither `1MB` nor a supported full image, the UI will reject it.

## Understanding the Status Panels

The lower part of the page shows the latest state:

- `Current upload`
  shows file name, size, time, and `SHA-256`
- `Latest backup`
  shows the newest automatic or manual backup
- `Latest operation`
  shows the latest flash, usage reset, or restore summary
- `Runtime status`
  shows `flashrom` path, programmer type, probe results, runtime directory, and logs

If something fails, read the log panel first. It usually tells you whether the problem is permissions, chip detection, or file size.

## Runtime Files

The tool stores generated files in:

- `runtime/uploads/`
  uploaded `BIN` files
- `runtime/backups/`
  card backups
- `runtime/prepared/`
  prepared intermediate images that are actually written
- `runtime/state.json`
  saved UI state

Avoid deleting these files while the tool is running.

## Common Problems

### 1. `flashrom` is not available

Usually this means the tool cannot find `flashrom`. Check that:

- `brew install flashrom` completed successfully
- `flashrom` runs in your terminal

You can also point to it explicitly:

```bash
DIM_FLASHROM_BIN=/opt/homebrew/bin/flashrom ./start-web-ui.command
```

### 2. Permission or USB access errors

Common markers:

- `LIBUSB_ERROR_ACCESS`
- `root privilege`
- `Cannot detach the existing USB driver`

Try this:

1. Close any other app that may be using the `CH341A`.
2. Replug the programmer.
3. Restart with `sudo ./start-web-ui.command`.

This is usually a permission issue, not necessarily damaged card data.

### 3. Full BIN size does not match the current card

This means:

- the card capacity and your full image size are different
- or your file is not a `1MB payload`

Run `Probe current card size` first, then use a matching `2MB / 4MB / 8MB / 16MB` image.

### 4. Usage reset cannot find a valid `Tama Smart` header

This usually means:

- the current card is not a supported `Tama Smart / TamaSma` image
- the image contents are invalid
- the card contents may already be damaged

In that case, stop and make a full backup before trying more changes.

### 5. Usage reset succeeded, but write protection failed

This means usage was cleared, but future use may increment it again. Common reasons:

- the chip does not support the required write-protect commands
- `flashrom` has limited support for that chip

This does not necessarily mean the reset failed.

### 6. The default port is busy

The tool starts trying from `127.0.0.1:8765`. If that port range is occupied, choose another port:

```bash
DIM_PORT=9000 ./start-web-ui.command
```

Then open the URL printed by the tool.

## Optional Environment Variables

You can override settings like this:

```bash
DIM_PORT=9000 DIM_OPEN_BROWSER=0 ./start-web-ui.command
```

Useful variables:

- `DIM_PORT`
  web UI port
- `DIM_HOST`
  bind address, default `127.0.0.1`
- `DIM_OPEN_BROWSER`
  set to `0` to disable auto-open
- `DIM_FLASHROM_BIN`
  path to the `flashrom` executable
- `DIM_PROGRAMMER`
  programmer name, default `ch341a_spi`
- `DIM_CHIP`
  default chip definition, default `MX25L3205(A)`
- `DIM_FLASHROM_TIMEOUT`
  `flashrom` timeout in seconds
- `DIM_MANAGE_WRITE_PROTECT`
  set to `0` to skip write-protect management

## Local Asset Directory

The `tamasmart/` directory is a convenient place to store your own:

- card backups
- full images
- other local resources

It is ignored by Git by default.

## Safety Notes

Please keep these risks in mind:

- flashing and write-protect operations affect real hardware
- a bad image can make a card unusable
- compatibility outside the `Tamagotchi Smart` use case is not fully verified

The safest habits are:

1. Make a manual backup before the first operation on each card.
2. Probe capacity whenever you swap cards.
3. Only write images from sources you trust.
