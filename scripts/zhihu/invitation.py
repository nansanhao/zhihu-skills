"""知乎邀请回答功能。"""

from __future__ import annotations

import json
import logging
import time

from .types import InvitedQuestion
from .urls import INVITED_QUESTIONS_URL

logger = logging.getLogger(__name__)


def get_invited_questions(page) -> list[InvitedQuestion]:
    """获取被邀请回答的问题列表。

    Args:
        page: CDP Page 对象。

    Returns:
        邀请回答的问题列表。
    """
    page.navigate(INVITED_QUESTIONS_URL)
    page.wait_for_load()
    page.wait_dom_stable(timeout=10.0)
    time.sleep(2)

    return _extract_invitations(page)


def _extract_invitations(page) -> list[InvitedQuestion]:
    """从 DOM 提取邀请回答列表。"""
    js_code = """
    (() => {
        const items = [];

        // 策略1：通过稳定的 BEM 类名 ToolsQuestion-QuestionItemV2-ignoreButton 定位卡片
        const ignoreBtns = document.querySelectorAll(
            '.ToolsQuestion-QuestionItemV2-ignoreButton'
        );

        if (ignoreBtns.length > 0) {
            ignoreBtns.forEach((btn, idx) => {
                if (idx >= 20) return;
                // 卡片是 ignoreButton 向上 2 层的容器
                const card = btn.parentElement && btn.parentElement.parentElement
                    ? btn.parentElement.parentElement : null;
                if (!card) return;

                // 标题链接
                const titleLink = card.querySelector('a[href*="question"]');
                const title = titleLink ? titleLink.textContent.trim() : '';
                const questionUrl = titleLink
                    ? titleLink.getAttribute('href') || '' : '';
                const qMatch = questionUrl.match(/question\\/(\\d+)/);
                const questionId = qMatch ? qMatch[1] : '';
                if (!title || !questionId) return;

                // 统计信息 "N 回答 · N 关注" — 在标题同级的 div 中
                const allDivs = card.querySelectorAll('div');
                let answerCount = '';
                let followerCount = '';
                allDivs.forEach(div => {
                    const t = div.textContent.trim();
                    if (t.match(/\\d+\\s*回答/) && t.match(/\\d+\\s*关注/)) {
                        const am = t.match(/(\\d+)\\s*回答/);
                        const fm = t.match(/(\\d+)\\s*关注/);
                        if (am) answerCount = am[1];
                        if (fm) followerCount = fm[1];
                    }
                });

                // 邀请人名字 — 在包含头像 img 的容器旁的 div 中
                let inviterName = '';
                const imgEl = card.querySelector('img');
                if (imgEl) {
                    const imgParent = imgEl.parentElement;
                    if (imgParent) {
                        // 名字 div 紧跟 img 后面
                        const siblings = imgParent.querySelectorAll('div');
                        siblings.forEach(s => {
                            const t = s.textContent.trim();
                            // 名字通常很短，不含"回答""关注"等
                            if (t && t.length < 20 && !t.includes('回答')
                                && !t.includes('关注') && !t.includes('·')) {
                                inviterName = t;
                            }
                        });
                    }
                }

                // 时间信息
                let inviteTime = '';
                allDivs.forEach(div => {
                    const t = div.textContent.trim();
                    const tm = t.match(/(\\d+\\s*(?:分钟|小时|天|周|月)前)/);
                    if (tm) inviteTime = tm[1];
                });

                items.push({
                    questionId,
                    title,
                    questionUrl,
                    inviterName,
                    followerCount,
                    answerCount,
                    inviteTime,
                    detailSnippet: '',
                });
            });
            return JSON.stringify(items);
        }

        // 策略2：降级 — 通用选择器（兼容旧版页面）
        const links = document.querySelectorAll('a[href*="/question/"]');
        const seen = new Set();
        links.forEach(link => {
            if (items.length >= 20) return;
            const href = link.getAttribute('href') || '';
            const qm = href.match(/question\\/(\\d+)/);
            if (!qm) return;
            const qid = qm[1];
            if (seen.has(qid)) return;
            seen.add(qid);
            items.push({
                questionId: qid,
                title: link.textContent.trim(),
                questionUrl: href,
                inviterName: '',
                followerCount: '',
                answerCount: '',
                inviteTime: '',
                detailSnippet: '',
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
        InvitedQuestion(
            question_id=d.get("questionId", ""),
            title=d.get("title", ""),
            question_url=d.get("questionUrl", ""),
            inviter_name=d.get("inviterName", ""),
            follower_count=d.get("followerCount", ""),
            answer_count=d.get("answerCount", ""),
            detail_snippet=d.get("detailSnippet", ""),
            invite_time=d.get("inviteTime", ""),
        )
        for d in data
    ]
