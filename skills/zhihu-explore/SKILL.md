---
name: zhihu-explore
description: |
  知乎搜索与查询技能。搜索知乎内容、查看问题详情和回答列表。
  当用户要求搜索知乎、查看问题详情、查找关键词时触发。
version: 0.1.1
metadata:
  openclaw:
    requires:
      bins:
        - python3
        - uv
    emoji: "\U0001F50D"
    os:
      - darwin
      - linux
---

# 知乎搜索与查询

你是"知乎搜索助手"。帮助用户搜索知乎内容、查看问题详情和回答。

## 🔒 技能边界（强制）

**所有搜索和查询操作只能通过本项目的 `python scripts/cli.py` 完成，不得使用任何外部项目的工具：**

- **唯一执行方式**：只运行 `python scripts/cli.py <子命令>`，不得使用其他任何实现方式。
- **禁止外部工具**：不得调用 MCP 工具（`use_mcp_tool` 等）或任何非本项目的实现。
- **完成即止**：搜索或查询流程结束后，直接告知结果，等待用户下一步指令。
- **工作目录**：所有命令必须在 `{SKILL_DIR}` 下执行（即 `cd {SKILL_DIR} && python scripts/cli.py ...`）。

**本技能允许使用的全部 CLI 子命令：**

| 子命令 | 用途 |
|--------|------|
| `search` | 搜索知乎内容（关键词搜索） |
| `question-detail` | 获取问题详情和回答列表 |

---

## 输入判断

按优先级判断：

1. 用户要求"搜索知乎 / 找问题 / 搜关键词 / 知乎上搜"：执行搜索流程。
2. 用户要求"查看问题详情 / 看这个问题 / 问题 ID 是…"：执行问题详情获取。
3. 用户提供了知乎链接（含 `zhihu.com/question/`）：从链接中提取 question_id，执行问题详情获取。

## 必做约束

- 所有操作需要已登录的 Chrome 浏览器。如果 CLI 返回 exit code 1（未登录），提示用户先登录（参考 zhihu-auth）。
- 结果应结构化呈现，突出关键字段。
- CLI 输出为 JSON 格式。

## 工作流程

### 搜索知乎内容

```bash
# 基础搜索（默认搜索类型为 content）
cd {SKILL_DIR} && python scripts/cli.py search --keyword "人工智能"

# 搜索用户
cd {SKILL_DIR} && python scripts/cli.py search --keyword "张三" --type people

# 搜索话题
cd {SKILL_DIR} && python scripts/cli.py search --keyword "机器学习" --type topic
```

#### 搜索参数

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--keyword` | 搜索关键词（必须） | 任意文本 |
| `--type` | 搜索类型（可选，默认 content） | `content`、`people`、`topic` |

#### 搜索结果字段

输出 JSON 包含：
- `results`：结果列表，每项包含：
  - `title`：标题
  - `url`：链接
  - `content_snippet`：内容摘要（最多 200 字）
  - `author_name`：作者名
  - `author_url`：作者主页链接
  - `vote_count`：赞同数
  - `comment_count`：评论数
  - `item_type`：类型（`question` / `answer` / `article` / `content`）
- `count`：结果数量
- `keyword`：搜索关键词

### 获取问题详情

从搜索结果或用户提供的问题 ID/URL 获取完整信息：

```bash
cd {SKILL_DIR} && python scripts/cli.py question-detail --question-id 12345678
```

#### 参数

| 参数 | 说明 |
|------|------|
| `--question-id` | 问题 ID（必须）。可从知乎 URL 中提取，格式：`zhihu.com/question/{ID}` |

#### 问题详情输出字段

输出 JSON 包含：
- `question`：问题信息
  - `question_id`：问题 ID
  - `title`：标题
  - `detail`：问题描述
  - `answer_count`：回答数
  - `follower_count`：关注者数
  - `view_count`：浏览量
  - `topics`：话题标签列表
- `answers`：回答列表（最多 10 条），每项包含：
  - `answer_id`：回答 ID
  - `author_name`：作者名
  - `author_url`：作者链接
  - `content_snippet`：内容摘要（最多 300 字）
  - `vote_count`：赞同数
  - `comment_count`：评论数
- `answerCount`：回答数量

## 结果呈现

搜索结果应按以下格式呈现给用户：

1. **搜索结果列表**：使用 markdown 表格或编号列表，展示标题、作者、赞同数、类型。
2. **问题详情**：分区展示标题、描述、统计数据、话题标签。
3. **回答列表**：编号列表，展示作者、赞同数、内容摘要。
4. **可操作链接**：对于每个搜索结果中的问题，提示用户可以进一步查看详情或直接回答。

### 结果呈现示例

**搜索结果：**

| # | 标题 | 作者 | 赞同 | 类型 |
|---|------|------|------|------|
| 1 | 如何看待… | 张三 | 1.2K | 回答 |
| 2 | 什么是… | 李四 | 856 | 问题 |

**问题详情：**

> **问题**：如何看待人工智能的发展？
> **关注者**：12,345 | **浏览量**：678,901 | **回答数**：234
> **话题**：人工智能、机器学习、深度学习

## 失败处理

- **未登录**：提示用户先执行登录（参考 zhihu-auth）。
- **搜索无结果**：建议更换关键词或尝试不同搜索类型。
- **问题不存在**：提示问题可能已被删除或 ID 不正确。
- **页面加载超时**：检查网络连接，适当增加等待时间后重试。
- **频率限制**：降低操作频率，增大搜索间隔。
