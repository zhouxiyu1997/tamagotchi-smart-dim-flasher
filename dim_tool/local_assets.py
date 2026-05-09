from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .flash_service import (
    MAX_IMAGE_SIZE_BYTES,
    MIN_FULL_IMAGE_SIZE_BYTES,
    PAYLOAD_SIZE_BYTES,
    format_size_bytes,
)


@dataclass(frozen=True)
class LocalBinAsset:
    name: str
    path: Path
    relative_path: str
    size_bytes: int
    supported: bool
    size_mode: str
    size_note: str


def local_assets_dir(base_dir: Path) -> Path:
    return base_dir / "tamasmart"


def discover_local_bin_assets(base_dir: Path) -> list[LocalBinAsset]:
    assets_dir = local_assets_dir(base_dir)
    if not assets_dir.exists():
        return []

    assets: list[LocalBinAsset] = []
    for path in sorted(
        assets_dir.rglob("*.bin"),
        key=lambda item: str(item.relative_to(assets_dir)).casefold(),
    ):
        if not path.is_file():
            continue

        relative = path.relative_to(assets_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue

        size_bytes = path.stat().st_size
        size_mode, supported = classify_bin_size(size_bytes)
        assets.append(
            LocalBinAsset(
                name=path.name,
                path=path.resolve(),
                relative_path=relative.as_posix(),
                size_bytes=size_bytes,
                supported=supported,
                size_mode=size_mode,
                size_note=describe_bin_size(size_bytes),
            )
        )
    return assets


def classify_bin_size(size_bytes: int) -> tuple[str, bool]:
    if size_bytes == PAYLOAD_SIZE_BYTES:
        return "1MB payload", True
    if MIN_FULL_IMAGE_SIZE_BYTES <= size_bytes <= MAX_IMAGE_SIZE_BYTES:
        return "完整镜像", True
    return "不支持的大小", False


def describe_bin_size(size_bytes: int) -> str:
    size_label = format_size_bytes(size_bytes)
    size_mode, supported = classify_bin_size(size_bytes)
    if supported:
        return f"{size_mode} · {size_label}"
    return f"{size_mode} · {size_label}（仅支持 1MB 或 2MB-16MB）"


def local_asset_to_dict(asset: LocalBinAsset) -> dict[str, object]:
    return {
        "name": asset.name,
        "path": str(asset.path),
        "relativePath": asset.relative_path,
        "size": asset.size_bytes,
        "supported": asset.supported,
        "sizeMode": asset.size_mode,
        "sizeNote": asset.size_note,
    }
