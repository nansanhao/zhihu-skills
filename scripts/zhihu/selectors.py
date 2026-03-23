"""知乎页面 CSS 选择器常量。

所有选择器集中管理，知乎改版时只需修改此文件。
"""

# ========== 登录状态检测 ==========
# 已登录：顶部导航栏有用户头像（多个选择器兼容）
LOGIN_AVATAR = ".AppHeader-profileAvatar, .AppHeader-profile, .AppHeader .Avatar"
# 未登录：有登录按钮
LOGIN_BUTTON = (
    'button[class*="SignContainer-button"], '
    'button[class*="Login"], .SignContainer .Button'
)
# 登录弹窗
LOGIN_MODAL = ".signFlowModal, .Modal-content"
# 登录弹窗中的二维码
LOGIN_QRCODE_IMG = ".Qrcode-img img, [class*=Qrcode] img"
