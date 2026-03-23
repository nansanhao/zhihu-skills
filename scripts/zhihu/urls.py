"""知乎 URL 常量和构建函数。"""

from urllib.parse import urlencode

# 基础页面
HOME_URL = "https://www.zhihu.com"
EXPLORE_URL = "https://www.zhihu.com/explore"
LOGIN_URL = "https://www.zhihu.com/signin"
CREATOR_URL = "https://www.zhihu.com/creator"

# 邀请回答页
INVITED_QUESTIONS_URL = "https://www.zhihu.com/creator/featured-question/invited"

# 写回答页
ANSWER_URL_PREFIX = "https://www.zhihu.com/question"

# 写文章页
ARTICLE_WRITE_URL = "https://zhuanlan.zhihu.com/write"


def make_question_url(question_id: str) -> str:
    """构建问题详情页 URL。"""
    return f"https://www.zhihu.com/question/{question_id}"


def make_answer_url(question_id: str, answer_id: str) -> str:
    """构建回答详情页 URL。"""
    return f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}"


def make_search_url(keyword: str, search_type: str = "content") -> str:
    """构建搜索结果页 URL。

    Args:
        keyword: 搜索关键词。
        search_type: 搜索类型 (content/people/topic)。
    """
    params = urlencode({"q": keyword, "type": search_type})
    return f"https://www.zhihu.com/search?{params}"


def make_user_profile_url(user_id: str) -> str:
    """构建用户主页 URL。"""
    return f"https://www.zhihu.com/people/{user_id}"


def make_article_url(article_id: str) -> str:
    """构建文章详情页 URL。"""
    return f"https://zhuanlan.zhihu.com/p/{article_id}"
