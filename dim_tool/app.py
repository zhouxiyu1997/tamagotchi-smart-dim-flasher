from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .flash_service import (
    MAX_IMAGE_SIZE_BYTES,
    MIN_FULL_IMAGE_SIZE_BYTES,
    PAYLOAD_SIZE_BYTES,
    FlashService,
    FlashromError,
    file_info,
    flashrom_permission_hint,
    format_size_bytes,
    iso_now,
)

BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "runtime" / "state.json"
MAX_HISTORY = 20

flash_service = FlashService(BASE_DIR)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_SIZE_BYTES + 1024

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/state")
    def api_state():
        return jsonify({"ok": True, "state": public_state()})

    @app.post("/api/upload")
    def api_upload():
        upload = request.files.get("bin_file")
        if upload is None or not upload.filename:
            return error_response("请先选择一个 BIN 文件。", 400)

        saved_path = flash_service.uploads_dir / unique_upload_name(upload.filename)
        upload.save(saved_path)

        try:
            validate_bin_size(saved_path)
        except FlashromError as exc:
            saved_path.unlink(missing_ok=True)
            return error_response(str(exc), 400)

        state = load_state()
        upload_entry = entry_with_time(file_info(saved_path), "uploaded_at")
        state["latest_upload"] = upload_entry
        push_history(state, "uploads", upload_entry)
        save_state(state)

        try:
            backup_path, backup_log = flash_service.backup_current_card(f"upload-{saved_path.stem}")
        except FlashromError as exc:
            save_state(state)
            message = "BIN 已上传，但自动备份当前卡失败。"
            return error_response(message, 500, exc.log)

        backup_entry = entry_with_time(file_info(backup_path), "created_at", reason="auto-backup-after-upload")
        state["latest_backup"] = backup_entry
        push_history(state, "backups", backup_entry)
        save_state(state)

        return jsonify(
            {
                "ok": True,
                "message": "BIN 上传成功，当前卡也已完成备份。",
                "log": backup_log,
                "state": public_state(),
            }
        )

    @app.post("/api/backup")
    def api_backup():
        try:
            backup_path, backup_log = flash_service.backup_current_card("manual-backup")
        except FlashromError as exc:
            return error_response("手动备份失败。", 500, exc.log)

        state = load_state()
        backup_entry = entry_with_time(file_info(backup_path), "created_at", reason="manual")
        state["latest_backup"] = backup_entry
        push_history(state, "backups", backup_entry)
        save_state(state)

        return jsonify(
            {
                "ok": True,
                "message": "当前卡备份完成。",
                "log": backup_log,
                "state": public_state(),
            }
        )

    @app.post("/api/install")
    def api_install():
        state = load_state()
        latest_upload = state.get("latest_upload")
        if not latest_upload:
            return error_response("请先上传要安装的 BIN 文件。", 400)

        source_path = Path(str(latest_upload["path"]))
        if not source_path.exists():
            return error_response("找不到刚才上传的 BIN 文件。", 400)

        try:
            fresh_backup_path, fresh_backup_log = flash_service.backup_current_card(f"pre-install-{source_path.stem}")
            prepared = flash_service.prepare_image(source_path, fresh_backup_path)
            write_log = flash_service.write_image(prepared.path)
        except FlashromError as exc:
            return error_response("安装失败。", 500, exc.log)

        backup_entry = entry_with_time(file_info(fresh_backup_path), "created_at", reason="pre-install")
        state["latest_backup"] = backup_entry
        push_history(state, "backups", backup_entry)

        latest_flash = {
            "flashed_at": iso_now(),
            "mode": prepared.mode,
            "note": prepared.note,
            "source": file_info(source_path),
            "written_image": file_info(prepared.path),
            "detectedCardSizeBytes": prepared.detected_card_size_bytes,
        }
        state["latest_flash"] = latest_flash
        push_history(state, "flashes", latest_flash)
        save_state(state)

        combined_log = "\n\n".join(
            [
                "[Backup before install]",
                fresh_backup_log,
                "[Write and verify]",
                write_log,
            ]
        )
        return jsonify(
            {
                "ok": True,
                "message": "安装完成，校验也已通过。",
                "log": combined_log,
                "state": public_state(),
            }
        )

    @app.post("/api/restore")
    def api_restore():
        state = load_state()
        latest_backup = state.get("latest_backup")
        if not latest_backup:
            return error_response("还没有可用的备份。", 400)

        backup_path = Path(str(latest_backup["path"]))
        if not backup_path.exists():
            return error_response("找不到最近一次备份文件。", 400)

        try:
            write_log = flash_service.write_image(backup_path)
        except FlashromError as exc:
            return error_response("复原失败。", 500, exc.log)

        latest_restore = {
            "restored_at": iso_now(),
            "source": file_info(backup_path),
        }
        state["latest_restore"] = latest_restore
        push_history(state, "restores", latest_restore)
        save_state(state)

        return jsonify(
            {
                "ok": True,
                "message": "最近备份已经复原，校验也已通过。",
                "log": write_log,
                "state": public_state(),
            }
        )

    @app.post("/api/reset-usage")
    def api_reset_usage():
        try:
            backup_path, backup_log = flash_service.backup_current_card("pre-usage-reset")
            prepared = flash_service.prepare_usage_reset_image(backup_path)
        except FlashromError as exc:
            return error_response("读取当前卡或分析使用次数失败。", 500, exc.log)

        state = load_state()
        backup_entry = entry_with_time(
            file_info(backup_path),
            "created_at",
            reason="pre-usage-reset",
        )
        state["latest_backup"] = backup_entry
        push_history(state, "backups", backup_entry)
        save_state(state)

        combined_log_parts = [
            "[Backup before usage reset]",
            backup_log,
        ]

        usage_count_before = prepared.usage_count_before or 0
        wrote_reset_image = prepared.image_changed
        if wrote_reset_image:
            try:
                write_log = flash_service.write_image(prepared.path)
            except FlashromError as exc:
                return error_response("使用次数镜像已经生成，但写回当前卡失败。", 500, exc.log)
            combined_log_parts.extend(["[Write reset image]", write_log])

        write_protect_result = flash_service.set_write_protect(
            True,
            prepared.path.stat().st_size,
        )
        if write_protect_result.log:
            combined_log_parts.extend(["[Write protection]", write_protect_result.log])

        note = prepared.note
        if write_protect_result.enabled:
            note = f"{note} 已启用整片写保护，后续应不再累计使用次数。"
        elif write_protect_result.attempted:
            note = f"{note} 但写保护没有成功启用，后续仍可能再次累计使用次数。"
        else:
            note = f"{note} 当前配置跳过了写保护步骤。"

        latest_flash = {
            "flashed_at": iso_now(),
            "mode": prepared.mode,
            "note": note,
            "source": file_info(backup_path),
            "written_image": file_info(prepared.path),
            "usageCountBefore": prepared.usage_count_before,
            "usageCountAfter": prepared.usage_count_after,
            "writeProtectionEnabled": write_protect_result.enabled,
            "detectedCardSizeBytes": prepared.detected_card_size_bytes,
            "detectedSegmentCount": prepared.detected_segment_count,
            "detectedSegmentSizeBytes": prepared.detected_segment_size_bytes,
        }
        state["latest_flash"] = latest_flash
        push_history(state, "flashes", latest_flash)
        save_state(state)

        if wrote_reset_image and usage_count_before > 0 and write_protect_result.enabled:
            message = "当前卡使用次数已清零，并已启用写保护。"
        elif wrote_reset_image and usage_count_before > 0:
            message = "当前卡使用次数已清零，但写保护未成功启用。"
        elif wrote_reset_image and write_protect_result.enabled:
            message = "当前卡头部校验已修正，并已启用写保护。"
        elif wrote_reset_image:
            message = "当前卡头部校验已修正，但写保护未成功启用。"
        elif write_protect_result.enabled:
            message = "当前卡使用次数本来就是 0，现已补上写保护。"
        else:
            message = "当前卡使用次数本来就是 0，但写保护未成功启用。"

        combined_log = "\n\n".join(part for part in combined_log_parts if part)
        return jsonify(
            {
                "ok": True,
                "message": message,
                "log": combined_log,
                "state": public_state(),
            }
        )

    @app.errorhandler(413)
    def request_too_large(_error):
        return error_response(
            "BIN 文件太大了，目前只支持 1MB payload，或不超过 16MB 的完整镜像。",
            413,
        )

    return app


