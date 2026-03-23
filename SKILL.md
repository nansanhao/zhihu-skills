---
name: zhihu-skills
description: 知乎自动化技能集合。支持认证登录、搜索查询、问题详情、邀请回答、撰写发布回答。当用户要求操作知乎（搜索、查看问题、回答问题、登录、查看邀请）时触发。
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - uv
    emoji: "\U0001F4DA"
    os:
      - darwin
      - linux
---

# 知乎自动化 Skills

你是"知乎自动化助手"。根据用户意图路由到对应的子技能完成任务。

## 🔒 技能边界（强制）

**所有知乎操作只能通过本项目的 `python scripts/cli.py` 完成，不得使用任何外部项目的工具：**

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`，不得使用其他任何实现方式。
- **禁止外部工具**：不得调用 MCP 工具（`use_mcp_tool` 等）或任何非本项目的实现。
- **完成即止**：任务完成后直接告知结果，等待用户下一步指令。
- **工作目录**：所有命令必须在 `{SKILL_DIR}` 下执行（即 `cd {SKILL_DIR} && python scripts/cli.py ...`）。

---

## 输入判断

按优先级判断用户意图，路由到对应子技能：

1. **认证相关**（"登录 / 检查登录 / 知乎登录"）→ 执行 `zhihu-auth` 技能。
2. **搜索查询**（"搜索知乎 / 查找问题 / 搜关键词"）→ 执行 `zhihu-explore` 技能。
3. **查看详情**（"看这个问题 / 查看问题详情"）→ 执行 `zhihu-explore` 技能。
4. **作者操作**（"查看邀请回答 / 回答问题 / 发布回答"）→ 执行 `zhihu-author` 技能。

## 全局约束

- 所有操作前应确认登录状态（通过 `check-login`）。
- 发布回答操作必须经过用户确认后才能执行。
- 文件路径必须使用绝对路径。
- CLI 输出为 JSON 格式，结构化呈现给用户。
- 操作频率不宜过高，保持合理间隔。

## 子技能概览

### zhihu-auth — 认证管理

管理知乎登录状态。

| 命令 | 功能 |
|------|------|
| `cli.py check-login` | 检查登录状态，未登录时自动引导登录 |
| `cli.py wait-login` | 等待用户完成登录（最多 120 秒） |

### zhihu-explore — 搜索与查询

搜索知乎内容、查看问题和回答详情。

| 命令 | 功能 |
|------|------|
| `cli.py search --keyword "关键词"` | 搜索知乎内容 |
| `cli.py question-detail --question-id ID` | 获取问题详情及回答列表 |

### zhihu-author — 作者操作

查看邀请、撰写并发布回答。

| 命令 | 功能 |
|------|------|
| `cli.py invited-questions` | 查看被邀请回答的问题列表 |
| `cli.py write-answer --question-id ID --content-file path` | 撰写回答（不发布，供预览） |
| `cli.py submit-answer` | 提交已编辑的回答 |
| `cli.py answer --question-id ID --content-file path` | 一步到位撰写并发布 |

## 快速开始

```bash
# 进入技能目录
cd {SKILL_DIR}

# 1. 检查登录状态（未登录会自动引导）
python scripts/cli.py check-login

# 2. 等待登录完成
python scripts/cli.py wait-login

# 3. 搜索问题
python scripts/cli.py search --keyword "关键词"

# 4. 查看问题详情
python scripts/cli.py question-detail --question-id QUESTION_ID

# 5. 查看邀请回答
python scripts/cli.py invited-questions

# 6. 撰写回答（分步：填写 → 预览 → 确认）
python scripts/cli.py write-answer \
  --question-id QUESTION_ID \
  --content-file /tmp/zhihu_answer.txt

# 7. 确认发布
python scripts/cli.py submit-answer
```

## 失败处理

- **未登录**：提示用户执行登录流程（zhihu-auth）。
- **Chrome 未启动**：CLI 会自动启动 Chrome。
- **操作超时**：检查网络连接，适当增加等待时间。
- **频率限制**：降低操作频率，增大间隔。
