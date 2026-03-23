"""知乎自动化异常体系。"""


class ZhihuError(Exception):
    """知乎自动化基础异常。"""


class NotLoggedInError(ZhihuError):
    """未登录。"""

    def __init__(self) -> None:
        super().__init__("未登录，请先登录知乎")


class NoResultsError(ZhihuError):
    """没有搜索结果。"""

    def __init__(self) -> None:
        super().__init__("没有搜索到相关结果")


class QuestionNotFoundError(ZhihuError):
    """问题不存在。"""

    def __init__(self, question_id: str = "") -> None:
        msg = f"问题不存在: {question_id}" if question_id else "问题不存在"
        super().__init__(msg)


class AnswerNotFoundError(ZhihuError):
    """回答不存在。"""

    def __init__(self) -> None:
        super().__init__("回答不存在")


class PageNotAccessibleError(ZhihuError):
    """页面不可访问。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"页面不可访问: {reason}")


class PublishError(ZhihuError):
    """发布失败。"""


class EditorError(ZhihuError):
    """编辑器操作失败。"""

    def __init__(self, detail: str = "") -> None:
        msg = f"编辑器操作失败: {detail}" if detail else "编辑器操作失败"
        super().__init__(msg)


class RateLimitError(ZhihuError):
    """请求频率过高。"""

    def __init__(self) -> None:
        super().__init__("请求太频繁，请稍后再试")
