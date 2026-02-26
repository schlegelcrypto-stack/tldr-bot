"""
TG TLDR Bot - Your chat's snarky, helpful summarizer
"""

import asyncio
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from db import Database
from ai import generate_tldr, generate_whois, generate_support

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()
scheduler = AsyncIOScheduler()


# ──────────────────────────────────────────────
# Message Listener — the bot's eyes and ears
# ──────────────────────────────────────────────

async def listen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Silently collect every message into the database."""
    msg = update.message
    if not msg or not msg.text:
        return

    db.store_message(
        chat_id=msg.chat_id,
        user_id=msg.from_user.id,
        username=msg.from_user.username or msg.from_user.first_name,
        text=msg.text,
        timestamp=msg.date,
        message_id=msg.message_id,
    )


# ──────────────────────────────────────────────
# /tldr  — on-demand summary
# ──────────────────────────────────────────────

async def cmd_tldr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a TLDR summary of the last 24h (or N hours if specified)."""
    chat_id = update.effective_chat.id

    # Optional: /tldr 48  → last 48 hours
    hours = 24
    if context.args:
        try:
            hours = int(context.args[0])
            hours = min(max(hours, 1), 168)  # clamp 1h–7d
        except ValueError:
            pass

    await update.message.reply_text(
        f"⏳ Brewing your {hours}h summary... one sec."
    )

    messages = db.get_messages(chat_id, hours=hours)
    if not messages:
        await update.message.reply_text(
            "📭 Nothing to summarize yet — I haven't seen any messages in that window. "
            "Give me some time to lurk first."
        )
        return

    summary = await generate_tldr(messages, hours)
    await update.message.reply_text(summary, parse_mode="Markdown")


# ──────────────────────────────────────────────
# /schedule — set up daily auto-TLDR
# ──────────────────────────────────────────────

async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /schedule HH:MM  or  /schedule off"""
    chat_id = update.effective_chat.id

    if not context.args:
        current = db.get_schedule(chat_id)
        if current:
            await update.message.reply_text(
                f"⏰ Daily TLDR is set for *{current}* UTC.\n"
                f"Use `/schedule HH:MM` to change it or `/schedule off` to disable.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "No daily TLDR scheduled. Use `/schedule HH:MM` (UTC) to set one.",
                parse_mode="Markdown"
            )
        return

    arg = context.args[0].lower()

    if arg == "off":
        db.remove_schedule(chat_id)
        _remove_scheduled_job(chat_id)
        await update.message.reply_text("🔕 Daily TLDR disabled. I'll go back to silently judging everyone.")
        return

    # Parse HH:MM
    try:
        t = datetime.strptime(arg, "%H:%M")
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Use HH:MM (e.g. `/schedule 09:00`)", parse_mode="Markdown")
        return

    db.save_schedule(chat_id, arg)
    _upsert_scheduled_job(chat_id, t.hour, t.minute, context.application)
    await update.message.reply_text(
        f"✅ Done! I'll drop a daily TLDR at *{arg} UTC* every day.\n"
        f"Use `/schedule off` to cancel.",
        parse_mode="Markdown"
    )


def _upsert_scheduled_job(chat_id: int, hour: int, minute: int, app):
    job_id = f"tldr_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    scheduler.add_job(
        _send_scheduled_tldr,
        trigger="cron",
        hour=hour,
        minute=minute,
        id=job_id,
        kwargs={"chat_id": chat_id, "app": app},
    )


def _remove_scheduled_job(chat_id: int):
    job_id = f"tldr_{chat_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


async def _send_scheduled_tldr(chat_id: int, app):
    """Called by the scheduler — posts the daily summary."""
    messages = db.get_messages(chat_id, hours=24)
    if not messages:
        return  # Quiet day, nothing to post
    summary = await generate_tldr(messages, hours=24, scheduled=True)
    await app.bot.send_message(chat_id=chat_id, text=summary, parse_mode="Markdown")


# ──────────────────────────────────────────────
# /whois @username — personality roast
# ──────────────────────────────────────────────

async def cmd_whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usage: /whois @username"""
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("Usage: `/whois @username`", parse_mode="Markdown")
        return

    raw = context.args[0].lstrip("@")
    messages = db.get_user_messages(chat_id, username=raw, limit=100)

    if not messages:
        await update.message.reply_text(
            f"🤷 I don't have enough messages from *{raw}* to build a profile yet. "
            "They're either a lurker, or a ghost.",
            parse_mode="Markdown"
        )
        return

    await update.message.reply_text(f"🔍 Analyzing @{raw}... this could get interesting.")
    profile = await generate_whois(raw, messages)
    await update.message.reply_text(profile, parse_mode="Markdown")


# ──────────────────────────────────────────────
# /support — answer a question from chat history
# ──────────────────────────────────────────────

async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Reply to a message with /support, or:
    /support How do I reset my password?
    """
    chat_id = update.effective_chat.id
    question = None

    # Check if it's a reply to a message
    if update.message.reply_to_message and update.message.reply_to_message.text:
        question = update.message.reply_to_message.text
    elif context.args:
        question = " ".join(context.args)

    if not question:
        await update.message.reply_text(
            "Usage: Reply to a message with `/support`, or `/support your question here`",
            parse_mode="Markdown"
        )
        return

    messages = db.get_messages(chat_id, hours=168)  # Last 7 days of context
    if not messages:
        await update.message.reply_text(
            "📭 I don't have enough chat history to answer that yet. Keep talking — I'm learning!"
        )
        return

    await update.message.reply_text("🤔 Searching the chat archives...")
    answer = await generate_support(question, messages)
    await update.message.reply_text(answer, parse_mode="Markdown")


# ──────────────────────────────────────────────
# /help
# ──────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*📋 TLDR Bot — Command Reference*\n\n"
        "`/tldr` — Summary of the last 24 hours\n"
        "`/tldr 48` — Summary of the last N hours (up to 168)\n\n"
        "`/schedule 09:00` — Post daily TLDR at 09:00 UTC\n"
        "`/schedule off` — Disable daily TLDR\n\n"
        "`/whois @username` — Personality profile based on their messages\n\n"
        "`/support question` — Answer a question using chat history\n"
        "_(or reply to a message with /support)_\n\n"
        "I silently collect messages once added to a group. "
        "The more I see, the smarter I get. 🧠",
        parse_mode="Markdown"
    )


# ──────────────────────────────────────────────
# Startup — restore scheduled jobs from DB
# ──────────────────────────────────────────────

async def on_startup(app):
    schedules = db.get_all_schedules()
    for chat_id, time_str in schedules:
        try:
            t = datetime.strptime(time_str, "%H:%M")
            _upsert_scheduled_job(chat_id, t.hour, t.minute, app)
            logger.info(f"Restored schedule for chat {chat_id} at {time_str}")
        except Exception as e:
            logger.error(f"Failed to restore schedule for {chat_id}: {e}")
    scheduler.start()
    logger.info("Scheduler started.")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

async def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    app = Application.builder().token(token).post_init(on_startup).build()

    app.add_handler(CommandHandler("tldr", cmd_tldr))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("whois", cmd_whois))
    app.add_handler(CommandHandler("support", cmd_support))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))

    # Listen to ALL non-command messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, listen))

    logger.info("Bot is running...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
