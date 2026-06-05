#!/usr/bin/env python3
"""
Upload tutorials/all_md/Обучение to Notion.
Creates a page hierarchy with navigation (link_to_page blocks).
"""
import os
import re
import time
import requests
from pathlib import Path

TOKEN = os.environ.get("NOTION_TOKEN", "")
if not TOKEN:
    raise SystemExit("NOTION_TOKEN not set")

API = "https://api.notion.com/v1"
HDRS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

BASE = Path(r"C:\Z\project_knowledge_base\tutorials\Обучение")


# ── API helpers ────────────────────────────────────────────────────────────────

def call(method, endpoint, **kw):
    url = f"{API}/{endpoint}"
    for attempt in range(4):
        r = getattr(requests, method)(url, headers=HDRS, **kw)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        if not r.ok:
            raise RuntimeError(f"{r.status_code} {r.text[:300]}")
        return r.json()
    raise RuntimeError(f"Failed after retries: {endpoint}")


# ── Block constructors ─────────────────────────────────────────────────────────

def rt(text):
    """Inline markdown → Notion rich_text (handles **bold**)."""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    parts = []
    last = 0
    for m in re.finditer(r"\*\*(.*?)\*\*", text):
        if m.start() > last:
            parts.append({"type": "text", "text": {"content": text[last:m.start()]}})
        parts.append({
            "type": "text",
            "text": {"content": m.group(1)},
            "annotations": {"bold": True},
        })
        last = m.end()
    if last < len(text):
        parts.append({"type": "text", "text": {"content": text[last:]}})
    return parts or [{"type": "text", "text": {"content": ""}}]


def heading(level, text):
    t = f"heading_{level}"
    return {"object": "block", "type": t, t: {"rich_text": rt(text.strip())}}


def para(text):
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": rt(text)}}


def bullet(text):
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": rt(text)}}


