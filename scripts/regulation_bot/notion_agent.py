"""Модуль получения контента регламента из Notion."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

REGULATION_ROOT_ID = "36b57cb0-1e34-8015-8bfa-f12f78d0873c"
NOTION_VERSION = "2022-06-28"
CACHE_TTL = 3600  # секунды

_cache: dict[str, tuple[str, float]] = {}  # page_id -> (content, timestamp)
_full_cache: tuple[str, float] = ("", 0.0)


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _extract_text(block: dict) -> str:
    btype = block.get("type", "")
    content = block.get(btype, {})

    if btype in ("paragraph", "bulleted_list_item", "numbered_list_item",
                  "quote", "callout", "toggle"):
        parts = content.get("rich_text", [])
        return "".join(p.get("plain_text", "") for p in parts)

    if btype.startswith("heading_"):
        parts = content.get("rich_text", [])
        text = "".join(p.get("plain_text", "") for p in parts)
        level = "#" * int(btype[-1])
        return f"{level} {text}"

    if btype == "child_page":
        return f"\n## {content.get('title', '')}"

    return ""


async def _fetch_children(
    client: httpx.AsyncClient, block_id: str, token: str, depth: int = 0
) -> str:
    if depth > 2:
        return ""

    try:
        resp = await client.get(
            f"https://api.notion.com/v1/blocks/{block_id}/children",
            headers=_headers(token),
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("Не удалось получить блоки %s: %s", block_id, e)
        return ""

    blocks = resp.json().get("results", [])
    lines = []

    for block in blocks:
        text = _extract_text(block).strip()
        if text:
            lines.append(text)

        if block.get("has_children"):
            child_text = await _fetch_children(client, block["id"], token, depth + 1)
            if child_text:
                lines.append(child_text)

    return "\n".join(lines)


async def search_pages(query: str, token: str) -> list[dict]:
    """Поиск страниц в Notion по запросу."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                "https://api.notion.com/v1/search",
                headers=_headers(token),
                json={
                    "query": query,
                    "filter": {"property": "object", "value": "page"},
                    "page_size": 5,
                },
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
        except Exception as e:
            logger.warning("Ошибка поиска в Notion: %s", e)
            return []


async def load_regulation_content(token: str) -> str:
    """Загружает полное дерево регламента из Notion с кэшированием."""
    global _full_cache

    content, ts = _full_cache
    if content and (time.time() - ts) < CACHE_TTL:
        return content

    logger.info("Загружаю регламент из Notion...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            content = await _fetch_children(client, REGULATION_ROOT_ID, token)
        _full_cache = (content, time.time())
        logger.info("Регламент загружен (%d символов)", len(content))
    except Exception:
        logger.exception("Ошибка загрузки регламента")
        if _full_cache[0]:
            logger.warning("Использую устаревший кэш")
            return _full_cache[0]
        content = "База знаний временно недоступна."

    return content


async def get_context_for_query(query: str, token: str) -> str:
    """
    Возвращает релевантный контент из Notion для ответа на вопрос.
    Сначала пробует поиск, при неудаче — полный регламент.
    """
    pages = await search_pages(query, token)

    if pages:
        async with httpx.AsyncClient(timeout=30.0) as client:
            texts = []
            seen = set()

            for page in pages[:3]:
                page_id = page["id"]
                if page_id in seen:
                    continue
                seen.add(page_id)

                props = page.get("properties", {})
                title_parts = props.get("title", {}).get("title", [])
                title = "".join(t.get("plain_text", "") for t in title_parts)

                text = await _fetch_children(client, page_id, token)
                if text.strip():
                    texts.append(f"## {title}\n{text}" if title else text)

            if texts:
                return "\n\n".join(texts)

    # Фолбэк: полный регламент
    return await load_regulation_content(token)
