---
name: project-setup
description: Разворачивает проект «Система адаптации и поддержки операторов» с нуля. Запускай когда нужно настроить проект на новой машине.
version: 2.0.0
---

# project-setup

Справочник по работе с репозиторием operator-support-bots. Используй как карту проекта: структура, запуск, изменения, диагностика, публикация.

---

## Карта проекта

```
operator-support-bots/          ← github.com/Jane-547/operator-support-bots
├── bot_claude.py               ← @ResponseGeneratorBot (бот ответов клиентам)
├── requirements.txt            ← зависимости для bot_claude.py
├── fly.toml                    ← конфиг деплоя Fly.io
├── .env                        ← токены (не коммитить!)
├── .env.example                ← шаблон переменных окружения
├── images/                     ← скриншоты для README
│   ├── site.png
│   ├── regulation-bot.png
│   └── response-generator-bot.png
├── scripts/
│   ├── regulation_bot/         ← @Reglament547Bot (бот регламента)
│   │   ├── bot.py              ← точка входа
│   │   ├── site_agent.py       ← поиск по HTML-файлам card/site/
│   │   ├── notion_agent.py     ← резервный источник: Notion API
│   │   └── requirements.txt
│   ├── notion_upload.py        ← загрузка tutorials/ в Notion
│   └── notion_cleanup.py       ← очистка дублей в Notion
├── docs/                       ← PDF и MD-гайды для операторов
├── tutorials/                  ← учебные материалы (синхронизируются с Notion)
├── tmp/
│   ├── operator-kb.md          ← база знаний для @ResponseGeneratorBot
│   └── notion-snapshot.md      ← снапшот Notion (генерируется /kb-sync)
├── reports/                    ← логи запросов (не коммитятся)
└── card/site/                  ← HTML-сайт — ОТДЕЛЬНЫЙ репозиторий!
                                   github.com/Jane-547/call-training
                                   деплой: call-training.vercel.app
```

**Два репозитория:**
- `operator-support-bots` — боты + база знаний (этот репо)
- `call-training` — сайт, папка `card/site/`, деплоится на Vercel автоматически

---

## Как устроены боты

**@ResponseGeneratorBot** (`bot_claude.py`):
- Ждёт сообщение с `!` в Telegram
- Запускает `claude --dangerously-skip-permissions -p` как subprocess
- Claude читает скилл `.claude/skills/response-generator/` и `tmp/operator-kb.md`
- Возвращает оператору готовый ответ клиенту
- Логи: `reports/log.md`

**@Reglament547Bot** (`scripts/regulation_bot/bot.py`):
- Ждёт сообщение с `!` в Telegram
- Ищет ответ по HTML-файлам `card/site/` через `site_agent.py`
- Если нужно — обращается к Notion через `notion_agent.py`
- Отвечает строго по базе знаний, без домыслов
- Логи: `reports/regulation-bot-log.md`

---

## Первичная установка на новой машине

### 1. Требования

```bash
python --version      # нужен 3.11+
claude --version      # нужен Claude Code CLI
```

Если нет Claude Code: `npm install -g @anthropic-ai/claude-code`, затем `claude login`.

### 2. Клонировать оба репозитория

```bash
git clone git@github.com:Jane-547/operator-support-bots.git
cd operator-support-bots
git clone git@github.com:Jane-547/call-training.git card/site
```

### 3. Создать `.env`

Скопировать `.env.example` и заполнить токены:

```env
TELEGRAM_TOKEN=         # токен @ResponseGeneratorBot
REGULATION_BOT_TOKEN=   # токен @Reglament547Bot
NOTION_TOKEN=           # только если нужен /kb-sync
```

### 4. Установить зависимости

```bash
pip install -r requirements.txt
pip install -r scripts/regulation_bot/requirements.txt
```

### 5. Убедиться, что Claude Code авторизован

```bash
claude --version
# если нет — claude login
```

---

## Запуск ботов

Каждый бот — отдельный терминал.

**Терминал 1 — @ResponseGeneratorBot:**
```bash
python bot_claude.py
```
Успешный старт: `INFO - Бот запущен с Claude Code!`

