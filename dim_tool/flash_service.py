from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MAX_IMAGE_SIZE_BYTES = 16 * 1024 * 1024
MIN_FULL_IMAGE_SIZE_BYTES = 2 * 1024 * 1024
PAYLOAD_SIZE_BYTES = 1 * 1024 * 1024
STANDARD_CHECKSUM_SPANS = (
    1 * 1024 * 1024,
    2 * 1024 * 1024,
    4 * 1024 * 1024,
    8 * 1024 * 1024,
    16 * 1024 * 1024,
)
SMART_CARD_SIGNATURE = b"BANDAINTPD_0_0_0TAMASUMA_TIM0000"
SMART_CARD_SIGNATURE_OFFSET = 16
SMART_CARD_USAGE_SLOTS = 3
SMART_CARD_USAGE_SLOT_SIZE = 4
SMART_CARD_HEADER_MD5_OFFSET = 64
SMART_CARD_HEADER_MD5_SIZE = 16
SMART_CARD_CONTENT_OFFSET = 4096


class FlashromError(RuntimeError):
    def __init__(self, message: str, log: str = "") -> None:
        super().__init__(message)
        self.log = log


@dataclass(frozen=True)
class PreparedImage:
    path: Path
    mode: str
    note: str
    image_changed: bool = False
    usage_count_before: int | None = None
    usage_count_after: int | None = None
    detected_card_size_bytes: int | None = None
    detected_segment_count: int | None = None
    detected_segment_size_bytes: int | None = None


@dataclass(frozen=True)
class WriteProtectResult:
    attempted: bool
    succeeded: bool
    enabled: bool
    log: str


@dataclass(frozen=True)
class DetectedFlashChip:
    name: str
    size_bytes: int
    log: str


@dataclass(frozen=True)
class TamaSmartSegment:
    start_offset: int
    size_bytes: int
    checksum_size_bytes: int
    usage_count: int


