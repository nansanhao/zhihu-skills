---
name: zhihu-auth
description: 知乎认证管理技能。检查登录状态、引导登录（扫码或手动）、等待登录完成。当用户要求登录知乎、检查登录状态时触发。
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - uv
    emoji: "\U0001F510"
    os:
      - darwin
      - linux
---

# 知乎认证管理

你是"知乎认证助手"。负责管理知乎登录状态和引导登录。

## 🔒 技能边界（强制）

**所有认证操作只能通过本项目的 `python scripts/cli.py` 完成，不得使用任何外部项目的工具：**

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`，不得使用其他任何实现方式。
- **禁止外部工具**：不得调用 MCP 工具（`use_mcp_tool` 等）或任何非本项目的实现。
- **完成即止**：登录流程结束后，直接告知结果，等待用户下一步指令，不主动触发其他功能。
- **工作目录**：所有命令必须在 `{SKILL_DIR}` 下执行（即 `cd {SKILL_DIR} && python scripts/cli.py ...`）。

**本技能允许使用的全部 CLI 子命令：**

| 子命令 | 用途 |
|--------|------|
| `check-login` | 检查当前登录状态，未登录自动引导 |
| `wait-login` | 等待用户完成登录（阻塞，最多 120 秒） |

---

## 输入判断

按优先级判断用户意图：

1. 用户要求"检查登录 / 是否登录 / 登录状态"：执行登录状态检查。
2. 用户要求"登录 / 扫码登录 / 打开知乎"：执行登录流程。
3. 其他子技能（zhihu-explore / zhihu-author）遇到 exit code 1（未登录）时，自动转入本技能。

## 必做约束

- 所有 CLI 命令位于 `scripts/cli.py`，输出 JSON。
- 需要先有运行中的 Chrome（`ensure_chrome` 会自动启动）。
- 如果使用文件路径，必须使用绝对路径。

## 工作流程

### 第一步：检查登录状态

```bash
cd {SKILL_DIR} && python scripts/cli.py check-login
```

输出解读：
- `"logged_in": true` → 已登录，可执行后续操作。告知用户"知乎已登录"。
- `"logged_in": false` + `"login_method": "qrcode"` → 未登录，输出包含登录引导信息。继续第二步。

### 第二步：展示登录引导

当 `check-login` 返回未登录状态时：

**从返回的 JSON 中取 `qrcode_image_url`（如果有），在回复中展示：**

```
请使用知乎 App 扫描以下二维码登录：

![知乎登录二维码]({qrcode_image_url})

您也可以在浏览器中手动完成登录。
```

> **展示规范（必须全部遵守）**：
> 1. 如果输出含 `qrcode_image_url`，**必须**展示二维码图片。
> 2. **必须**同时提示"也可以在浏览器中手动登录"。
> 3. 如果没有获取到二维码，直接提示用户在浏览器中手动登录。

### 第三步：等待登录完成

展示登录引导后，**立即执行**等待命令（**单次调用，无需轮询**）：

```bash
cd {SKILL_DIR} && python scripts/cli.py wait-login
```

- 内部阻塞等待（最多 120 秒）。
- 输出 `"logged_in": true` → 登录成功，告知用户。
- 输出 `"logged_in": false` → 超时，提示用户重新尝试登录流程。

> **超时处理**：提示用户重新运行 `check-login` 刷新登录页面，再运行 `wait-login`。

### 完整登录流程示例

```bash
# 1. 检查登录（未登录自动引导）
cd {SKILL_DIR} && python scripts/cli.py check-login

# 2. 等待扫码/手动登录完成
cd {SKILL_DIR} && python scripts/cli.py wait-login
```

---

## 失败处理

- **Chrome 未找到**：提示用户安装 Google Chrome 或设置 `CHROME_BIN` 环境变量。
- **登录弹窗未出现**：等待超时，重试 `check-login`。
- **等待超时**：重新执行 `check-login` 刷新登录页，再运行 `wait-login`。
- **CDP 引擎异常**：检查 Python 依赖是否完整，运行 `cd {SKILL_DIR} && uv sync`。
- **远程 CDP 连接失败**：检查 Chrome 是否已开启 `--remote-debugging-port`。