def numbered(text):
    return {"object": "block", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": rt(text)}}


def todo(text, checked=False):
    return {"object": "block", "type": "to_do",
            "to_do": {"rich_text": rt(text), "checked": checked}}


def quote_block(text):
    return {"object": "block", "type": "quote",
            "quote": {"rich_text": rt(text)}}


def divider():
    return {"object": "block", "type": "divider", "divider": {}}


def callout(text, emoji="📎"):
    return {
        "object": "block", "type": "callout",
        "callout": {
            "rich_text": rt(text),
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


def link_to_page(page_id):
    return {
        "object": "block", "type": "link_to_page",
        "link_to_page": {"type": "page_id", "page_id": page_id},
    }


# ── Markdown → blocks ──────────────────────────────────────────────────────────

def md_to_blocks(text):
    blocks = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        if not line.strip():
            i += 1
            continue

        # Table → bullet rows (avoid table API complexity)
        if line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = []
            for tl in table_lines:
                if re.match(r"^\|[\s\-:|]+\|$", tl.strip()):
                    continue  # separator row
                cells = [c.strip() for c in tl.strip().strip("|").split("|")]
                rows.append(cells)
            if len(rows) >= 2:
                header = rows[0]
                for row in rows[1:]:
                    parts = []
                    for j, cell in enumerate(row):
                        label = header[j] if j < len(header) else ""
                        parts.append(f"**{label}:** {cell}" if label else cell)
                    blocks.append(bullet(" | ".join(parts)))
            continue

        # Headings
        if line.startswith("# "):
            blocks.append(heading(1, line[2:]))
        elif line.startswith("## "):
            blocks.append(heading(2, line[3:]))
        elif line.startswith("### "):
            blocks.append(heading(3, line[4:]))

        # Blockquote — collect consecutive > lines
        elif line.startswith(">"):
            q_parts = []
            while i < len(lines) and lines[i].startswith(">"):
                q_parts.append(lines[i].lstrip(">").strip())
                i += 1
            blocks.append(quote_block(" ".join(q_parts)))
            continue

        # Checkboxes
        elif line.startswith("- [ ] "):
            blocks.append(todo(line[6:], False))
        elif re.match(r"- \[x\] ", line, re.I):
            blocks.append(todo(line[6:], True))

        # Bullets (also indented sub-bullets)
        elif re.match(r"^(\s{1,4})?[-*] ", line):
            text_b = re.sub(r"^(\s{1,4})?[-*] ", "", line)
            blocks.append(bullet(text_b))

        # Numbered list
        elif re.match(r"^\d+\.\s", line):
            blocks.append(numbered(re.sub(r"^\d+\.\s", "", line)))

        # Horizontal rule
        elif line.strip() in ("---", "***", "___"):
            blocks.append(divider())

        # Plain paragraph
        else:
            blocks.append(para(line))

        i += 1

    return blocks


# ── Notion page creation ───────────────────────────────────────────────────────

def create_page(parent_id, title, blocks=None, emoji=None, workspace=False):
    parent = {"type": "workspace", "workspace": True} if workspace \
        else {"type": "page_id", "page_id": parent_id}
    data = {
        "parent": parent,
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
        "children": (blocks or [])[:100],
    }
    if emoji:
        data["icon"] = {"type": "emoji", "emoji": emoji}

    result = call("post", "pages", json=data)
    page_id = result["id"]
    print(f"  ✓ '{title}' → {page_id}")

    # Append remaining blocks in batches of 100
    remaining = (blocks or [])[100:]
    while remaining:
        call("patch", f"blocks/{page_id}/children",
             json={"children": remaining[:100]})
        remaining = remaining[100:]
        time.sleep(0.3)

    return page_id


def append_blocks(page_id, blocks):
    while blocks:
        call("patch", f"blocks/{page_id}/children",
             json={"children": blocks[:100]})
        blocks = blocks[100:]
        time.sleep(0.3)


def read_md(path):
    return path.read_text(encoding="utf-8")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n── Создаём страницы в Notion ──")

    # Root page under the accessible parent page
    PARENT_PAGE_ID = "35b57cb0-1e34-80d4-82e8-d17fbd0bc569"  # Getting Started
    root_id = create_page(
        PARENT_PAGE_ID,
        "📚 Обучение по звонкам",
        emoji="📚",
    )

    # Intro
    intro_id = create_page(
        root_id, "Введение",
        md_to_blocks(read_md(BASE / "call-training-overview.md")),
        emoji="📋",
    )

    # ── Module 1 ──
    print("\nМодуль 1:")
    m1_dir = BASE / "Модуль 1. Структура звонка на диагностику"
    m1_id = create_page(root_id, "Модуль 1. Структура звонка на диагностику", emoji="📞")

    m1_script_id = create_page(
        m1_id, "Скрипт звонка: 10 шагов",
        md_to_blocks(read_md(m1_dir / "module-1-call-structure-script.md")),
        emoji="📝",
    )
    m1_tasks_id = create_page(
        m1_id, "Мини-задания",
        md_to_blocks(read_md(m1_dir / "module-1-mini-tasks.md")),
        emoji="✏️",
    )
    append_blocks(m1_id, [link_to_page(m1_script_id), link_to_page(m1_tasks_id)])

    # ── Module 2 ──
    print("\nМодуль 2:")
    m2_dir = BASE / "Модуль 2. Как не быть роботом по скрипту"
    m2_id = create_page(root_id, "Модуль 2. Как не быть роботом по скрипту", emoji="🎭")

    m2_guide_id = create_page(
        m2_id, "Руководство",
        md_to_blocks(read_md(m2_dir / "module-2-anti-robot-guide.md")),
        emoji="📖",
    )
    m2_ex_id = create_page(
        m2_id, "Упражнения",
        md_to_blocks(read_md(m2_dir / "module-2-exercises.md")),
        emoji="🏋️",
    )
    m2_cl_id = create_page(
        m2_id, "Чек-лист анти-робот",
        md_to_blocks(read_md(m2_dir / "module-2-daily-checklist.md")),
        emoji="✅",
    )
    append_blocks(m2_id, [
        link_to_page(m2_guide_id),
        link_to_page(m2_ex_id),
        link_to_page(m2_cl_id),
    ])

    # ── Module 3 ──
    print("\nМодуль 3:")
    m3_dir = BASE / "Модуль 3. Фиксация времени, переносы и ценность слота"
    m3_id = create_page(root_id, "Модуль 3. Фиксация времени, переносы и ценность слота", emoji="⏰")

    m3_guide_id = create_page(
        m3_id, "Руководство",
        md_to_blocks(read_md(m3_dir / "module-3-time-slot-guide.md")),
        emoji="📖",
    )

    m3_prac_dir = m3_dir / "Практические упражнения"
    m3_prac_id = create_page(m3_id, "Практические упражнения", emoji="🏋️")

    m3_ex1_id = create_page(
        m3_prac_id, "Упражнения (часть 1)",
        md_to_blocks(read_md(m3_prac_dir / "module-3-exercises-1.md")),
        emoji="1️⃣",
    )
    m3_ex2_id = create_page(
        m3_prac_id, "Упражнения (часть 2)",
        md_to_blocks(read_md(m3_prac_dir / "module-3-exercises-2.md")),
        emoji="2️⃣",
    )
    append_blocks(m3_prac_id, [link_to_page(m3_ex1_id), link_to_page(m3_ex2_id)])
    append_blocks(m3_id, [link_to_page(m3_guide_id), link_to_page(m3_prac_id)])

    # ── Navigation on root page ──
    print("\nДобавляем навигацию на корневую страницу...")
    append_blocks(root_id, [
        callout("Навигация по курсу", "🗺️"),
        link_to_page(intro_id),
        link_to_page(m1_id),
        link_to_page(m2_id),
        link_to_page(m3_id),
    ])

    print(f"\n✅ Готово!")
    print(f"Корневая страница: https://www.notion.so/{root_id.replace('-', '')}")


if __name__ == "__main__":
    main()