@dataclass(frozen=True)
class TamaSmartLayout:
    image_size_bytes: int
    segments: tuple[TamaSmartSegment, ...]


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
        self.manage_write_protect = os.environ.get("DIM_MANAGE_WRITE_PROTECT", "1") == "1"
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

    def _flashrom_cmd(self, *args: str, chip_override: str | None = None) -> list[str]:
        cmd = [self.flashrom_bin, "-p", self.programmer]
        chip = self.chip if chip_override is None else chip_override
        if chip and chip.lower() != "auto":
            cmd.extend(["-c", chip])
        cmd.extend(args)
        return cmd

    def run_flashrom(self, *args: str) -> str:
        ok, log, returncode = self.try_run_flashrom(*args)
        if not ok:
            raise FlashromError(
                f"flashrom exited with code {returncode}.",
                log=log,
            )
        return log

    def try_run_flashrom(self, *args: str) -> tuple[bool, str, int]:
        primary_cmd = self._flashrom_cmd(*args)
        primary_ok, primary_log, primary_returncode = self._run_flashrom_cmd(primary_cmd)

        if primary_ok:
            return primary_ok, primary_log, primary_returncode

        if not should_retry_flashrom_without_chip(self.chip, primary_log):
            return primary_ok, primary_log, primary_returncode

        fallback_cmd = self._flashrom_cmd(*args, chip_override="")
        fallback_ok, fallback_log, fallback_returncode = self._run_flashrom_cmd(fallback_cmd)
        combined_log = "\n\n".join(
            part
            for part in (
                f"指定芯片 `{self.chip}` 探测失败，已回退到 flashrom 自动识别。",
                "[Configured chip attempt]",
                primary_log,
                "[Auto-detect fallback]",
                fallback_log,
            )
            if part
        )
        return fallback_ok, combined_log, fallback_returncode

    def _run_flashrom_cmd(self, cmd: list[str]) -> tuple[bool, str, int]:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.command_timeout_seconds,
            check=False,
        )
        log = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part)
        return proc.returncode == 0, log, proc.returncode

    def probe_flash_chip(self) -> DetectedFlashChip:
        cmd = [self.flashrom_bin, "-p", self.programmer, "-V"]
        ok, log, returncode = self._run_flashrom_cmd(cmd)
        if not ok:
            raise FlashromError(
                f"flashrom chip probe exited with code {returncode}.",
                log=log,
            )

        chip = parse_detected_flash_chip(log)
        if chip is None:
            raise FlashromError(
                "flashrom 没有返回可解析的芯片型号/容量信息。",
                log=log,
            )
        return chip

    def run_flashrom_for_chip(self, chip_name: str, *args: str) -> str:
        cmd = self._flashrom_cmd(*args, chip_override=chip_name)
        ok, log, returncode = self._run_flashrom_cmd(cmd)
        if not ok:
            raise FlashromError(
                f"flashrom exited with code {returncode}.",
                log=log,
            )
        return log

    def backup_current_card(self, reason: str) -> tuple[Path, str]:
        detected_chip = self.probe_flash_chip()
        timestamp = timestamp_slug()
        backup_path = self.backups_dir / f"{timestamp}-{reason}.bin"
        read_log = self.run_flashrom_for_chip(detected_chip.name, "-r", str(backup_path))
        actual_size = backup_path.stat().st_size
        if actual_size != detected_chip.size_bytes:
            raise FlashromError(
                "flashrom 读出的备份大小和自动探测到的芯片容量不一致。"
                f" 探测容量是 {format_size_bytes(detected_chip.size_bytes)}，"
                f" 但备份文件是 {format_size_bytes(actual_size)}。",
                log="\n\n".join(
                    [
                        "[Chip probe]",
                        detected_chip.log,
                        "[Read backup]",
                        read_log,
                    ]
                ),
            )
        log = "\n\n".join(
            [
                "[Chip probe]",
                detected_chip.log,
                "[Read backup]",
                read_log,
            ]
        )
        return backup_path, log

    def write_image(self, image_path: Path) -> str:
        detected_chip = self.probe_flash_chip()
        image_size = image_path.stat().st_size
        if image_size != detected_chip.size_bytes:
            raise FlashromError(
                "待写入镜像的大小和当前卡自动探测到的芯片容量不一致。"
                f" 卡容量是 {format_size_bytes(detected_chip.size_bytes)}，"
                f" 镜像大小是 {format_size_bytes(image_size)}。",
                log=detected_chip.log,
            )

        preflight_logs: list[str] = []
        preflight_logs_for_errors: list[str] = []
        preflight_logs.extend(["[Chip probe]", detected_chip.log])
        preflight_logs_for_errors.extend(["[Chip probe]", detected_chip.log])

        disable_result = self.set_write_protect(False, chip_name=detected_chip.name)
        if disable_result.attempted and disable_result.log:
            preflight_logs_for_errors.extend(["[Disable write protection]", disable_result.log])
            if disable_result.succeeded:
                preflight_logs.extend(["[Disable write protection]", disable_result.log])

        try:
            write_log = self.run_flashrom_for_chip(detected_chip.name, "-w", str(image_path))
        except FlashromError as exc:
            combined_log = "\n\n".join(preflight_logs_for_errors + ([exc.log] if exc.log else []))
            raise FlashromError(str(exc), combined_log) from exc

        return "\n\n".join(preflight_logs + [write_log])

    def set_write_protect(
        self,
        enabled: bool,
        size_bytes: int | None = None,
        chip_name: str | None = None,
    ) -> WriteProtectResult:
        if not self.manage_write_protect:
            return WriteProtectResult(
                attempted=False,
                succeeded=False,
                enabled=False,
                log="写保护管理已关闭。将跳过 flashrom 写保护命令。",
            )

        args: list[str] = []
        if enabled:
            if size_bytes is not None:
                args.append(f"--wp-range=0,{size_bytes}")
            args.append("--wp-enable")
        else:
            args.append("--wp-disable")

        probe_log = ""
        if chip_name is None:
            try:
                detected_chip = self.probe_flash_chip()
                chip_name = detected_chip.name
                probe_log = detected_chip.log
            except FlashromError:
                chip_name = None

        if chip_name:
            cmd = self._flashrom_cmd(*args, chip_override=chip_name)
            ok, log, _returncode = self._run_flashrom_cmd(cmd)
            if probe_log:
                log = "\n\n".join(part for part in ("[Chip probe]", probe_log, log) if part)
        else:
            ok, log, _returncode = self.try_run_flashrom(*args)
        if ok:
            return WriteProtectResult(
                attempted=True,
                succeeded=True,
                enabled=enabled,
                log=log,
            )

        action = "启用" if enabled else "关闭"
        details = log or "flashrom 没有返回更多信息。"
        return WriteProtectResult(
            attempted=True,
            succeeded=False,
            enabled=False,
            log=f"{action}写保护失败。\n{details}",
        )

    def prepare_image(self, source_path: Path, backup_path: Path) -> PreparedImage:
        source_size = source_path.stat().st_size
        backup_size = backup_path.stat().st_size
        timestamp = timestamp_slug()
        prepared_path = self.prepared_dir / f"{timestamp}-{source_path.stem}-prepared.bin"

        if source_size == backup_size:
            shutil.copyfile(source_path, prepared_path)
            return PreparedImage(
                path=prepared_path,
                mode="full-card-image",
                note=f"完整 BIN 将按当前卡容量整片写入（{format_size_bytes(source_size)}）。",
                image_changed=True,
                detected_card_size_bytes=backup_size,
            )

        if source_size == PAYLOAD_SIZE_BYTES:
            if backup_size < PAYLOAD_SIZE_BYTES:
                raise FlashromError("当前卡容量小于 1MB，无法合并 Tama Smart payload。")
            shutil.copyfile(backup_path, prepared_path)
            with source_path.open("rb") as source_file:
                payload = source_file.read()
            with prepared_path.open("r+b") as prepared_file:
                prepared_file.seek(0)
                prepared_file.write(payload)
            return PreparedImage(
                path=prepared_path,
                mode="merge-1mb-into-current-card",
                note=(
                    "1MB BIN 会写入前 1MB，剩余区域保留自当前卡备份"
                    f"（当前卡容量 {format_size_bytes(backup_size)}）。"
                ),
                image_changed=True,
                detected_card_size_bytes=backup_size,
            )

        raise FlashromError(
            "上传的完整 BIN 与当前卡容量不匹配。"
            f" 当前卡是 {format_size_bytes(backup_size)}，"
            f" 上传文件是 {format_size_bytes(source_size)}。"
            " 请选择 1MB payload，或与当前卡容量一致的完整镜像。"
        )

    def prepare_usage_reset_image(self, source_path: Path) -> PreparedImage:
        payload = source_path.read_bytes()
        layout = analyze_tamasma_image(payload)
        usage_count_before = smart_card_usage_count(layout)

        timestamp = timestamp_slug()
        prepared_path = self.prepared_dir / f"{timestamp}-{source_path.stem}-usage-reset.bin"
        prepared_bytes = clear_tamasma_usages(payload, layout)
        prepared_path.write_bytes(prepared_bytes)
        prepared_layout = analyze_tamasma_image(prepared_bytes)

        return PreparedImage(
            path=prepared_path,
            mode="clear-smart-card-usages",
            note=(
                "保留当前卡内容，扫描整张卡里的 Tama Smart 头，"
                "清空每个镜像段的使用次数槽并重算校验。"
                f" 检测到 {describe_tamasma_layout(layout)}。"
            ),
            image_changed=prepared_bytes != payload,
            usage_count_before=usage_count_before,
            usage_count_after=smart_card_usage_count(prepared_layout),
            detected_card_size_bytes=layout.image_size_bytes,
            detected_segment_count=len(layout.segments),
            detected_segment_size_bytes=layout.segments[0].size_bytes,
        )


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


