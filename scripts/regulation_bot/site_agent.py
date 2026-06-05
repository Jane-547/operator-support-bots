"""Локальный индекс сайта для поиска контекста по регламенту."""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SITE_DIR = Path(__file__).parent.parent.parent / "card" / "site"
BASE_URL = "https://call-training.vercel.app"

# Страницы-оглавления — полезны как запасной вариант, но приоритет ниже
OVERVIEW_PAGES = {"index.html", "training.html", "regulation.html",
                  "getcourse.html", "script.html"}


def _extract_text(html: str) -> str:
    html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<header[^>]*>.*?</header>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<nav[^>]*>.*?</nav>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<footer[^>]*>.*?</footer>', ' ', html, flags=re.DOTALL)
    html = re.sub(r'<[^>]+>', ' ', html)
    html = (html
            .replace('&nbsp;', ' ').replace('&lt;', '<')
            .replace('&gt;', '>').replace('&amp;', '&')
            .replace('&quot;', '"').replace('&#39;', "'"))
    return re.sub(r'\s+', ' ', html).strip()


def _get_meta(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ''


def _build_index(site_dir: Path) -> list[dict]:
    index = []
    for path in sorted(site_dir.glob('*.html')):
        try:
            raw = path.read_text(encoding='utf-8')
            title = _get_meta(raw, r'<title>(.*?) — Матриус</title>')
            if not title:
                title = _get_meta(raw, r'<title>(.*?)</title>') or path.stem
            section = _get_meta(raw, r'class="module-indicator"[^>]*>(.*?)</div>')
            text = _extract_text(raw)
            words = set(re.sub(r'[^\w\s]', '', text.lower()).split())
            index.append({
                'filename': path.name,
                'url': f"{BASE_URL}/{path.name}",
                'title': title,
                'section': section,
                'text': text,
                'words': words,
                'is_overview': path.name in OVERVIEW_PAGES,
            })
            logger.debug("Indexed %s (%d chars)", path.name, len(text))
        except Exception:
            logger.warning("Не удалось индексировать %s", path.name, exc_info=True)
    logger.info("Индекс построен: %d страниц", len(index))
    return index


_index: list[dict] = []


def load_index() -> None:
    global _index
    _index = _build_index(SITE_DIR)


# Явные алиасы: ключевые фразы → приоритетная страница
# Используется когда keyword-поиск даёт неверный результат
_ALIASES: list[tuple[list[str], str]] = [
    (
        ['не отвечает', 'не берёт', 'не берет', 'не дозвонились', 'недозвон',
         'ндз', 'не выходит на связь', 'нет ответа', 'не пришёл', 'не пришел',
         'пропустил встречу', 'не дошёл до звонка'],
        'regulation-ndz.html',
    ),
    (
        ['дежурств', 'дежурный', 'дежурного', 'дежурит', 'передача смены',
         'обязанности дежурного'],
        'regulation-duty.html',
    ),
]


def _alias_match(query_lower: str) -> str | None:
    """Возвращает filename если запрос явно попадает под алиас."""
    for phrases, filename in _ALIASES:
        if any(p in query_lower for p in phrases):
            return filename
    return None


def get_context_for_query(query: str) -> tuple[str, list[dict]]:
    """
    Возвращает (context_text, top_pages).
    top_pages — список dict с 'title' и 'url'.
    """
    if not _index:
        load_index()

    query_lower = query.lower()

    # Проверяем явные алиасы — они точнее keyword-поиска
    alias_file = _alias_match(query_lower)
    if alias_file:
        match = next((p for p in _index if p['filename'] == alias_file), None)
        if match:
            return match['text'][:3500], [match]

    query_words = set(re.sub(r'[^\w\s]', '', query.lower()).split())
    # Убираем стоп-слова
    stop = {'как', 'что', 'где', 'когда', 'зачем', 'почему', 'можно', 'нужно',
            'надо', 'это', 'для', 'при', 'если', 'или', 'и', 'в', 'на', 'с',
            'по', 'из', 'у', 'о', 'не', 'то', 'а', 'но', 'да', 'же', 'ли'}
    query_words -= stop

    scored = []
    for page in _index:
        body_score = len(query_words & page['words'])
        title_words = set(re.sub(r'[^\w\s]', '', page['title'].lower()).split())
        title_score = len(query_words & title_words) * 3
        score = body_score + title_score
        if page['is_overview']:
            score *= 0.5
        if score > 0:
            scored.append((score, page))

    scored.sort(key=lambda x: -x[0])
    top = [p for _, p in scored[:2]]

    if not top:
        # Фолбэк: берём первые содержательные страницы
        top = [p for p in _index if not p['is_overview']][:2]

    parts = []
    for page in top:
        header = page['title']
        if page['section']:
            header += f" ({page['section']})"
        parts.append(f"## {header}\n{page['text'][:3500]}")

    return '\n\n'.join(parts), top
