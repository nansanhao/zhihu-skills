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

    # 在发布设置面板中选择"包含 AI 辅助创作"
    _select_ai_declaration(page)

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


def _select_ai_declaration(page) -> None:
    """在发布设置面板中选择"包含 AI 辅助创作"创作声明。

    知乎回答编辑器右侧有"发布设置"面板，其中"创作声明"是一个下拉选择框。
    点击下拉框展开选项列表，然后点击"包含 AI 辅助创作"选项。
    """
    # 检查当前创作声明值
    current = page.evaluate('''
    (() => {
        const labels = document.querySelectorAll("label");
        for (const label of labels) {
            if (label.textContent.includes("创作声明")) {
                const btn = label.parentElement.querySelector(
                    "button[role='combobox']"
                );
                if (btn) {
                    const span = btn.querySelector("span");
                    return span ? span.textContent.trim() : "";
                }
            }
        }
        return "";
    })()
    ''')

    if "AI 辅助创作" in current or "AI辅助创作" in current:
        logger.info("创作声明已为: %s，无需修改", current)
        return

    logger.info("当前创作声明: %s，需要切换为 AI 辅助创作", current or "未找到")

    # 点击下拉框展开选项
    page.evaluate('''
    (() => {
        const labels = document.querySelectorAll("label");
        for (const label of labels) {
            if (label.textContent.includes("创作声明")) {
                const btn = label.parentElement.querySelector(
                    "button[role='combobox']"
                );
                if (btn) { btn.click(); return true; }
            }
        }
        return false;
    })()
    ''')
    time.sleep(0.8)

    # 在下拉选项中点击"包含 AI 辅助创作"
    result = page.evaluate('''
    (() => {
        const options = document.querySelectorAll(
            ".Select-option, [role='option']"
        );
        for (const opt of options) {
            const text = opt.textContent.trim();
            if (text.includes("AI 辅助创作") || text.includes("AI辅助创作")) {
                opt.click();
                return "selected: " + text;
            }
        }
        return "not_found";
    })()
    ''')
    logger.info("选择 AI 辅助创作: %s", result)
    time.sleep(0.3)


