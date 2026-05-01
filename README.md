# DiM 卡一键刷写工具

这个仓库现在带了一个本地 Web 界面，可以把 `CH341A + DiM/BEM` 的常用流程做成页面操作。

## 功能

- 上传 `1MB` 或 `4MB` 的 `BIN`
- 上传后自动备份当前卡
- 安装前再次自动备份，确保复原点是最新的
- 一键把最近备份复原回当前卡
- 保留上传、备份和中间镜像到 `runtime/`

## 启动方式

直接双击：

- [start-web-ui.command](/Users/xiyu/Documents/code/tamagotchi-smart-dim-flasher/start-web-ui.command)

或者在终端里运行：

```bash
cd /Users/xiyu/Documents/code/tamagotchi-smart-dim-flasher
./start-web-ui.command
```

首次启动会自动创建 `.venv` 并安装 `Flask`。

## 页面流程

1. 插入 `CH341A` 和卡。
2. 上传要安装的 `BIN`。
3. 页面会立即备份当前卡。
4. 点击“安装到当前 DiM 卡”。
5. 如果需要撤回，点击“复原最近备份”。

## BIN 规则

- `1MB BIN`：只覆盖前 `1MB`，后 `3MB` 会沿用安装前最新备份里的内容。
- `4MB BIN`：整片 `4MB` 原样写入。

## 注意

- 依赖本机已经可用的 `flashrom`。
- 当前默认程序器参数是 `ch341a_spi`。
- 当前默认芯片定义是 `MX25L3205(A)`。
- 如果你以后换了别的芯片定义，可以用环境变量 `DIM_CHIP` 覆盖。
