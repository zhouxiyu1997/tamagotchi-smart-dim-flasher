# DiM 卡一键刷写工具

这个仓库现在带了一个本地 Web 界面，可以把 `CH341A + DiM/BEM` 的常用流程做成页面操作。

## 功能

- 上传 `1MB payload` 或完整 `BIN`
- 自动按当前卡容量处理完整镜像，不再写死只认 `4MB`
- 上传后自动备份当前卡
- 安装前再次自动备份，确保复原点是最新的
- 一键把最近备份复原回当前卡
- 一键重置当前 Tama Smart 卡的使用次数，自动扫描不同容量/镜像段并尽量同时启用写保护
- 保留上传、备份和中间镜像到 `runtime/`

## 启动方式

直接双击：

- [start-web-ui.command](/Users/xiyu/Documents/code/tamagotchi-smart-dim-flasher/start-web-ui.command)
- [start-web-ui-root.command](/Users/xiyu/Documents/code/tamagotchi-smart-dim-flasher/start-web-ui-root.command)

或者在终端里运行：

```bash
cd /Users/xiyu/Documents/code/tamagotchi-smart-dim-flasher
./start-web-ui.command
```

如果你在 macOS 上看到 `LIBUSB_ERROR_ACCESS`、`root privilege` 或 `Cannot detach the existing USB driver`，请改用：

```bash
cd /Users/xiyu/Documents/code/tamagotchi-smart-dim-flasher
sudo ./start-web-ui.command
```

或者直接双击 [start-web-ui-root.command](/Users/xiyu/Documents/code/tamagotchi-smart-dim-flasher/start-web-ui-root.command)。

首次启动会自动创建 `.venv` 并安装 `Flask`。

## 页面流程

1. 插入 `CH341A` 和卡。
2. 上传要安装的 `BIN`。
3. 页面会立即备份当前卡。
4. 点击“安装到当前 DiM 卡”。
5. 如果需要撤回，点击“复原最近备份”。
6. 如果只想保留当前内容并清空使用次数，点击“重置当前卡使用次数”。

## BIN 规则

- `1MB BIN`：只覆盖前 `1MB`，剩余区域会沿用安装前最新备份里的内容；无论当前卡是 `2MB`、`4MB` 还是别的兼容容量，都按实际容量 merge。
- 完整 `BIN`：只要大小和当前卡容量一致，就会整片原样写入，不再固定要求 `4MB`。
- “重置当前卡使用次数”：会先备份当前卡，再扫描整张卡里所有有效的 Tama Smart 镜像段，清空每个段的 3 个 usage 槽，并按该段容量重算头部校验后写回。

## 注意

- 依赖本机已经可用的 `flashrom`。
- 当前默认程序器参数是 `ch341a_spi`。
- 当前默认芯片定义是 `MX25L3205(A)`。
- 如果当前卡实际不是这颗芯片，工具会在探测失败时自动回退到 `flashrom` 自检，再按读出来的真实容量处理。
- 在 macOS 上，如果 `flashrom` 提示 `LIBUSB_ERROR_ACCESS` 或 `No EEPROM/flash device found`，通常是权限不足导致 CH341A 没有被成功接管，不是 BIN 本身的问题。
- 如果 `flashrom` 和当前芯片支持写保护命令，重置使用次数后会尽量启用整片写保护；如果不支持，页面会提示“已清零，但未成功启用写保护”。
- 如果你以后换了别的芯片定义，可以用环境变量 `DIM_CHIP` 覆盖。
