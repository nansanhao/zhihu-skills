"""知乎数据类型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field

# ========== 搜索结果 ==========


@dataclass
class SearchResultItem:
    """搜索结果条目。"""

    title: str = ""
    url: str = ""
    content_snippet: str = ""
    author_name: str = ""
    author_url: str = ""
    vote_count: str = ""
    comment_count: str = ""
    item_type: str = ""  # question / answer / article

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "contentSnippet": self.content_snippet,
            "authorName": self.author_name,
            "authorUrl": self.author_url,
            "voteCount": self.vote_count,
            "commentCount": self.comment_count,
            "itemType": self.item_type,
        }


# ========== 问题详情 ==========


@dataclass
class QuestionDetail:
    """问题详情。"""

    question_id: str = ""
    title: str = ""
    detail: str = ""
    answer_count: str = ""
    follower_count: str = ""
    view_count: str = ""
    topics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "questionId": self.question_id,
            "title": self.title,
            "detail": self.detail,
            "answerCount": self.answer_count,
            "followerCount": self.follower_count,
            "viewCount": self.view_count,
            "topics": self.topics,
        }


# ========== 回答 ==========


@dataclass
class AnswerInfo:
    """回答摘要信息。"""

    answer_id: str = ""
    author_name: str = ""
    author_url: str = ""
    content_snippet: str = ""
    vote_count: str = ""
    comment_count: str = ""
    created_time: str = ""

    def to_dict(self) -> dict:
        return {
            "answerId": self.answer_id,
            "authorName": self.author_name,
            "authorUrl": self.author_url,
            "contentSnippet": self.content_snippet,
            "voteCount": self.vote_count,
            "commentCount": self.comment_count,
            "createdTime": self.created_time,
        }


# ========== 邀请回答 ==========


@dataclass
class InvitedQuestion:
    """被邀请回答的问题。"""

    question_id: str = ""
    title: str = ""
    question_url: str = ""
    inviter_name: str = ""
    follower_count: str = ""
    answer_count: str = ""
    detail_snippet: str = ""
    invite_time: str = ""

    def to_dict(self) -> dict:
        return {
            "questionId": self.question_id,
            "title": self.title,
            "questionUrl": self.question_url,
            "inviterName": self.inviter_name,
            "followerCount": self.follower_count,
            "answerCount": self.answer_count,
            "detailSnippet": self.detail_snippet,
            "inviteTime": self.invite_time,
        }