def is_tamasma_image(data: bytes) -> bool:
    try:
        analyze_tamasma_image(data)
    except FlashromError:
        return False
    return True


def analyze_tamasma_image(data: bytes) -> TamaSmartLayout:
    matches = find_valid_tamasma_segments(data)
    if not matches:
        raise FlashromError(
            "当前镜像里没有找到有效的 Tama Smart / TamaSma Card 头。"
        )
    return TamaSmartLayout(
        image_size_bytes=len(data),
        segments=tuple(matches),
    )


def find_valid_tamasma_segments(data: bytes) -> list[TamaSmartSegment]:
    matches: list[TamaSmartSegment] = []
    header_starts: list[int] = []
    search_from = 0

    while True:
        signature_offset = data.find(SMART_CARD_SIGNATURE, search_from)
        if signature_offset < 0:
            break
        header_start = signature_offset - SMART_CARD_SIGNATURE_OFFSET
        if header_start >= 0 and has_valid_tamasma_header_md5(data, header_start):
            header_starts.append(header_start)
        search_from = signature_offset + 1

    unique_starts = sorted(set(header_starts))
    for index, start_offset in enumerate(unique_starts):
        end_offset = unique_starts[index + 1] if index + 1 < len(unique_starts) else len(data)
        segment = data[start_offset:end_offset]
        if len(segment) < SMART_CARD_CONTENT_OFFSET:
            continue
        checksum_size_bytes = detect_tamasma_checksum_span(segment)
        if checksum_size_bytes is None:
            continue
        matches.append(
            TamaSmartSegment(
                start_offset=start_offset,
                size_bytes=end_offset - start_offset,
                checksum_size_bytes=checksum_size_bytes,
                usage_count=usage_count_from_segment(segment),
            )
        )
    return matches


