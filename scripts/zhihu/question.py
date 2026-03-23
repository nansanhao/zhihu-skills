"""知乎问题详情获取。"""

from __future__ import annotations

import json
import logging
import time

from .errors import QuestionNotFoundError
from .types import AnswerInfo, QuestionDetail
from .urls import make_question_url

logger = logging.getLogger(__name__)


def get_question_detail(page, question_id: str) -> dict:
    """获取问题详情及回答列表。

    Args:
        page: CDP Page 对象。
        question_id: 问题 ID。

    Returns:
        包含问题信息和回答列表的字典。
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
        # 可能是 404 或其他错误页
        error_text = page.evaluate("document.body?.textContent?.substring(0, 200) || ''")
        if "404" in (error_text or "") or "不存在" in (error_text or ""):
            raise QuestionNotFoundError(question_id)

    # 提取问题信息
    question = _extract_question_info(page, question_id)

    # 提取回答列表
    answers = _extract_answers(page)

    return {
        "question": question.to_dict(),
        "answers": [a.to_dict() for a in answers],
        "answerCount": len(answers),
    }


def _extract_question_info(page, question_id: str) -> QuestionDetail:
    """从 DOM 提取问题信息。"""
    js_code = """
    (() => {
        const title = document.querySelector('.QuestionHeader-title')
            ?.textContent?.trim() || '';
        const detail = document.querySelector('.QuestionHeader-detail .RichText')
            ?.textContent?.trim() || '';

        // 提取关注数、浏览量等
        const numberItems = document.querySelectorAll(
            '.NumberBoard-itemInner'
        );
        let followerCount = '';
        let viewCount = '';
        numberItems.forEach((item) => {
            const label = item.querySelector('.NumberBoard-itemName')
                ?.textContent?.trim() || '';
            const value = item.querySelector('.NumberBoard-itemValue')
                ?.textContent?.trim() || '';
            if (label.includes('关注')) followerCount = value;
            if (label.includes('浏览')) viewCount = value;
        });

        // 提取回答数
        const answerCount = document.querySelector(
            '.List-headerText span'
        )?.textContent?.trim() || '';

        // 提取话题标签
        const topicLinks = document.querySelectorAll(
            '.QuestionHeader a[href*="topic"]'
        );
        const topics = [];
        topicLinks.forEach(el => {
            const t = el.textContent?.trim();
            if (t) topics.push(t);
        });

        return JSON.stringify({
            title, detail, followerCount, viewCount, answerCount, topics
        });
    })()
    """
    result = page.evaluate(js_code)
    if not result:
        return QuestionDetail(question_id=question_id)

    data = json.loads(result)
    return QuestionDetail(
        question_id=question_id,
        title=data.get("title", ""),
        detail=data.get("detail", ""),
        answer_count=data.get("answerCount", ""),
        follower_count=data.get("followerCount", ""),
        view_count=data.get("viewCount", ""),
        topics=data.get("topics", []),
    )


def _extract_answers(page) -> list[AnswerInfo]:
    """从 DOM 提取回答列表。"""
    js_code = """
    (() => {
        const items = [];
        // 直接选择 .ContentItem.AnswerItem 避免 List-item 层级重复
        const answerItems = document.querySelectorAll('.ContentItem.AnswerItem');
        answerItems.forEach((item, index) => {
            if (index >= 10) return;

            // answerId 从元素的 name 属性获取
            const answerId = item.getAttribute('name') || '';

            // 作者名优先从 itemprop 结构化数据提取
            const authorMeta = item.querySelector('[itemprop="author"] meta[itemprop="name"]');
            let authorName = authorMeta ? authorMeta.getAttribute('content') || '' : '';
            // 备选：从 AuthorInfo-name 区域提取
            if (!authorName) {
                const nameLink = item.querySelector('.AuthorInfo-name .UserLink-link');
                authorName = nameLink ? nameLink.textContent.trim() : '';
            }
            // 再备选：从 RichText 开头 b 标签提取（搜索结果页格式）
            if (!authorName) {
                const boldEl = item.querySelector('.RichText b[data-first-child]');
                authorName = boldEl ? boldEl.textContent.trim() : '';
            }

            // 作者链接
            const authorLink = item.querySelector('.AuthorInfo-name .UserLink-link');
            const authorUrl = authorLink ? authorLink.getAttribute('href') || '' : '';

            // 内容摘要
            const richText = item.querySelector('.RichText');
            let contentSnippet = richText ? richText.textContent.trim().substring(0, 300) : '';

            // 赞同数优先从 itemprop 提取
            const voteMeta = item.querySelector('meta[itemprop="upvoteCount"]');
            let voteCount = voteMeta ? voteMeta.getAttribute('content') || '' : '';
            if (!voteCount) {
                const voteBtn = item.querySelector('button[aria-label*="赞同"]');
                if (voteBtn) {
                    const label = voteBtn.getAttribute('aria-label') || '';
                    const m = label.match(/(\\d+)/);
                    voteCount = m ? m[1] : '';
                }
            }

            // 评论数优先从 itemprop 提取
            const commentMeta = item.querySelector('meta[itemprop="commentCount"]');
            let commentCount = commentMeta ? commentMeta.getAttribute('content') || '' : '';
            if (!commentCount) {
                const allBtns = item.querySelectorAll('button');
                allBtns.forEach(btn => {
                    const t = btn.textContent.trim();
                    const m = t.match(/(\\d+)\\s*条评论/);
                    if (m) commentCount = m[1];
                });
            }

            // 创建时间
            const dateMeta = item.querySelector('meta[itemprop="dateCreated"]');
            const createdTime = dateMeta ? dateMeta.getAttribute('content') || '' : '';

            items.push({
                answerId,
                authorName,
                authorUrl,
                contentSnippet,
                voteCount,
                commentCount,
                createdTime,
            });
        });
        return JSON.stringify(items);
    })()
    """
    result = page.evaluate(js_code)
    if not result:
        return []

    data = json.loads(result)
    return [
        AnswerInfo(
            answer_id=d.get("answerId", ""),
            author_name=d.get("authorName", ""),
            author_url=d.get("authorUrl", ""),
            content_snippet=d.get("contentSnippet", ""),
            vote_count=d.get("voteCount", ""),
            comment_count=d.get("commentCount", ""),
            created_time=d.get("createdTime", ""),
        )
        for d in data
    ]
