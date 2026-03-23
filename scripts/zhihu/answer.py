"""知乎回答发布功能。"""

from __future__ import annotations

import json
import logging
import random
import time

from .errors import EditorError
from .urls import make_question_url

logger = logging.getLogger(__name__)


def _markdown_to_html(md_text: str) -> str:
    """将 Markdown 文本转换为知乎编辑器友好的 HTML。

    知乎编辑器（Draft.js）在粘贴时会解析 HTML，因此我们把 Markdown
    转成带标签的 HTML，粘贴后即可保留格式（加粗、标题、列表、代码块、
    表格、分割线等）。
    """
    try:
        from markdown_it import MarkdownIt
        md = MarkdownIt("commonmark", {"html": True, "typographer": True})
        # 启用表格和删除线插件
        md.enable("table")
        md.enable("strikethrough")
        html = md.render(md_text)
    except ImportError:
        logger.warning("markdown-it-py 未安装，回退到纯文本模式")
        return ""
    except Exception as e:
        logger.warning("Markdown 转换失败: %s，回退到纯文本模式", e)
        return ""

    return html


def write_answer(page, question_id: str, content: str, submit: bool = False) -> dict:
    """在问题页面撰写回答。

    Args:
        page: CDP Page 对象。
        question_id: 问题 ID。
        content: 回答内容（纯文本或 Markdown）。
        submit: 是否直接提交。False 则只填写不发布，等待用户确认。

    Returns:
        操作结果字典。
    """
    url = make_question_url(question_id)
    page.navigate(url)
    page.wait_for_load()
    page.wait_dom_stable(timeout=10.0)
    time.sleep(1.5)

    # 检查问题是否存在
    title = page.evaluate(
        """document.querySelector('.QuestionHeader-title')?.textContent?.trim() || ''"""
    )
    if not title:
        return {"success": False, "error": "问题不存在或无法访问"}

    # 点击"写回答"按钮
    _click_write_answer(page)

    # 等待编辑器出现
    time.sleep(1.5)

    # 在编辑器中输入内容
    _fill_editor(page, content)

    if submit:
        # 点击发布按钮
        return _click_submit(page, title)
    else:
        return {
            "success": True,
            "title": title,
            "status": "回答已填写，等待确认发布",
            "message": "请在浏览器中检查回答内容，确认后执行 submit-answer 命令",
        }


def submit_answer(page) -> dict:
    """提交已编辑的回答（在 write_answer 后调用）。

    Args:
        page: CDP Page 对象。

    Returns:
        操作结果字典。
    """
    title = page.evaluate(
        """document.querySelector('.QuestionHeader-title')?.textContent?.trim() || ''"""
    )
    return _click_submit(page, title or "")


def _click_write_answer(page) -> None:
    """点击"写回答"按钮，打开回答编辑区域。"""
    js_code = """
    (() => {
        // 方案1：编辑器已存在（之前已打开）
        const existingEditor = document.querySelector(
            '.public-DraftEditor-content[contenteditable="true"]'
        );
        if (existingEditor) {
            return 'editor_already_open';
        }

        // 方案2：点击"写回答"按钮（蓝色按钮，文字可能带零宽字符）
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const text = btn.textContent.trim();
            if (text.includes('写回答') && !btn.disabled) {
                btn.click();
                return 'button_clicked';
            }
        }

        // 方案3：回答框区域占位符
        const placeholder = document.querySelector(
            '.AnswerForm .public-DraftEditorPlaceholder-root'
        );
        if (placeholder) {
            placeholder.click();
            return 'placeholder_clicked';
        }

        return 'not_found';
    })()
    """
    result = page.evaluate(js_code)
    logger.info("点击写回答: %s", result)

    if result == "not_found":
        # 尝试滚动到页面底部找到回答区域
        page.scroll_to_bottom()
        time.sleep(1)
        result = page.evaluate(js_code)
        logger.info("滚动后再次尝试: %s", result)


def _fill_editor(page, content: str) -> None:
    """在编辑器中填入回答内容。

    优先尝试将 Markdown 转为 HTML 并通过剪贴板粘贴（保留格式），
    如果 Markdown 转换不可用则回退到纯文本逐段输入。
    """
    # 等待编辑器激活
    deadline = time.monotonic() + 10.0
    editor_found = False
    while time.monotonic() < deadline:
        has_editor = page.evaluate(
            """
            document.querySelector(
                '.public-DraftEditor-content[contenteditable="true"], '
                + '.AnswerForm [contenteditable="true"], '
                + '[role="textbox"][contenteditable="true"]'
            ) !== null
            """
        )
        if has_editor:
            editor_found = True
            break
        time.sleep(0.5)

    if not editor_found:
        raise EditorError("未找到可编辑区域，请确保已点击写回答")

    # 聚焦编辑器
    page.evaluate(
        """
        (() => {
            const editor = document.querySelector(
                '.public-DraftEditor-content[contenteditable="true"], '
                + '.AnswerForm [contenteditable="true"], '
                + '[role="textbox"][contenteditable="true"]'
            );
            if (editor) {
                editor.focus();
                // 移动光标到末尾
                const range = document.createRange();
                const sel = window.getSelection();
                range.selectNodeContents(editor);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
            }
        })()
        """
    )
    time.sleep(0.3)

    # 先全选清空已有内容
    page.select_all_and_delete()
    time.sleep(0.2)

    # 尝试富文本粘贴模式
    html_content = _markdown_to_html(content)
    if html_content:
        success = _paste_rich_text(page, html_content, content)
        if success:
            logger.info("回答内容已通过富文本粘贴填写 (%d 字符)", len(content))
            return

    # 回退：纯文本逐段输入
    logger.info("使用纯文本模式输入")
    _fill_plain_text(page, content)
    logger.info("回答内容已填写 (%d 字符)", len(content))


