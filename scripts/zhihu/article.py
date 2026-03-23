"""知乎文章发布功能。"""

from __future__ import annotations

import json
import logging
import random
import time

from .errors import EditorError
from .urls import ARTICLE_WRITE_URL

logger = logging.getLogger(__name__)


def _markdown_to_html(md_text: str) -> str:
    """将 Markdown 文本转换为知乎编辑器友好的 HTML。"""
    try:
        from markdown_it import MarkdownIt

        md = MarkdownIt("commonmark", {"html": True, "typographer": True})
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


def write_article(page, title: str, content: str, submit: bool = False) -> dict:
    """在知乎专栏编辑器中撰写文章。

    Args:
        page: CDP Page 对象。
        title: 文章标题。
        content: 文章内容（纯文本或 Markdown）。
        submit: 是否直接发布。False 则只填写不发布，等待用户确认。

    Returns:
        操作结果字典。
    """
    page.navigate(ARTICLE_WRITE_URL)
    page.wait_for_load()
    page.wait_dom_stable(timeout=10.0)
    time.sleep(2.0)

    # 检查是否在文章编辑页面
    current_url = page.evaluate("location.href") or ""
    if "zhuanlan.zhihu.com" not in current_url:
        return {"success": False, "error": "未能进入文章编辑页面，请检查登录状态"}

    # 填写标题
    _fill_title(page, title)
    time.sleep(0.5)

    # 填写正文
    _fill_body(page, content)

    if submit:
        return _click_publish(page, title)
    else:
        return {
            "success": True,
            "title": title,
            "status": "文章已填写，等待确认发布",
            "message": "请在浏览器中检查文章内容，确认后执行 submit-article 命令",
        }


def submit_article(page) -> dict:
    """提交已编辑的文章（在 write_article 后调用）。

    Args:
        page: CDP Page 对象。

    Returns:
        操作结果字典。
    """
    # 尝试读取标题
    title = page.evaluate("""
    (() => {
        const titleInput = document.querySelector(
            '.WriteIndex-titleInput input, '
            + 'textarea[placeholder*="标题"], '
            + 'input[placeholder*="标题"], '
            + '.PostEditor-titleInput input'
        );
        return titleInput ? (titleInput.value || titleInput.textContent || '').trim() : '';
    })()
    """) or ""
    return _click_publish(page, title)


# ========== 内部函数 ==========


def _fill_title(page, title: str) -> None:
    """填写文章标题。

    知乎编辑器标题是 React 受控组件（textarea），直接赋值 el.value 不会
    触发 React 内部状态更新。必须用 CDP Input.insertText 模拟真实键盘输入，
    这样 React 的 onChange 才能正确捕获。
    """
    js_find_title = """
    (() => {
        let el = document.querySelector('.WriteIndex-titleInput input');
        if (el) return '.WriteIndex-titleInput input';

        el = document.querySelector('textarea[placeholder*="标题"]');
        if (el) return 'textarea[placeholder*="标题"]';

        el = document.querySelector('input[placeholder*="标题"]');
        if (el) return 'input[placeholder*="标题"]';

        el = document.querySelector('.PostEditor-titleInput input');
        if (el) return '.PostEditor-titleInput input';

        el = document.querySelector('[contenteditable="true"][data-placeholder*="标题"]');
        if (el) return '[contenteditable="true"][data-placeholder*="标题"]';

        return '';
    })()
    """
    selector = page.evaluate(js_find_title)
    logger.info("标题输入框选择器: %s", selector)

    if not selector:
        raise EditorError("未找到文章标题输入框")

    # 聚焦标题输入框并清空已有内容
    page.evaluate(f"""
    (() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return;
        el.focus();
        el.select && el.select();
    }})()
    """)
    time.sleep(0.2)

    # 全选删除已有内容
    page.select_all_and_delete()
    time.sleep(0.1)

    # 用 CDP Input.insertText 输入标题（触发 React onChange）
    page._send_session("Input.insertText", {"text": title})
    time.sleep(0.3)

    # 验证标题是否成功写入
    actual = page.evaluate(f"""
    (() => {{
        const el = document.querySelector({json.dumps(selector)});
        return el ? el.value || el.textContent || '' : '';
    }})()
    """) or ""
    if title[:10] not in actual:
        logger.warning("标题验证失败: expected=%s, actual=%s", title[:20], actual[:20])

    logger.info("标题已填写: %s", title[:50])


