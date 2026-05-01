const uploadForm = document.getElementById("upload-form");
const uploadButton = document.getElementById("upload-button");
const installButton = document.getElementById("install-button");
const backupButton = document.getElementById("backup-button");
const resetUsageButton = document.getElementById("reset-usage-button");
const restoreButton = document.getElementById("restore-button");
const logOutput = document.getElementById("log-output");
const statusPill = document.getElementById("status-pill");
const uploadMeta = document.getElementById("upload-meta");
const backupMeta = document.getElementById("backup-meta");
const flashMeta = document.getElementById("flash-meta");
const restoreMeta = document.getElementById("restore-meta");
const serviceMeta = document.getElementById("service-meta");

let currentState = null;

function formatBytes(size) {
  if (size == null) return "Unknown";
  const units = ["B", "KB", "MB", "GB"];
  let value = size;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`;
}

function setBusy(message, isError = false) {
  statusPill.textContent = message;
  statusPill.classList.toggle("error", isError);
}

function setButtonsDisabled(disabled) {
  uploadButton.disabled = disabled;
  installButton.disabled = disabled || !currentState?.latestUpload;
  backupButton.disabled = disabled;
  resetUsageButton.disabled = disabled;
  restoreButton.disabled = disabled || !currentState?.latestBackup;
}

function metaBlock(label, value) {
  return `
    <div class="meta-item">
      <span class="meta-label">${label}</span>
      <div class="meta-value">${value}</div>
    </div>
  `;
}

function renderMeta(target, blocks, emptyText) {
  if (!blocks.length) {
    target.classList.add("empty");
    target.innerHTML = emptyText;
    return;
  }
  target.classList.remove("empty");
  target.innerHTML = blocks.join("");
}

function renderState(state) {
  currentState = state;

  const upload = state.latestUpload;
  const backup = state.latestBackup;
  const flash = state.latestFlash;
  const restore = state.latestRestore;
  const config = state.config;

  renderMeta(
    uploadMeta,
    upload
      ? [
          metaBlock("文件名", upload.name),
          metaBlock("大小", formatBytes(upload.size)),
          metaBlock("上传时间", upload.uploaded_at),
          metaBlock("SHA-256", upload.sha256),
        ]
      : [],
    "还没有上传 BIN。"
  );

  renderMeta(
    backupMeta,
    backup
      ? [
          metaBlock("备份文件", backup.name),
          metaBlock("大小", formatBytes(backup.size)),
          metaBlock("备份时间", backup.created_at),
          metaBlock("用途", backup.reason || "automatic"),
          metaBlock("SHA-256", backup.sha256),
        ]
      : [],
    "还没有备份记录。"
  );

  const flashBlocks = [];
  if (flash) {
    flashBlocks.push(metaBlock("最近刷写", flash.flashed_at));
    flashBlocks.push(metaBlock("模式", flash.mode));
    flashBlocks.push(metaBlock("说明", flash.note));
    flashBlocks.push(metaBlock("来源 BIN", flash.source.name));
    if (flash.detectedCardSizeBytes != null) {
      flashBlocks.push(metaBlock("检测到卡容量", formatBytes(flash.detectedCardSizeBytes)));
    }
    if (flash.detectedSegmentCount != null) {
      flashBlocks.push(metaBlock("检测到镜像段", String(flash.detectedSegmentCount)));
    }
    if (flash.detectedSegmentSizeBytes != null) {
      flashBlocks.push(metaBlock("每段容量", formatBytes(flash.detectedSegmentSizeBytes)));
    }
    if (flash.usageCountBefore != null) {
      flashBlocks.push(metaBlock("清零前次数", String(flash.usageCountBefore)));
    }
    if (flash.usageCountAfter != null) {
      flashBlocks.push(metaBlock("清零后次数", String(flash.usageCountAfter)));
    }
  }
  if (restore) {
    flashBlocks.push(metaBlock("最近复原", restore.restored_at));
    flashBlocks.push(metaBlock("复原来源", restore.source.name));
  }
  renderMeta(flashMeta, flashBlocks, "还没有刷写或复原记录。");

  renderMeta(
    restoreMeta,
    backup
      ? [
          metaBlock("将写回", backup.name),
          metaBlock("备份位置", backup.path),
        ]
      : [],
    "还没有可复原的备份。"
  );

  renderMeta(
    serviceMeta,
    [
      metaBlock("flashrom", config.flashromBin),
      metaBlock("程序器", config.programmer),
      metaBlock("芯片定义", config.chip),
      metaBlock("最近检测卡容量", config.detectedCardSizeBytes != null ? formatBytes(config.detectedCardSizeBytes) : "尚未检测"),
      metaBlock("Payload 容量", formatBytes(config.payloadSizeBytes)),
      metaBlock("完整镜像范围", config.fullImageRange),
      metaBlock("运行目录", state.runtimeDir),
      metaBlock("工具状态", config.flashromAvailable ? "已找到 flashrom" : "未找到 flashrom"),
    ],
    ""
  );

  installButton.disabled = !upload;
  restoreButton.disabled = !backup;
}

async function fetchState() {
  const response = await fetch("/api/state");
  const data = await response.json();
  renderState(data.state);
  setBusy("就绪");
  setButtonsDisabled(false);
}

async function post(url, body = null) {
  const options = { method: "POST" };
  if (body) {
    options.body = body;
  }
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw data;
  }
  return data;
}

function writeLog(message, log = "") {
  logOutput.textContent = log ? `${message}\n\n${log}` : message;
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("bin-file");
  if (!fileInput.files.length) {
    writeLog("请选择一个 BIN 文件。");
    return;
  }

  const formData = new FormData();
  formData.append("bin_file", fileInput.files[0]);

  setBusy("上传并备份中…");
  setButtonsDisabled(true);

  try {
    const data = await post("/api/upload", formData);
    renderState(data.state);
    writeLog(data.message, data.log);
    setBusy("上传完成");
  } catch (error) {
    renderState(error.state || currentState);
    writeLog(error.message || "上传失败。", error.log || "");
    setBusy("上传失败", true);
  } finally {
    setButtonsDisabled(false);
  }
});

installButton.addEventListener("click", async () => {
  if (!currentState?.latestUpload) {
    return;
  }
  const confirmed = window.confirm("安装会先重新备份当前卡，然后写入最新上传的 BIN。继续吗？");
  if (!confirmed) {
    return;
  }

  setBusy("安装中…");
  setButtonsDisabled(true);
  try {
    const data = await post("/api/install");
    renderState(data.state);
    writeLog(data.message, data.log);
    setBusy("安装完成");
  } catch (error) {
    renderState(error.state || currentState);
    writeLog(error.message || "安装失败。", error.log || "");
    setBusy("安装失败", true);
  } finally {
    setButtonsDisabled(false);
  }
});

backupButton.addEventListener("click", async () => {
  setBusy("备份中…");
  setButtonsDisabled(true);
  try {
    const data = await post("/api/backup");
    renderState(data.state);
    writeLog(data.message, data.log);
    setBusy("备份完成");
  } catch (error) {
    renderState(error.state || currentState);
    writeLog(error.message || "备份失败。", error.log || "");
    setBusy("备份失败", true);
  } finally {
    setButtonsDisabled(false);
  }
});

resetUsageButton.addEventListener("click", async () => {
  const confirmed = window.confirm("这会先备份当前卡，再把当前内容的使用次数清零，并尽量启用写保护。继续吗？");
  if (!confirmed) {
    return;
  }

  setBusy("重置使用次数中…");
  setButtonsDisabled(true);
  try {
    const data = await post("/api/reset-usage");
    renderState(data.state);
    writeLog(data.message, data.log);
    setBusy("重置完成");
  } catch (error) {
    renderState(error.state || currentState);
    writeLog(error.message || "重置使用次数失败。", error.log || "");
    setBusy("重置失败", true);
  } finally {
    setButtonsDisabled(false);
  }
});

restoreButton.addEventListener("click", async () => {
  if (!currentState?.latestBackup) {
    return;
  }
  const confirmed = window.confirm("这会把当前卡恢复成最近一次备份的内容。继续吗？");
  if (!confirmed) {
    return;
  }

  setBusy("复原中…");
  setButtonsDisabled(true);
  try {
    const data = await post("/api/restore");
    renderState(data.state);
    writeLog(data.message, data.log);
    setBusy("复原完成");
  } catch (error) {
    renderState(error.state || currentState);
    writeLog(error.message || "复原失败。", error.log || "");
    setBusy("复原失败", true);
  } finally {
    setButtonsDisabled(false);
  }
});

fetchState().catch((error) => {
  writeLog("页面初始化失败。", error?.message || "");
  setBusy("初始化失败", true);
});
