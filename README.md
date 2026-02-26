# TG TLDR Bot

Your group chat's snarky, helpful daily summarizer — powered by Claude.

## Features

| Command | What it does |
|---|---|
| `/tldr` | Summary of the last 24 hours |
| `/tldr 48` | Summary of any N hours (up to 168 / 7 days) |
| `/schedule 09:00` | Post a daily TLDR at 09:00 UTC automatically |
| `/schedule off` | Disable the daily post |
| `/whois @username` | Witty personality profile based on their messages |
| `/support your question` | Answers questions using the chat's history |
| _(reply to a message)_ `/support` | Same, but uses the replied message as the question |

## Setup

### 1. Get a Telegram Bot Token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy your token

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Install dependencies

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the bot

```bash
python bot.py
```

### 5. Add bot to your group

- Add the bot as a member of your Telegram group
- Make it an **admin** (so it can post daily TLDRs and read all messages)
- That's it — it starts collecting immediately

---

## Important Notes

- **The bot can only see messages sent after it joins.** It has no access to prior history.
  The longer it runs, the better the summaries and support answers get.
- Messages are stored locally in `tldr_bot.db` (SQLite). Back this up if you want persistence.
- All times for `/schedule` are in **UTC**.

## Deploy (Optional)

For 24/7 uptime, run on a cheap VPS or cloud instance:

```bash
# Simple systemd service or use screen/tmux:
screen -S tldrbot
python bot.py
# Ctrl+A, D to detach
```

Or with Docker:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

## Customizing the Tone

All AI prompts are in `ai.py`. Edit them to change:
- How formal/casual the summaries are
- Whether the `/whois` roast is gentler or spicier
- How the support bot cites chat history