def default_state() -> dict[str, object]:
    return {
        "latest_upload": None,
        "latest_backup": None,
        "latest_flash": None,
        "latest_restore": None,
        "uploads": [],
        "backups": [],
        "flashes": [],
        "restores": [],
    }


def load_state() -> dict[str, object]:
    if not STATE_PATH.exists():
        return default_state()
    with STATE_PATH.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def save_state(state: dict[str, object]) -> None:
    flash_service.ensure_dirs()
    with STATE_PATH.open("w", encoding="utf-8") as file_obj:
        json.dump(state, file_obj, ensure_ascii=False, indent=2)


def push_history(state: dict[str, object], key: str, entry: dict[str, object]) -> None:
    items = list(state.get(key, []))
    items.insert(0, entry)
    state[key] = items[:MAX_HISTORY]


def entry_with_time(base: dict[str, object], time_key: str, **extra: object) -> dict[str, object]:
    entry = dict(base)
    entry[time_key] = iso_now()
    entry.update(extra)
    return entry


def unique_upload_name(original_name: str) -> str:
    cleaned = Path(original_name).name.replace("\x00", "")
    if cleaned in {"", ".", ".."}:
        cleaned = "uploaded.bin"
    return f"{iso_now().replace(':', '-')}-{cleaned}"