def smart_card_usage_count(layout: TamaSmartLayout) -> int:
    if not layout.segments:
        raise FlashromError("没有找到可读取 usage 的 Tama Smart 镜像段。")
    return max(segment.usage_count for segment in layout.segments)


def clear_tamasma_usages(data: bytes, layout: TamaSmartLayout | None = None) -> bytes:
    current_layout = layout or analyze_tamasma_image(data)
    rebuilt = bytearray(data)

    for segment in current_layout.segments:
        clear_tamasma_usage_segment(
            rebuilt,
            segment.start_offset,
            segment.size_bytes,
            segment.checksum_size_bytes,
        )

    return bytes(rebuilt)


def clear_tamasma_usage_segment(
    buffer: bytearray,
    start_offset: int,
    size_bytes: int,
    checksum_size_bytes: int,
) -> None:
    end_offset = start_offset + size_bytes
    if end_offset > len(buffer):
        raise FlashromError("Tama Smart 镜像段超出了当前卡镜像范围。")

    usage_start = start_offset + 4
    usage_end = usage_start + SMART_CARD_USAGE_SLOTS * SMART_CARD_USAGE_SLOT_SIZE
    buffer[usage_start:usage_end] = b"\x00" * (usage_end - usage_start)

    checksum_start = start_offset + SMART_CARD_CONTENT_OFFSET
    checksum_end = start_offset + checksum_size_bytes
    if checksum_end > end_offset:
        raise FlashromError("Tama Smart 镜像段的 checksum 范围超出了该段长度。")
    checksum = smart_card_checksum(buffer[checksum_start:checksum_end])
    buffer[start_offset + 2 : start_offset + 4] = checksum.to_bytes(2, "little")

    header_end = start_offset + SMART_CARD_HEADER_MD5_OFFSET
    md5_start = header_end
    md5_end = md5_start + SMART_CARD_HEADER_MD5_SIZE
    header_md5 = hashlib.md5(buffer[start_offset:header_end]).digest()
    buffer[md5_start:md5_end] = header_md5


def usage_count_from_segment(segment: bytes) -> int:
    if len(segment) < 16:
        raise FlashromError("卡镜像段太小，无法读取使用次数。")
    usage_count = 0
    for slot_index in range(SMART_CARD_USAGE_SLOTS):
        offset = 4 + slot_index * SMART_CARD_USAGE_SLOT_SIZE
        value = int.from_bytes(segment[offset : offset + SMART_CARD_USAGE_SLOT_SIZE], "little")
        if value != 0:
            usage_count += 1
    return usage_count


