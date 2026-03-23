"""CDP 引擎异常体系。"""


class CDPError(Exception):
    """CDP 通信异常。"""


class ElementNotFoundError(CDPError):
    """页面元素未找到。"""

    def __init__(self, selector: str) -> None:
        self.selector = selector
        super().__init__(f"未找到元素: {selector}")
