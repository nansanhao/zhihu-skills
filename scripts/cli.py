"""知乎自动化统一 CLI 入口。

全局选项: --host, --port
输出: JSON（ensure_ascii=False）
退出码: 0=成功, 1=未登录, 2=错误
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import sys
import tempfile

# 将 scripts 目录加入 path
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _scripts_dir)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("zhihu-cli")

# Windows 控制台编码
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _output(data: dict, exit_code: int = 0) -> None:
    """输出 JSON 并退出。"""
    print(json.dumps(data, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


def _session_tab_file(port: int) -> str:
    return os.path.join(tempfile.gettempdir(), "zhihu", f"session_tab_{port}.txt")


def _save_session_tab(target_id: str, port: int) -> None:
    path = _session_tab_file(port)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(target_id)


def _load_session_tab(port: int) -> str | None:
    with contextlib.suppress(FileNotFoundError):
        with open(_session_tab_file(port)) as f:
            data = f.read().strip()
        return data or None
    return None


def _clear_session_tab(port: int) -> None:
    with contextlib.suppress(FileNotFoundError):
        os.remove(_session_tab_file(port))


def _ensure_browser(args: argparse.Namespace):
    """确保 Chrome 可用并返回已连接的 Browser 实例。"""
    from cdp_engine.cdp import Browser
    from chrome_launcher import ensure_chrome, has_display

    if not ensure_chrome(port=args.port, headless=not has_display()):
        _output(
            {"success": False, "error": "无法启动 Chrome，请检查 Chrome 是否已安装"},
            exit_code=2,
        )

    browser = Browser(host=args.host, port=args.port)
    browser.connect()
    return browser


def _connect(args: argparse.Namespace):
    """连接到 Chrome 并返回 (browser, page)。"""
    browser = _ensure_browser(args)

    # 优先复用上次留下的 tab
    saved_id = _load_session_tab(args.port)
    if saved_id:
        page = browser.get_page_by_target_id(saved_id)
        if page:
            _save_session_tab(page.target_id, args.port)
            return browser, page

    page = browser.get_or_create_page()
    _save_session_tab(page.target_id, args.port)
    return browser, page


def _connect_existing(args: argparse.Namespace):
    """连接到已有页面（用于分步操作的后续步骤）。"""
    browser = _ensure_browser(args)
    page = browser.get_existing_page()
    if not page:
        _output(
            {"success": False, "error": "未找到已打开的页面，请先执行前置步骤"},
            exit_code=2,
        )
    return browser, page


# ========== 子命令实现 ==========


def cmd_check_login(args: argparse.Namespace) -> None:
    """检查知乎登录状态。"""
    from zhihu.login import check_login_status, navigate_to_login

    browser, page = _connect(args)
    try:
        logged_in = check_login_status(page)
        if logged_in:
            _output({"logged_in": True, "message": "已登录"})
        else:
            # 未登录时引导用户登录
            login_info = navigate_to_login(page)
            _save_session_tab(page.target_id, args.port)
            _output(login_info, exit_code=1)
    finally:
        browser.close()


def cmd_wait_login(args: argparse.Namespace) -> None:
    """等待用户完成登录。"""
    from zhihu.login import wait_for_login

    browser, page = _connect(args)
    try:
        success = wait_for_login(page, timeout=args.timeout)
        _output(
            {
                "logged_in": success,
                "message": "登录成功" if success else "等待超时，请重试",
            },
            exit_code=0 if success else 2,
        )
    finally:
        browser.close()


def cmd_search(args: argparse.Namespace) -> None:
    """搜索知乎内容。"""
    from zhihu.search import search

    browser, page = _connect(args)
    try:
        results = search(page, args.keyword, args.type)
        _output({
            "results": [r.to_dict() for r in results],
            "count": len(results),
            "keyword": args.keyword,
        })
    finally:
        browser.close_page(page)
        browser.close()


def cmd_question_detail(args: argparse.Namespace) -> None:
    """获取问题详情。"""
    from zhihu.question import get_question_detail

    browser, page = _connect(args)
    try:
        detail = get_question_detail(page, args.question_id)
        _output(detail)
    finally:
        browser.close_page(page)
        browser.close()


def cmd_invited_questions(args: argparse.Namespace) -> None:
    """获取被邀请回答的问题列表。"""
    from zhihu.invitation import get_invited_questions

    browser, page = _connect(args)
    try:
        questions = get_invited_questions(page)
        _output({
            "questions": [q.to_dict() for q in questions],
            "count": len(questions),
        })
    finally:
        browser.close_page(page)
        browser.close()


def cmd_write_answer(args: argparse.Namespace) -> None:
    """撰写回答（只填写，不发布）。"""
    from zhihu.answer import write_answer

    with open(args.content_file, encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        _output({"success": False, "error": "回答内容不能为空"}, exit_code=2)

    browser, page = _connect(args)
    try:
        result = write_answer(page, args.question_id, content, submit=False)
        if result.get("success"):
            # 不关闭页面，等待用户确认
            _output(result)
        else:
            _output(result, exit_code=2)
    finally:
        browser.close()


def cmd_submit_answer(args: argparse.Namespace) -> None:
    """提交已编辑的回答。"""
    from zhihu.answer import submit_answer

    browser, page = _connect_existing(args)
    try:
        result = submit_answer(page)
        if result.get("success"):
            _output(result)
        else:
            _output(result, exit_code=2)
    finally:
        browser.close_page(page)
        browser.close()


def cmd_answer_direct(args: argparse.Namespace) -> None:
    """一步到位撰写并发布回答。"""
    from zhihu.answer import write_answer

    with open(args.content_file, encoding="utf-8") as f:
        content = f.read().strip()

    if not content:
        _output({"success": False, "error": "回答内容不能为空"}, exit_code=2)

    browser, page = _connect(args)
    try:
        result = write_answer(page, args.question_id, content, submit=True)
        if result.get("success"):
            _output(result)
        else:
            _output(result, exit_code=2)
    finally:
        browser.close_page(page)
        browser.close()


# ========== 参数解析 ==========


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="zhihu-cli",
        description="知乎自动化 CLI",
    )

    # 全局选项
    parser.add_argument(
        "--host", default="127.0.0.1", help="Chrome 调试主机 (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=9222, help="Chrome 调试端口 (default: 9222)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-login
    sub = subparsers.add_parser("check-login", help="检查登录状态")
    sub.set_defaults(func=cmd_check_login)

    # wait-login
    sub = subparsers.add_parser("wait-login", help="等待登录完成")
    sub.add_argument(
        "--timeout", type=float, default=120.0, help="等待超时秒数 (default: 120)"
    )
    sub.set_defaults(func=cmd_wait_login)

    # search
    sub = subparsers.add_parser("search", help="搜索知乎内容")
    sub.add_argument("--keyword", required=True, help="搜索关键词")
    sub.add_argument(
        "--type", default="content", help="搜索类型: content/people/topic"
    )
    sub.set_defaults(func=cmd_search)

    # question-detail
    sub = subparsers.add_parser("question-detail", help="获取问题详情")
    sub.add_argument("--question-id", required=True, help="问题 ID")
    sub.set_defaults(func=cmd_question_detail)

    # invited-questions
    sub = subparsers.add_parser("invited-questions", help="获取被邀请回答的问题")
    sub.set_defaults(func=cmd_invited_questions)

    # write-answer（只填写，不发布）
    sub = subparsers.add_parser("write-answer", help="撰写回答（不发布，供预览）")
    sub.add_argument("--question-id", required=True, help="问题 ID")
    sub.add_argument("--content-file", required=True, help="回答内容文件路径")
    sub.set_defaults(func=cmd_write_answer)

    # submit-answer（提交回答）
    sub = subparsers.add_parser("submit-answer", help="提交已编辑的回答")
    sub.set_defaults(func=cmd_submit_answer)

    # answer（一步到位）
    sub = subparsers.add_parser("answer", help="一步到位撰写并发布回答")
    sub.add_argument("--question-id", required=True, help="问题 ID")
    sub.add_argument("--content-file", required=True, help="回答内容文件路径")
    sub.set_defaults(func=cmd_answer_direct)

    return parser


def main() -> None:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()

    try:
        args.func(args)
    except Exception as e:
        logger.error("执行失败: %s", e, exc_info=True)
        _output({"success": False, "error": str(e)}, exit_code=2)


if __name__ == "__main__":
    main()