def has_valid_tamasma_header_md5(data: bytes, start_offset: int) -> bool:
    md5_start = start_offset + SMART_CARD_HEADER_MD5_OFFSET
    md5_end = md5_start + SMART_CARD_HEADER_MD5_SIZE
    if start_offset < 0 or md5_end > len(data):
        return False
    expected = data[md5_start:md5_end]
    actual = hashlib.md5(data[start_offset:md5_start]).digest()
    return actual == expected


def detect_tamasma_checksum_span(segment: bytes) -> int | None:
    if len(segment) < SMART_CARD_CONTENT_OFFSET:
        return None

    stored_checksum = int.from_bytes(segment[2:4], "little")
    candidates: list[int] = []
    for candidate in STANDARD_CHECKSUM_SPANS:
        if SMART_CARD_CONTENT_OFFSET <= candidate <= len(segment):
            candidates.append(candidate)
    if len(segment) not in candidates:
        candidates.append(len(segment))

    for candidate in candidates:
        actual_checksum = smart_card_checksum(segment[SMART_CARD_CONTENT_OFFSET:candidate])
        if stored_checksum == actual_checksum:
            return candidate
    return None


def describe_tamasma_layout(layout: TamaSmartLayout) -> str:
    segment_count = len(layout.segments)
    segment_sizes = sorted({segment.size_bytes for segment in layout.segments})
    checksum_sizes = sorted({segment.checksum_size_bytes for segment in layout.segments})
    if len(segment_sizes) == 1:
        segment_text = format_size_bytes(segment_sizes[0])
    else:
        segment_text = " / ".join(format_size_bytes(size) for size in segment_sizes)
    if len(checksum_sizes) == 1:
        checksum_text = format_size_bytes(checksum_sizes[0])
    else:
        checksum_text = " / ".join(format_size_bytes(size) for size in checksum_sizes)
    return (
        f"{segment_count} 个镜像段，总容量 {format_size_bytes(layout.image_size_bytes)}，"
        f" 每段容量 {segment_text}，checksum 范围 {checksum_text}"
    )


def smart_card_checksum(payload: bytes) -> int:
    checksum = 0
    for index, value in enumerate(payload):
        checksum += value << (8 * (index % 2))
    return checksum & 0xFFFF


def format_size_bytes(size: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    unit_index = 0
    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1
    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"
    return f"{value:.2f} {units[unit_index]}"


def parse_detected_flash_chip(log: str) -> DetectedFlashChip | None:
    match = re.search(
        r'Found .* flash chip "([^"]+)" \((\d+) (B|kB|MB), SPI\)\.',
        log,
    )
    if not match:
        return None

    chip_name = match.group(1)
    size_value = int(match.group(2))
    size_unit = match.group(3)
    multiplier = {
        "B": 1,
        "kB": 1024,
        "MB": 1024 * 1024,
    }[size_unit]
    return DetectedFlashChip(
        name=chip_name,
        size_bytes=size_value * multiplier,
        log=log,
    )


def flashrom_permission_hint(log: str) -> str | None:
    lowered = log.lower()
    permission_markers = (
        "libusb_error_access",
        "root privilege",
        "cannot detach the existing usb driver",
        "no capture entitlements",
    )
    if any(marker in lowered for marker in permission_markers):
        return (
            "flashrom 没有权限接管 CH341A / USB 设备。"
            " 在 macOS 上这通常不是卡内容问题，而是权限问题。"
            " 请关闭可能占用 CH341A 的程序，重新插拔一次，然后用 root 权限启动本工具，"
            " 例如在仓库目录执行 `sudo ./start-web-ui.command`，再重试。"
        )
    return None


def should_retry_flashrom_without_chip(chip: str, log: str) -> bool:
    if not chip or chip.lower() == "auto":
        return False
    lowered = log.lower()
    retry_markers = (
        "no eeprom/flash device found",
        "multiple flash chip definitions match the detected chip",
    )
    if "libusb_error_access" in lowered:
        return False
    return any(marker in lowered for marker in retry_markers)
