<h1 align="center">
  📚 zhihu-skills
</h1>

<p align="center">
  <strong>知乎自动化技能集 — 基于 CDP 的浏览器自动化，专为 AI Agent 设计</strong>
</p>

<p align="center">
  <a href="#特性">特性</a> •
  <a href="#架构">架构</a> •
  <a href="#安装">安装</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#命令参考">命令参考</a> •
  <a href="#反检测">反检测</a> •
  <a href="#许可证">许可证</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-≥3.11-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey" alt="Platform">
  <img src="https://img.shields.io/badge/protocol-Chrome%20DevTools-orange?logo=googlechrome&logoColor=white" alt="CDP">
</p>

---

## 特性

- **纯 CDP 实现** — 不依赖 Selenium / Playwright，仅通过 WebSocket 直连 Chrome DevTools Protocol
- **完整知乎工作流** — 登录认证、搜索内容、查看问题、撰写并发布回答、撰写并发布文章
- **分步发布机制** — 先填写后预览，确认再发布，安全的人机协作设计
- **13 项反检测** — WebDriver 隐藏、UA 伪装、WebGL 指纹覆盖、Client Hints 一致性等
- **跨平台适配** — 自动检测 macOS / Linux，生成对应的 UA、WebGL、Client Hints 配置
- **JSON 结构化输出** — 所有命令输出标准 JSON，便于 AI Agent 或脚本调用
- **会话持久化** — 跨命令复用 Chrome 标签页，避免频繁创建新页面

## 架构

```
+--------------------------------------------+
|            CLI 入口 (cli.py)               |
|     argparse -> 子命令路由 -> JSON 输出      |
+--------------------------------------------+
|          知乎业务层 (zhihu/)                |
|  login | search | question | answer |      |
|  article | invitation                      |
|  types · urls · errors · selectors         |
+--------------------------------------------+
|          CDP 引擎 (cdp_engine/)            |
|  Browser · Page · Element · CDPClient      |
|  stealth · errors                          |
+--------------------------------------------+
|      Chrome 管理 (chrome_launcher.py)      |
|     自动启动 · headless 检测 · 端口管理       |
+--------------------------------------------+
              ↕ WebSocket (CDP)
          +--------------+
          |    Chrome    |
          +--------------+
```

