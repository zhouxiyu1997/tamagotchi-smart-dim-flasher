# tamagotchi-smart-dim-flasher

一个面向 `macOS + CH341A` 的本地 Web 刷卡工具，用来备份、写入、复原和重置 `Tamagotchi Smart` 系列卡片。

Copyright (C) 2026 `xiyu`

## 项目定位

- 运行平台：`macOS`
- 程序器：`CH341A`
- 主要目标：`Tamagotchi Smart` 相关 `DiM / TamaSma / BIM` 类卡片备份与刷写
- 刷写后端：`flashrom`
- 交互方式：本地 `Flask` Web UI

本项目当前主要面向 `Tamagotchi Smart` 使用场景。按底层 SPI 刷写方式推测，部分 `数码暴龙机 / Digimon` 同类卡片理论上也可能适用，但我没有做过实机测试，请自行验证。

## 功能

- 上传 `1MB payload` 或完整 `BIN`
- 自动探测当前卡的真实芯片与容量
- 自动备份当前卡，再执行安装
- 一键复原最近一次备份
- 支持不同容量的完整镜像写入，不再只固定 `4MB`
- 支持保留当前内容、仅重置 `Tama Smart` 使用次数
- 运行过程中的上传、备份和中间镜像统一保存在 `runtime/`

## 环境要求

- `macOS`
- `Python 3.10+`
- 已安装并可执行的 `flashrom`
- `CH341A` 程序器

如果你使用 `Homebrew`，通常可以这样安装 `flashrom`：

```bash
brew install flashrom
```

## 快速开始

克隆仓库后，直接运行：

```bash
./start-web-ui.command
```

如果你在 macOS 上遇到以下报错：

- `LIBUSB_ERROR_ACCESS`
- `root privilege`
- `Cannot detach the existing USB driver`

请改用：

```bash
sudo ./start-web-ui.command
```

也可以直接双击：

- `start-web-ui.command`
- `start-web-ui-root.command`

首次启动会自动创建 `.venv` 并安装依赖。

## 页面使用流程

1. 连接 `CH341A`，插入目标卡。
2. 先点“探测当前卡容量”，确认当前芯片与容量。
3. 上传要写入的 `BIN`。
4. 页面会先自动备份当前卡。
5. 点击“安装到当前 DiM 卡”完成刷写。
6. 如果要撤回，点击“复原最近备份”。
7. 如果只想保留当前内容并清空次数，点击“重置当前卡使用次数”。

## BIN 规则

- `1MB BIN`
  只覆盖前 `1MB`，剩余区域保留当前卡备份中的内容。
- 完整 `BIN`
  文件大小必须和当前卡实际容量一致，工具会整片写入。
- 重置使用次数
  会先备份当前卡，再扫描整张卡中的有效 `Tama Smart` 头，清空 usage 槽并重算校验。

## 资源说明

这个仓库不再附带任何卡片 `BIN`、固件包或镜像资源。

- 请使用你自己的备份文件，或自行前往 [Internet Archive](https://archive.org/) 获取资源
- 请自行确认资源来源、版权状态和使用合法性
- 建议把你本地的资源放在 `tamasmart/` 目录；这个目录里的资源默认不会进入 Git

## 项目结构

```text
.
├── dim_tool/                  # Flask 应用与刷卡逻辑
├── runtime/                   # 运行时生成的上传、备份与中间文件
├── tamasmart/                 # 本地自备资源目录（默认不纳入版本控制）
├── tools/mock_flashrom.py     # 测试用 mock flashrom
├── start-web-ui.command       # 普通启动脚本
├── start-web-ui-root.command  # root 启动脚本
├── pyproject.toml             # Python 项目元数据
├── requirements.txt           # 启动脚本使用的依赖列表
└── README.md
```

## 开发

创建虚拟环境并安装依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

本地启动：

```bash
python -m dim_tool
```

基础校验：

```bash
python3 -m py_compile dim_tool/*.py
```

## 限制与说明

- 本项目主要在 `Tamagotchi Smart` 场景下整理和验证
- 其他同类卡片可能兼容，但目前没有完整实机覆盖
- `flashrom` 对不同芯片的写保护支持程度不同
- 写卡、清 usage、刷固件都存在硬件风险，请自行承担风险
- 本项目与 `Bandai` 无任何官方关联

## License

本仓库采用 `GNU GPL v3.0`，详见 [LICENSE](LICENSE)。

- 分发原版或修改版时，必须保留原作者署名、版权声明和许可证文本
- 如果你分发修改后的版本，也必须继续按 `GPL-3.0` 发布对应源码，并标明你修改过哪些内容
