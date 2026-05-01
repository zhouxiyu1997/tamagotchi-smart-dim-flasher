# Contributing

感谢你愿意改进这个项目。

Thank you for helping improve this project.

## 开发环境 / Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 本地运行 / Run Locally

```bash
python -m dim_tool
```

如果你在 macOS 上需要直接访问 `CH341A`，通常要使用：

If you need direct `CH341A` access on macOS, you will usually need:

```bash
sudo ./start-web-ui.command
```

## 提交前检查 / Pre-Submission Checks

至少运行：

At minimum, run:

```bash
python3 -m py_compile dim_tool/*.py
```

如果你改动了刷写逻辑，请尽量补充：

If you change flashing logic, please try to include:

- 不同容量镜像的探测说明 / probe notes for different image capacities
- `flashrom` 日志样例 / example `flashrom` logs
- 真实硬件验证结果 / real hardware validation results

## 资源与版权 / Assets and Copyright

这个仓库不接收卡片 `BIN`、固件包、镜像压缩包或其他分发资源。

This repository does not accept card `BIN` files, firmware packages, image archives, or other distributable assets.

- 请不要提交 `tamasmart/` 下的本地资源 / do not commit local assets under `tamasmart/`
- 请不要在 PR 中附带受版权保护的镜像文件 / do not attach copyrighted images or dumps in PRs
- 如果需要讨论资源来源，请只写获取方式说明，不直接把资源入库 / if asset sources need to be discussed, describe the acquisition method without committing the files
- 向本仓库提交代码时，默认同意你的修改以 `GPL-3.0` 方式分发，并保留现有作者署名和许可证声明 / by contributing code, you agree that your changes may be distributed under `GPL-3.0` with existing attribution and license notices preserved

## 变更建议 / Change Guidelines

- 优先保持 Web UI 操作简单直接 / keep the Web UI simple and direct
- 新增兼容性时，尽量不要把逻辑写死到某一张具体卡 / avoid hardcoding support for one specific card when adding compatibility
- 如果修改了用户可见文案，请尽量保持中英文说明清晰明确 / keep user-facing Chinese and English wording clear when editing documentation or UI text