**Терминал 2 — @Reglament547Bot:**
```bash
python scripts/regulation_bot/bot.py
```
Успешный старт: `INFO - Бот регламента запущен (источник: локальный сайт)`

**Проверка в Telegram:**
```
! Дорого, у других дешевле          → @ResponseGeneratorBot
! что делать если клиент не отвечает → @Reglament547Bot
```

---

## Внесение изменений

### Логика бота ответов
Редактировать: `.claude/skills/response-generator/script.md`
Это системный промпт — меняй стиль, тон, правила ответа.

### Логика бота регламента
Редактировать: `scripts/regulation_bot/bot.py` — триггеры, форматирование ответа.
Источник знаний: `card/site/` HTML-файлы или Notion.

### База знаний (регламент, скрипты)
Обновить в Notion, затем запустить синхронизацию:
```
/kb-sync
```
Пайплайн: Notion → `tmp/notion-snapshot.md` → `card/site/` + `tmp/operator-kb.md`

### Обучающие материалы (tutorials/)
Редактировать файлы в `tutorials/` напрямую или загрузить в Notion:
```bash
python scripts/notion_upload.py
```

### Документы (docs/)
Добавлять/редактировать файлы в `docs/` напрямую. PDF, MD, DOCX.

---

## Обновление README

README.md находится в корне проекта.

**Структура README:**
1. Заголовок + описание
2. Таблица компонентов (сайт, 2 бота)
3. Скриншоты из `images/`
4. Инструкция по использованию ботов
5. Установка
6. Обновление базы знаний
7. Технологии

**Добавить скриншот:**
1. Положить файл в `images/`
2. Добавить в README: `![Описание](images/filename.png)`
3. Закоммитить оба файла

**Обновить ссылки на ботов:** найти раздел "Компоненты" и поменять `@username` или URL.

---

## Диагностика ошибок

| Симптом | Причина | Решение |
|---|---|---|
| `❌ Токен не найден` | Нет `.env` или опечатка | Проверь `.env` в корне |
| `❌ Claude Code не найден` | `claude` не в PATH | Переустанови или проверь PATH |
| `KeyError: 'REGULATION_BOT_TOKEN'` | Нет переменной в `.env` | Добавь токен в `.env` |
| Бот молчит на `!` | Процесс не запущен | Запусти соответствующий `bot.py` |
| @ResponseGeneratorBot таймаут | Claude Code медленно отвечает | Норма до 120 сек на первый запрос |
| @Reglament547Bot не находит ответ | `card/site/` отсутствует или пустая | Клонируй `call-training` в `card/site` |
| Регламент устарел | KB не синхронизирован | Запусти `/kb-sync` |

**Проверить, что запущено:**
```bash
# Windows
tasklist | findstr python

# Логи последних запросов
cat reports/log.md
cat reports/regulation-bot-log.md
```

---

## Публикация изменений

### Изменения в ботах и базе знаний → operator-support-bots

Из корня проекта:
```bash
git add <файл>
git commit -m "описание изменений"
git push
```

**Что можно коммитить:**
- `bot_claude.py`, `scripts/`
- `docs/`, `tutorials/`
- `README.md`, `images/`
- `requirements.txt`, `fly.toml`, `.env.example`

**Что НЕ коммитить** (уже в `.gitignore`):
- `.env` — токены
- `card/` — сайт в отдельном репо
- `tmp/` — авто-генерируемые снапшоты
- `reports/` — рабочие логи
- `.claude/` — внутренний конфиг агента

### Изменения на сайте → call-training (Vercel)

Из папки `card/site/`:
```bash
git add .
git commit -m "описание изменений"
git push
```
Vercel автоматически задеплоит после пуша. Сайт обновится через ~1 минуту.

### Чек-лист перед публикацией

- [ ] `.env` не попал в `git status`
- [ ] `tmp/` и `reports/` не попали в `git status`
- [ ] Боты запускаются локально
- [ ] README актуален (версии, ссылки, скриншоты)
- [ ] `requirements.txt` обновлён если добавлены зависимости

---

После завершения установки выведи итог: что установлено, что запущено, что проверено.
