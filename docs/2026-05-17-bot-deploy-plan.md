# План: переезд бота на бесплатный хостинг без карты

**Стек:** Gemini Flash API (бесплатная модель) + Koyeb (бесплатный хостинг)  
**Цель:** бот работает 24/7, не зависит от твоего ПК, не требует подписки и карты

---

## Что меняется в архитектуре

| Сейчас | После |
|---|---|
| `claude` CLI как subprocess | Прямой вызов Gemini API из Python |
| Твоя подписка Claude | Gemini Flash (бесплатно, без карты) |
| Запущен локально на ПК | Koyeb — облачный сервер |
| Лог пишется в `reports/log.md` | Лог выводится в консоль (виден в Koyeb Dashboard) |

---

## Шаг 1. Получить бесплатный API-ключ Gemini

1. Открыть **aistudio.google.com**
2. Войти через Google-аккаунт
3. Нажать **Get API key → Create API key**
4. Скопировать ключ — он выглядит как `AIzaSy...`

> Карта не нужна. Лимиты бесплатного тарифа: 15 запросов/мин, 1 млн токенов/день — для бота более чем достаточно.

---

## Шаг 2. Переработать `bot_claude.py`

Заменить вызов `claude` CLI на вызов Gemini API. Логику скилла (`skill.md` + `templates.md`) встроить как system prompt прямо в код. Логирование перенести в `print()` — Koyeb пишет весь stdout в Dashboard.

**Что конкретно менять в коде:**
- Убрать `asyncio.create_subprocess_exec("claude", ...)` — весь блок `generate_response`
- Добавить `import google.generativeai as genai`
- Написать новую функцию `generate_response` с вызовом `genai.GenerativeModel(...).generate_content(...)`
- System prompt = содержимое `skill.md` + `templates.md`
- Вместо записи в файл — `print(f"[LOG] {тип} | {сообщение} | {ответ}")`

---

## Шаг 3. Создать `requirements.txt`

Добавить файл в корень проекта:

```
python-telegram-bot==21.10.0
google-generativeai
python-dotenv
```

---

## Шаг 4. Подготовить `.gitignore`

Убедиться, что `.env` не попадёт в репозиторий. В `.gitignore` должна быть строка:

```
.env
```

---

## Шаг 5. Создать приватный репозиторий на GitHub

1. Открыть **github.com → New repository**
2. Visibility: **Private**
3. Добавить файлы: `bot_claude.py`, `requirements.txt`, `.gitignore`, папку `.claude/skills/response-generator/`
4. Файл `.env` **не добавлять**

---

## Шаг 6. Зарегистрироваться на Koyeb

1. Открыть **koyeb.com**
2. Sign up через Google или GitHub — карта не нужна
3. Подтвердить email

> Koyeb free tier: 1 сервис, 512 MB RAM, 0.1 vCPU. Для Python Telegram-бота — достаточно.

---

## Шаг 7. Создать сервис на Koyeb

1. Dashboard → **Create Service**
2. Источник: **GitHub** → выбрать репозиторий
3. Runtime: **Python**
4. Run command: `python bot_claude.py`
5. Раздел **Environment Variables** — добавить:
   - `TELEGRAM_TOKEN` = значение из `.env`
   - `GEMINI_API_KEY` = ключ из шага 1
6. Нажать **Deploy**

---

## Шаг 8. Проверить работу

1. Дождаться статуса **Running** в Koyeb Dashboard
2. Открыть бота в Telegram, написать тестовое сообщение
3. В разделе **Logs** на Koyeb проверить, что ответы генерируются и логи пишутся

---

## Важные нюансы

**Логи:** файл `reports/log.md` на сервере работать не будет — Koyeb использует временное хранилище, которое сбрасывается при каждом перезапуске. Все логи — через `print()` в Dashboard. Если нужно постоянное хранение — можно добавить запись в Notion через API.

**Путь в skill.md:** строка 67 содержит абсолютный Windows-путь `C:\Z\project_knowledge_base\reports\log.md` — после переноса логики в Python этот путь становится неактуальным.

**Polling vs Webhook:** Koyeb поддерживает polling (текущий режим бота) — ничего переделывать не нужно.

**Обновление кода:** при пуше нового коммита в GitHub Koyeb автоматически передеплоивает бота.
