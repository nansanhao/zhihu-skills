"""知乎登录管理。"""

from __future__ import annotations

import json
import logging
import time

from .selectors import (
    LOGIN_AVATAR,
    LOGIN_BUTTON,
    LOGIN_MODAL,
    LOGIN_QRCODE_IMG,
)
from .urls import HOME_URL

logger = logging.getLogger(__name__)


def check_login_status(page) -> bool:
    """检查知乎登录状态。

    Args:
        page: CDP Page 对象。

    Returns:
        True 已登录，False 未登录。
    """
    current_url = page.evaluate("location.href") or ""
    if "zhihu.com" not in current_url:
        page.navigate(HOME_URL)
        page.wait_for_load()

    # 等待页面稳定
    page.wait_dom_stable(timeout=8.0)

    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        # 已登录：顶部有用户头像
        if page.has_element(LOGIN_AVATAR):
            return True
        # 未登录：有登录按钮
        if page.has_element(LOGIN_BUTTON):
            return False
        time.sleep(0.3)

    # 兜底检测：通过 JS 检查页面中是否有创作中心入口或头像
    try:
        fallback = page.evaluate("""
        (() => {
            const sel = '.AppHeader img.Avatar, .AppHeader img[alt*="主页"]';
            const avatar = document.querySelector(sel);
            if (avatar) return 'logged_in';
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.textContent.includes('创作中心')) return 'logged_in';
            }
            return 'not_logged_in';
        })()
        """)
        if fallback == "logged_in":
            return True
    except Exception:
        pass

    return page.has_element(LOGIN_AVATAR)


def navigate_to_login(page) -> dict:
    """导航到知乎登录页，返回登录状态信息。

    知乎采用扫码/手机号登录。此函数导航到首页并触发登录弹窗。

    Returns:
        登录状态字典。
    """
    page.navigate(HOME_URL)
    page.wait_for_load()
    page.wait_dom_stable()

    # 如果已登录则直接返回
    if page.has_element(LOGIN_AVATAR):
        return {"logged_in": True, "message": "已登录"}

    # 点击登录按钮触发弹窗
    if page.has_element(LOGIN_BUTTON):
        page.click_element(LOGIN_BUTTON)
        time.sleep(1.5)

    # 等待登录弹窗出现
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if page.has_element(LOGIN_MODAL):
            break
        time.sleep(0.3)

    # 尝试获取二维码
    qrcode_info = _try_get_qrcode(page)

    result = {
        "logged_in": False,
        "login_method": "qrcode",
        "message": "请使用知乎 App 扫描二维码登录，或在浏览器中手动完成登录",
    }

    if qrcode_info:
        result.update(qrcode_info)

    return result


def _try_get_qrcode(page) -> dict | None:
    """尝试从登录弹窗获取二维码信息。"""
    try:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            src = page.evaluate(
                f"document.querySelector({json.dumps(LOGIN_QRCODE_IMG)})?.src || ''"
            )
            if src and src.startswith("http"):
                return {"qrcode_image_url": src}
            if src and "base64," in src:
                return {"qrcode_image_url": src}
            time.sleep(0.5)
    except Exception:
        logger.debug("获取登录二维码失败")
    return None


def wait_for_login(page, timeout: float = 120.0) -> bool:
    """等待登录完成。

    在登录弹窗打开后，轮询检测用户是否完成登录。

    Args:
        page: CDP Page 对象。
        timeout: 超时时间（秒）。

    Returns:
        True 登录成功，False 超时。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # 弹窗消失 + 头像出现 = 登录成功
        if page.has_element(LOGIN_AVATAR):
            logger.info("知乎登录成功")
            return True
        # 页面可能跳转了
        current_url = page.evaluate("location.href") or ""
        if (
            "zhihu.com" in current_url
            and not page.has_element(LOGIN_MODAL)
            and page.has_element(LOGIN_AVATAR)
        ):
            logger.info("知乎登录成功（页面跳转后检测）")
            return True
        time.sleep(1.0)
    return False


def get_current_user_info(page) -> dict:
    """获取当前登录用户信息（best-effort）。

    Returns:
        用户信息字典 {"name": ..., "url": ...}
    """
    try:
        name = page.evaluate(
            """
            (() => {
                const el = document.querySelector('.AppHeader-profile .Avatar');
                return el ? el.getAttribute('alt') || '' : '';
            })()
            """
        )
        url = page.evaluate(
            """
            (() => {
                const el = document.querySelector('.AppHeader-profileEntry a');
                return el ? el.getAttribute('href') || '' : '';
            })()
            """
        )
        return {"name": name or "", "url": url or ""}
    except Exception:
        return {"name": "", "url": ""}