def _fill_body(page, content: str) -> None:
    """在编辑器中填入文章正文。"""
    # 等待编辑器激活（知乎文章编辑器可能是 Draft.js 或其他富文本编辑器）
    deadline = time.monotonic() + 10.0
    editor_found = False
    while time.monotonic() < deadline:
        has_editor = page.evaluate("""
            document.querySelector(
                '.public-DraftEditor-content[contenteditable="true"], '
                + '.WriteIndex-editor [contenteditable="true"], '
                + '.PostEditor-body [contenteditable="true"], '
                + '[role="textbox"][contenteditable="true"], '
                + '.DraftEditor-editorContainer [contenteditable="true"]'
            ) !== null
            """)
        if has_editor:
            editor_found = True
            break
        time.sleep(0.5)

    if not editor_found:
        raise EditorError("未找到文章正文编辑区域")

    # 聚焦编辑器
    page.evaluate("""
        (() => {
            const editor = document.querySelector(
                '.public-DraftEditor-content[contenteditable="true"], '
                + '.WriteIndex-editor [contenteditable="true"], '
                + '.PostEditor-body [contenteditable="true"], '
                + '[role="textbox"][contenteditable="true"], '
                + '.DraftEditor-editorContainer [contenteditable="true"]'
            );
            if (editor) {
                editor.focus();
                const range = document.createRange();
                const sel = window.getSelection();
                range.selectNodeContents(editor);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
            }
        })()
        """)
    time.sleep(0.3)

    # 全选清空已有内容
    page.select_all_and_delete()
    time.sleep(0.2)

    # 尝试富文本粘贴模式
    html_content = _markdown_to_html(content)
    if html_content:
        success = _paste_rich_text(page, html_content, content)
        if success:
            logger.info("文章正文已通过富文本粘贴填写 (%d 字符)", len(content))
            return

    # 回退：纯文本逐段输入
    logger.info("使用纯文本模式输入")
    _fill_plain_text(page, content)
    logger.info("文章正文已填写 (%d 字符)", len(content))