## 安装

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Google Chrome | 任意近期稳定版 | 两种安装方式均需要 |
| Python | ≥ 3.11 | 仅源码安装需要 |
| [uv](https://docs.astral.sh/uv/) | 最新版 | 仅源码安装需要 |

### 方式一：Release 包（推荐）

前往 [Releases](https://github.com/nansanhao/zhihu-skills/releases) 下载最新版本的压缩包，已包含所有依赖环境，解压即用：

```bash
# 1. 下载并解压（以 v0.1.1 为例）
unzip zhihu-skills-v0.1.1.zip
cd zhihu-skills

# 2. 直接运行，无需额外安装
python scripts/cli.py check-login
```

> 💡 Release 包已打包 Python 虚拟环境及所有依赖，无需手动安装 uv 或执行 `uv sync`。

### 方式二：源码安装

```bash
git clone https://github.com/nansanhao/zhihu-skills.git
cd zhihu-skills
uv sync
```

## 快速开始

```bash
# 1. 检查登录状态（未登录会自动打开登录页）
python scripts/cli.py check-login

# 2. 等待扫码登录
python scripts/cli.py wait-login

# 3. 搜索
python scripts/cli.py search --keyword "人工智能"

# 4. 查看问题详情
python scripts/cli.py question-detail --question-id 12345678

# 5. 撰写回答（填写到编辑器，不发布）
python scripts/cli.py write-answer \
  --question-id 12345678 \
  --content-file /path/to/answer.txt

# 6. 确认后发布
python scripts/cli.py submit-answer

# 7. 撰写文章（填写到编辑器，不发布）
python scripts/cli.py write-article \
  --title "我的文章标题" \
  --content-file /path/to/article.txt

# 8. 确认后发布文章
python scripts/cli.py submit-article
```

## 命令参考

### 全局选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `127.0.0.1` | Chrome 调试主机 |
| `--port` | `9222` | Chrome 调试端口 |

### 子命令

| 命令 | 说明 | 关键参数 |
|------|------|----------|
| `check-login` | 检查登录状态，未登录自动引导 | — |
| `wait-login` | 阻塞等待登录完成 | `--timeout` (默认 120s) |
| `search` | 搜索知乎内容 | `--keyword` (必须), `--type` (content/people/topic) |
| `question-detail` | 获取问题详情与回答列表 | `--question-id` (必须) |
| `invited-questions` | 查看被邀请回答的问题 | — |
| `write-answer` | 撰写回答，不发布 | `--question-id`, `--content-file` |
| `submit-answer` | 提交已填写的回答 | — |
| `answer` | 一步到位撰写并发布 | `--question-id`, `--content-file` |
| `write-article` | 撰写文章，不发布 | `--title`, `--content-file` |
| `submit-article` | 提交已填写的文章 | — |
| `article` | 一步到位撰写并发布文章 | `--title`, `--content-file` |

### 退出码

| 码 | 含义 |
|----|------|
| `0` | 成功 |
| `1` | 未登录 |
| `2` | 错误 |

## 反检测

内置 13 项反自动化检测措施，确保浏览器行为与真实用户一致：

| 层级 | 技术 | 说明 |
|------|------|------|
| JS 注入 | navigator.webdriver | Proxy 包装，`toString()` 返回 `[native code]` |
| JS 注入 | chrome.runtime / app | 完整伪造 headless 缺失的对象 |
| JS 注入 | WebGL 指纹 | 根据实际平台覆盖 vendor/renderer |
| JS 注入 | navigator 属性 | vendor、languages、connection、硬件参数 |
| JS 注入 | permissions.query | 拦截 notifications 权限查询 |
| CDP 协议 | User-Agent 覆盖 | `Emulation.setUserAgentOverride` |
| CDP 协议 | Client Hints | 完整 UA Metadata（brands、platform、architecture） |
| 启动参数 | Chrome flags | `--disable-blink-features=AutomationControlled` 等 10 项 |

所有信号（UA、platform、WebGL、Client Hints）**跨层一致**，自动适配 macOS / Windows / Linux。

## 项目结构

```
zhihu-skills/
├── scripts/
│   ├── cli.py                 # CLI 统一入口
│   ├── chrome_launcher.py     # Chrome 进程管理
│   ├── cdp_engine/
│   │   ├── cdp.py             # CDP WebSocket 客户端
│   │   ├── stealth.py         # 反检测配置
│   │   └── errors.py          # CDP 异常
│   └── zhihu/
│       ├── login.py           # 登录管理
│       ├── search.py          # 搜索
│       ├── question.py        # 问题详情
│       ├── answer.py          # 撰写/发布回答
│       ├── article.py         # 撰写/发布文章
│       ├── invitation.py      # 邀请回答
│       ├── types.py           # 数据模型
│       ├── urls.py            # URL 常量
│       ├── errors.py          # 知乎异常
│       └── selectors.py       # CSS 选择器
├── skills/                    # 子技能文档（供 AI Agent 路由）
│   ├── zhihu-auth/SKILL.md
│   ├── zhihu-explore/SKILL.md
│   └── zhihu-author/SKILL.md
├── SKILL.md                   # 主技能文档
├── pyproject.toml
└── LICENSE
```

## 作为 AI Skill 使用

本项目设计为 [WorkBuddy](https://www.codebuddy.cn/) 的自动化技能插件。安装后，AI Agent 可通过自然语言指令自动路由到对应子技能：

| 用户意图 | 路由子技能 | CLI 命令 |
|----------|-----------|----------|
| "登录知乎" | zhihu-auth | `check-login` → `wait-login` |
| "搜索知乎" | zhihu-explore | `search` |
| "看这个问题" | zhihu-explore | `question-detail` |
| "回答这个问题" | zhihu-author | `write-answer` → `submit-answer` |
| "写篇文章" | zhihu-author | `write-article` → `submit-article` |

## 致谢

本项目参考了 [xiaohongshu-skills](https://github.com/autoclaw-cc/xiaohongshu-skills) 的实现思路与架构设计，在此表示感谢。

## 许可证

[MIT](LICENSE)