def _click_submit(page, title: str) -> dict:
    """点击提交按钮发布回答。

    完整流程：
    1. 点击"发布回答"按钮
    2. 处理可能出现的确认弹窗（如 Markdown 格式确认）
    3. 如果弹窗处理后仍未跳转，尝试再次点击发布
    4. 轮询检查是否发布成功（URL 跳转到 /answer/）
    """
    # ---------- Step 1: 点击发布按钮 ----------
    js_click_submit = """
    (() => {
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
    result = page.evaluate(js_click_submit)
    logger.info("点击发布按钮: %s", result)

    if result == "not_found":
        return {"success": False, "error": "未找到发布按钮"}

    if result == "disabled":
        return {"success": False, "error": "发布按钮不可用，可能内容为空"}

    # ---------- Step 2: 等待并处理确认弹窗 ----------
    # 知乎在粘贴 Markdown 内容后点击发布时，可能弹出"识别到特殊格式，
    # 请确认是否将 Markdown 解析为正确格式"的 toast/弹窗，需要点击"确认并解析"。
    # 也可能出现其他确认弹窗。循环检测并处理。
    max_dialog_rounds = 3
    for round_idx in range(max_dialog_rounds):
        time.sleep(2)

        # 检查是否已跳转（发布成功）
        current_url = page.evaluate("location.href") or ""
        if "/answer/" in current_url:
            answer_id = _extract_answer_id(current_url)
            logger.info("发布成功，已跳转: %s", current_url)
            return _success_result(title, current_url, answer_id)

        # 检测并处理确认弹窗（Markdown 解析确认、通用确认等）
        dialog_result = page.evaluate("""
        (() => {
            // 1. Markdown 格式确认弹窗 —— 查找包含"确认并解析"的按钮
            const allBtns = document.querySelectorAll('button');
            for (const btn of allBtns) {
                const text = btn.textContent.trim();
                if (text.includes('确认并解析') || text.includes('确认解析')) {
                    if (!btn.disabled) {
                        btn.click();
                        return 'clicked_confirm_parse: ' + text;
                    }
                }
            }

            // 2. 通用确认弹窗 —— Modal/Dialog 中的确认按钮
            const modalBtns = document.querySelectorAll(
                '.Modal button, .Dialog button, [role="dialog"] button, '
                + '[class*="modal"] button, [class*="Modal"] button'
            );
            for (const btn of modalBtns) {
                const text = btn.textContent.trim();
                if ((text === '确认' || text === '确定' || text === '是')
                    && !btn.disabled) {
                    btn.click();
                    return 'clicked_modal_confirm: ' + text;
                }
            }

            // 3. Toast 中的可点击确认（知乎有时把确认做在 toast 里）
            const toasts = document.querySelectorAll(
                '.Notification, .Toast, [class*="toast"], [class*="Toast"]'
            );
            for (const toast of toasts) {
                const links = toast.querySelectorAll('a, button, span[role="button"]');
                for (const link of links) {
                    const text = link.textContent.trim();
                    if (text.includes('确认') || text.includes('解析')) {
                        link.click();
                        return 'clicked_toast_action: ' + text;
                    }
                }
            }

            // 4. 无弹窗需要处理
            return 'no_dialog';
        })()
        """)
        logger.info("弹窗检测 (round %d): %s", round_idx + 1, dialog_result)

        if dialog_result == "no_dialog":
            break  # 没有弹窗，继续后续检查

        # 点击了确认按钮，等待知乎处理后可能需要再次点击发布
        time.sleep(2)

        # 检查是否已跳转
        current_url = page.evaluate("location.href") or ""
        if "/answer/" in current_url:
            answer_id = _extract_answer_id(current_url)
            logger.info("确认弹窗后发布成功: %s", current_url)
            return _success_result(title, current_url, answer_id)

        # 确认弹窗后知乎可能需要再次点击发布按钮
        retry_result = page.evaluate(js_click_submit)
        logger.info("弹窗确认后重试发布: %s", retry_result)

    # ---------- Step 3: 最终轮询等待发布完成 ----------
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        current_url = page.evaluate("location.href") or ""
        if "/answer/" in current_url:
            answer_id = _extract_answer_id(current_url)
            logger.info("发布成功: %s", current_url)
            return _success_result(title, current_url, answer_id)
        time.sleep(1)

    # ---------- Step 4: 最终状态检查 ----------
    post_check = page.evaluate("""
    (() => {
        const toast = document.querySelector(
            '.Notification, .Toast, [class*=toast], [class*=Toast]');
        if (toast) return 'toast: ' + toast.textContent.trim().substring(0, 100);
        if (location.href.includes('/answer/')) return 'redirected: ' + location.href;
        return 'url: ' + location.href;
    })()
    """)
    logger.info("最终发布检查: %s", post_check)

    # 即使没有跳转，也可能已经发布成功（某些情况下知乎不跳转）
    if "redirected" in (post_check or ""):
        answer_id = _extract_answer_id(post_check)
        return _success_result(title, post_check, answer_id)

    return {
        "success": True,
        "title": title,
        "status": "回答已发布",
        "postCheck": post_check,
    }


def _extract_answer_id(url_or_text: str) -> str:
    """从 URL 中提取回答 ID。"""
    import re
    match = re.search(r"/answer/(\d+)", url_or_text)
    return match.group(1) if match else ""


def _success_result(title: str, url: str, answer_id: str) -> dict:
    """构造发布成功的返回结果。"""
    result = {
        "success": True,
        "title": title,
        "status": "回答已发布",
        "postCheck": f"redirected: {url}",
    }
    if answer_id:
        result["answerId"] = answer_id
    return result
