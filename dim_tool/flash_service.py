from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CARD_SIZE_BYTES = 4 * 1024 * 1024
PAYLOAD_SIZE_BYTES = 1 * 1024 * 1024


class FlashromError(RuntimeError):
    def __init__(self, message: str, log: str = "") -> None:
        super().__init__(message)
        self.log = log


@dataclass(frozen=True)
class PreparedImage:
    path: Path
    mode: str
    note: str


class FlashService:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.runtime_dir = base_dir / "runtime"
        self.uploads_dir = self.runtime_dir / "uploads"
        self.backups_dir = self.runtime_dir / "backups"
        self.prepared_dir = self.runtime_dir / "prepared"
        self.state_file = self.runtime_dir / "state.json"
        self.flashrom_bin = os.environ.get("DIM_FLASHROM_BIN", "flashrom")
        self.programmer = os.environ.get("DIM_PROGRAMMER", "ch341a_spi")
        self.chip = os.environ.get("DIM_CHIP", "MX25L3205(A)")
        self.command_timeout_seconds = int(os.environ.get("DIM_FLASHROM_TIMEOUT", "900"))
        self.ensure_dirs()

    def ensure_dirs(self) -> None:
        self.runtime_dir.mkdir(exist_ok=True)
        self.uploads_dir.mkdir(exist_ok=True)
        self.backups_dir.mkdir(exist_ok=True)
        self.prepared_dir.mkdir(exist_ok=True)

    def flashrom_available(self) -> bool:
        if Path(self.flashrom_bin).is_file():
            return True
        return shutil.which(self.flashrom_bin) is not None

    def run_flashrom(self, *args: str) -> str:
        cmd = [self.flashrom_bin, "-p", self.programmer, "-c", self.chip, *args]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.command_timeout_seconds,
            check=False,
        )
        log = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part)
        if proc.returncode != 0:
            raise FlashromError(
                f"flashrom exited with code {proc.returncode}.",
                log=log,
            )
        return log

    def backup_current_card(self, reason: str) -> tuple[Path, str]:
        timestamp = timestamp_slug()
        backup_path = self.backups_dir / f"{timestamp}-{reason}.bin"
        log = self.run_flashrom("-r", str(backup_path))
        return backup_path, log

    def write_image(self, image_path: Path) -> str:
        return self.run_flashrom("-w", str(image_path))

    def prepare_image(self, source_path: Path, backup_path: Path) -> PreparedImage:
        source_size = source_path.stat().st_size
        timestamp = timestamp_slug()
        prepared_path = self.prepared_dir / f"{timestamp}-{source_path.stem}-prepared.bin"

        if source_size == CARD_SIZE_BYTES:
            shutil.copyfile(source_path, prepared_path)
            return PreparedImage(
                path=prepared_path,
                mode="full-4mb",
                note="4MB BIN 将整片原样写入。",
            )

        if source_size == PAYLOAD_SIZE_BYTES:
            shutil.copyfile(backup_path, prepared_path)
            with source_path.open("rb") as source_file:
                payload = source_file.read()
            with prepared_path.open("r+b") as prepared_file:
                prepared_file.seek(0)
                prepared_file.write(payload)
            return PreparedImage(
                path=prepared_path,
                mode="merge-1mb-into-4mb",
                note="1MB BIN 会写入前 1MB，后 3MB 保留自最新备份。",
            )

        raise FlashromError("目前只支持 1MB 或 4MB 的 BIN 文件。")


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sha256_for_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def file_info(path: Path) -> dict[str, object]:
    return {
        "name": path.name,
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256_for_file(path),
    }