def validate_bin_size(path: Path) -> None:
    size = path.stat().st_size
    if size == PAYLOAD_SIZE_BYTES:
        return
    if MIN_FULL_IMAGE_SIZE_BYTES <= size <= MAX_IMAGE_SIZE_BYTES:
        return
    raise FlashromError(
        "目前支持 1MB payload，或 2MB 到 16MB 之间的完整镜像。"
    )


def public_state() -> dict[str, object]:
    state = load_state()
    latest_backup = state.get("latest_backup")
    detected_card_size_bytes = None
    if isinstance(latest_backup, dict):
        detected_card_size_bytes = latest_backup.get("size")
    return {
        "config": {
            "flashromAvailable": flash_service.flashrom_available(),
            "flashromBin": flash_service.flashrom_bin,
            "programmer": flash_service.programmer,
            "chip": f"{flash_service.chip}（失败时自动回退到 flashrom 自检）",
            "payloadSizeBytes": PAYLOAD_SIZE_BYTES,
            "fullImageRange": (
                f"{format_size_bytes(MIN_FULL_IMAGE_SIZE_BYTES)}"
                f" - {format_size_bytes(MAX_IMAGE_SIZE_BYTES)}"
            ),
            "detectedCardSizeBytes": detected_card_size_bytes,
        },
        "latestUpload": state.get("latest_upload"),
        "latestBackup": state.get("latest_backup"),
        "latestFlash": state.get("latest_flash"),
        "latestRestore": state.get("latest_restore"),
        "recentBackups": state.get("backups", [])[:5],
        "runtimeDir": str(flash_service.runtime_dir),
    }


def error_response(message: str, status: int, log: str = ""):
    hint = flashrom_permission_hint(log) if log else None
    if hint:
        message = f"{message}\n\n{hint}"
    return (
        jsonify(
            {
                "ok": False,
                "message": message,
                "log": log,
                "state": public_state(),
            }
        ),
        status,
    )