def _paste_rich_text(page, html: str, plain_text: str) -> bool:
    """通过模拟剪贴板粘贴事件将富文本粘贴到编辑器。"""
    html_escaped = json.dumps(html)
    plain_escaped = json.dumps(plain_text)

    js_code = f"""
    (() => {{
        const editor = document.querySelector(
            '.public-DraftEditor-content[contenteditable="true"], '
            + '.WriteIndex-editor [contenteditable="true"], '
            + '.PostEditor-body [contenteditable="true"], '
            + '[role="textbox"][contenteditable="true"], '
            + '.DraftEditor-editorContainer [contenteditable="true"]'
        );
        if (!editor) return 'no_editor';

        editor.focus();

        const dt = new DataTransfer();
        dt.setData('text/html', {html_escaped});
        dt.setData('text/plain', {plain_escaped});

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

    time.sleep(1.5)

    # 验证是否有内容被写入
    has_content = page.evaluate("""
    (() => {
        const editor = document.querySelector(
            '.public-DraftEditor-content[contenteditable="true"], '
            + '.WriteIndex-editor [contenteditable="true"], '
            + '.PostEditor-body [contenteditable="true"], '
            + '[role="textbox"][contenteditable="true"], '
            + '.DraftEditor-editorContainer [contenteditable="true"]'
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
    paragraphs = content.split("\n")
    for i, para in enumerate(paragraphs):
        if para:
            page._send_session("Input.insertText", {"text": para})
            time.sleep(random.uniform(0.1, 0.3))

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


def _click_publish(page, title: str) -> dict:
    """点击发布按钮发布文章。

    知乎文章发布流程（2026 版）：
    1. 底部固定栏有"发布"按钮（Button--primary），可能是 enabled 或 disabled
    2. 点击后可能直接发布，也可能先弹出"发布设置"面板
    3. 如果弹出面板，面板底部也有一个"发布"按钮用于最终确认
    """
    # 等待发布按钮变为可用（填写内容后可能有短暂延迟）
    deadline = time.monotonic() + 10.0
    btn_enabled = False
    while time.monotonic() < deadline:
        state = page.evaluate("""
        (() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.replace(/\\u200b/g, '').trim();
                if (text === '发布' && btn.className.includes('primary')) {
                    return btn.disabled ? 'disabled' : 'enabled';
                }
            }
            return 'not_found';
        })()
        """)
        if state == "enabled":
            btn_enabled = True
            break
        logger.debug("发布按钮状态: %s", state)
        time.sleep(0.5)

    if not btn_enabled:
        logger.warning("发布按钮始终不可用 (最后状态: %s)", state)
        # 截图保存以便调试
        _debug_screenshot(page, "publish_disabled")
        return {
            "success": False,
            "error": f"发布按钮不可用 ({state})，请检查标题和正文是否正确填写",
        }

    # 获取按钮位置并用 CDP 鼠标事件点击（isTrusted=true）
    box = page.evaluate("""
    (() => {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const text = btn.textContent.replace(/\\u200b/g, '').trim();
            if (text === '发布' && btn.className.includes('primary') && !btn.disabled) {
                const rect = btn.getBoundingClientRect();
                return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
            }
        }
        return null;
    })()
    """)
    if not box:
        return {"success": False, "error": "无法定位发布按钮坐标"}

    x = box["x"] + random.uniform(-2, 2)
    y = box["y"] + random.uniform(-2, 2)
    page.mouse_move(x, y)
    time.sleep(0.1)
    page.mouse_click(x, y)
    logger.info("已点击发布按钮 (%.0f, %.0f)", x, y)

    # 等待可能出现的发布设置面板或直接跳转
    time.sleep(3.0)

    # 检查是否已跳转到文章页（发布成功）
    current_url = page.evaluate("location.href") or ""
    if "/p/" in current_url and "/edit" not in current_url:
        logger.info("发布成功，已跳转: %s", current_url)
        return {
            "success": True,
            "title": title,
            "status": "文章已发布",
            "url": current_url,
        }

    # 可能弹出了发布设置面板，查找面板中的确认"发布"按钮
    confirm_result = page.evaluate("""
    (() => {
        const buttons = document.querySelectorAll('button');
        const publishBtns = [];
        for (let i = 0; i < buttons.length; i++) {
            const btn = buttons[i];
            const text = btn.textContent.replace(/\\u200b/g, '').trim();
            if (text === '发布' && !btn.disabled && btn.className.includes('primary')) {
                const rect = btn.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    publishBtns.push({index: i, x: rect.left + rect.width/2, y: rect.top + rect.height/2});
                }
            }
        }
        return publishBtns.length > 0 ? publishBtns[publishBtns.length - 1] : null;
    })()
    """)

    if confirm_result:
        logger.info("发现确认发布按钮，再次点击...")
        cx = confirm_result["x"] + random.uniform(-2, 2)
        cy = confirm_result["y"] + random.uniform(-2, 2)
        page.mouse_move(cx, cy)
        time.sleep(0.1)
        page.mouse_click(cx, cy)
        time.sleep(5.0)

    # 最终检查发布结果
    post_check = page.evaluate("""
    (() => {
        const url = location.href;
        if (url.includes('/p/') && !url.includes('/edit')) return 'redirected: ' + url;
        const toast = document.querySelector(
            '.Notification, .Toast, [class*=toast], [class*=Toast]');
        if (toast) return 'toast: ' + toast.textContent.trim().substring(0, 100);
        return 'url: ' + url;
    })()
    """)
    logger.info("发布后检查: %s", post_check)

    success = "redirected" in (post_check or "") or "/edit" not in (post_check or "")
    result_dict = {
        "success": success,
        "title": title,
        "status": "文章已发布" if success else "发布结果不确定",
        "postCheck": post_check,
    }
    if not success:
        _debug_screenshot(page, "publish_result")
    return result_dict


def _debug_screenshot(page, name: str) -> None:
    """保存调试截图到 /tmp。"""
    import base64

    try:
        result = page._send_session(
            "Page.captureScreenshot", {"format": "png"}
        )
        data = result.get("data", "")
        if data:
            path = f"/tmp/zhihu_debug_{name}.png"
            with open(path, "wb") as f:
                f.write(base64.b64decode(data))
            logger.info("调试截图: %s", path)
    except Exception as e:
        logger.debug("截图失败: %s", e)
