"""知乎搜索功能。"""

from __future__ import annotations

import json
import logging
import time

from .types import SearchResultItem
from .urls import make_search_url

logger = logging.getLogger(__name__)


def search(page, keyword: str, search_type: str = "content") -> list[SearchResultItem]:
    """搜索知乎内容。

    Args:
        page: CDP Page 对象。
        keyword: 搜索关键词。
        search_type: 搜索类型 (content/people/topic)。

    Returns:
        搜索结果列表。
    """
    url = make_search_url(keyword, search_type)
    page.navigate(url)
    page.wait_for_load()
    page.wait_dom_stable(timeout=10.0)

    # 等待搜索结果加载
    time.sleep(2)

    # 通过 DOM 提取搜索结果
    results = _extract_search_results(page)
    return results


def _extract_search_results(page) -> list[SearchResultItem]:
    """从页面 DOM 提取搜索结果。"""
    js_code = """
    (() => {
        const items = [];
        const seen = new Set(); // 去重用

        // 只选择包含 ContentItem 的 List-item（过滤广告、专业卡片等非内容项）
        const listItems = document.querySelectorAll('.List-item');
        listItems.forEach((card) => {
            const contentItem = card.querySelector('.ContentItem');
            if (!contentItem) return; // 跳过非内容项（如专业介绍卡片）
            if (items.length >= 15) return;

            // 提取标题和链接
            const titleEl = contentItem.querySelector('.ContentItem-title a');
            if (!titleEl) return;
            const href = titleEl.getAttribute('href') || '';
            const fullUrl = href.startsWith('/') ? 'https://www.zhihu.com' + href : href;

            // 去重：同一个 URL 只保留第一次出现
            if (seen.has(fullUrl)) return;
            seen.add(fullUrl);

            const title = titleEl.textContent.trim();
            if (!title) return;

            // 提取内容摘要
            const richText = contentItem.querySelector('.RichText');
            let contentSnippet = '';
            let authorName = '';
            if (richText) {
                const fullText = richText.textContent.trim();
                // 知乎搜索结果格式：「作者名：内容摘要...」
                const colonIdx = fullText.indexOf('：');
                if (colonIdx > 0 && colonIdx < 30) {
                    authorName = fullText.substring(0, colonIdx).trim();
                    contentSnippet = fullText.substring(colonIdx + 1).trim().substring(0, 200);
                } else {
                    contentSnippet = fullText.substring(0, 200);
                }
            }

            // 提取赞同数
            const voteBtn = contentItem.querySelector('button[aria-label*="赞同"]');
            let voteCount = '';
            if (voteBtn) {
                const vt = voteBtn.textContent.trim();
                const m = vt.match(/(\\d+)/);
                voteCount = m ? m[1] : '';
            }

            // 提取评论数
            const allBtns = contentItem.querySelectorAll('button.ContentItem-action');
            let commentCount = '';
            allBtns.forEach(btn => {
                const t = btn.textContent.trim();
                const m = t.match(/(\\d+)\\s*条评论/);
                if (m) commentCount = m[1];
            });

            // 判断类型
            let itemType = 'content';
            if (href.includes('/answer/')) {
                itemType = 'answer';
            } else if (href.includes('/question/') && !href.includes('/answer/')) {
                itemType = 'question';
            } else if (href.includes('/p/')) {
                itemType = 'article';
            }

            items.push({
                title,
                url: fullUrl,
                contentSnippet,
                authorName,
                authorUrl: '',
                voteCount,
                commentCount,
                itemType,
            });
        });
        return JSON.stringify(items);
    })()
    """
    result = page.evaluate(js_code)
    if not result:
        return []

    data = json.loads(result)
    items = []
    for d in data:
        items.append(SearchResultItem(
            title=d.get("title", ""),
            url=d.get("url", ""),
            content_snippet=d.get("contentSnippet", ""),
            author_name=d.get("authorName", ""),
            author_url=d.get("authorUrl", ""),
            vote_count=d.get("voteCount", ""),
            comment_count=d.get("commentCount", ""),
            item_type=d.get("itemType", ""),
        ))
    return items