def _paste_rich_text(page, html: str, plain_text: str) -> bool:
    """通过模拟剪贴板粘贴事件将富文本 HTML 粘贴到知乎编辑器。

    知乎的 Draft.js 编辑器会监听 paste 事件，从 clipboardData 中
    读取 text/html 类型的数据并解析为富文本块。
    """
    html_escaped = json.dumps(html)
    plain_escaped = json.dumps(plain_text)

    js_code = f"""
    (() => {{
        const editor = document.querySelector(
            '.public-DraftEditor-content[contenteditable="true"], '
            + '.AnswerForm [contenteditable="true"], '
            + '[role="textbox"][contenteditable="true"]'
        );
        if (!editor) return 'no_editor';

        editor.focus();

        // 构造 DataTransfer 对象
        const dt = new DataTransfer();
        dt.setData('text/html', {html_escaped});
        dt.setData('text/plain', {plain_escaped});

        // 构造并触发 paste 事件
        const pasteEvent = new ClipboardEvent('paste', {{
            bubbles: true,
            cancelable: true,
            clipboardData: dt
        }});
        editor.dispatchEvent(pasteEvent);

        return 'pasted';
    }})()
    """
    result = page.evaluate(js_code)
    logger.info("富文本粘贴结果: %s", result)

    if result != "pasted":
        return False

    # 等待编辑器处理粘贴内容
    time.sleep(1.5)

    # 验证是否有内容被写入
    has_content = page.evaluate("""
    (() => {
        const editor = document.querySelector(
            '.public-DraftEditor-content[contenteditable="true"], '
            + '.AnswerForm [contenteditable="true"], '
            + '[role="textbox"][contenteditable="true"]'
        );
        if (!editor) return false;
        const text = editor.textContent.trim();
        return text.length > 10;
    })()
    """)

    if has_content:
        return True

    logger.warning("富文本粘贴后编辑器内容为空，将回退到纯文本模式")
    return False


def _fill_plain_text(page, content: str) -> None:
    """纯文本逐段输入（回退方案）。"""
    # 按段落输入：先按换行拆分，每段用 insertText 输入
    paragraphs = content.split("\n")
    for i, para in enumerate(paragraphs):
        if para:
            # 使用 Input.insertText 一次性输入整段文字（比逐字符更可靠）
            page._send_session("Input.insertText", {"text": para})
            time.sleep(random.uniform(0.1, 0.3))

        # 除最后一段外，插入换行
        if i < len(paragraphs) - 1:
            page._send_session(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyDown",
                    "key": "Enter",
                    "code": "Enter",
                    "windowsVirtualKeyCode": 13,
                },
            )
            page._send_session(
                "Input.dispatchKeyEvent",
                {
                    "type": "keyUp",
                    "key": "Enter",
                    "code": "Enter",
                    "windowsVirtualKeyCode": 13,
                },
            )
            time.sleep(random.uniform(0.05, 0.15))


def _click_submit(page, title: str) -> dict:
    """点击提交按钮发布回答。"""
    js_code = """
    (() => {
        // 查找提交按钮（用 includes 兼容零宽字符）
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const text = btn.textContent.trim();
            if ((text.includes('发布回答') || text.includes('提交回答'))
                && !text.includes('发布设置')) {
                if (!btn.disabled) {
                    btn.click();
                    return 'clicked';
                }
                return 'disabled';
            }
        }
        // 尝试 .AnswerForm 内的主按钮
        const primaryBtn = document.querySelector(
            '.AnswerForm button.Button--primary, '
            + '.AnswerForm button[type="submit"]'
        );
        if (primaryBtn && !primaryBtn.disabled) {
            primaryBtn.click();
            return 'clicked';
        }
        return 'not_found';
    })()
    """
    result = page.evaluate(js_code)
    logger.info("点击发布按钮: %s", result)

    if result == "not_found":
        return {"success": False, "error": "未找到发布按钮"}

    if result == "disabled":
        return {"success": False, "error": "发布按钮不可用，可能内容为空"}

    # 等待发布完成
    time.sleep(5)

    # 检查是否发布成功：看是否出现成功提示或页面 URL 变化
    post_check = page.evaluate("""
    (() => {
        // 检查是否有错误提示
        const toast = document.querySelector(
            '.Notification, .Toast, [class*=toast], [class*=Toast]');
        if (toast) return 'toast: ' + toast.textContent.trim().substring(0, 100);
        // 检查 URL 是否包含 answer（发布后会跳转到回答页）
        if (location.href.includes('/answer/')) return 'redirected: ' + location.href;
        return 'done';
    })()
    """)
    logger.info("发布后检查: %s", post_check)

    return {
        "success": True,
        "title": title,
        "status": "回答已发布",
        "postCheck": post_check,
    }
