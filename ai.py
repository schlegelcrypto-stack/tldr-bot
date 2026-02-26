"""
AI layer — all Claude API calls live here.
Swap the model or prompts without touching bot logic.
"""

import os
import anthropic
from typing import List

client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-opus-4-6"


def _format_messages(messages: List[dict]) -> str:
    """Turn raw DB rows into a readable transcript for the AI."""
    lines = []
    for m in messages:
        ts = m["timestamp"][:16].replace("T", " ")  # "2024-01-15 14:32"
        lines.append(f"[{ts}] {m['username']}: {m['text']}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# TLDR
# ──────────────────────────────────────────────────────────────────────────────

async def generate_tldr(
    messages: List[dict], hours: int = 24, scheduled: bool = False
) -> str:
    transcript = _format_messages(messages)
    header = "📰 *Daily Digest*" if scheduled else f"📋 *TLDR — Last {hours}h*"

    prompt = f"""You are the witty, sharp, and slightly sarcastic summarizer for a group chat.
Your job is to write a TLDR summary that reads like a smart friend recapping what happened — 
NOT a boring bullet list.

Write in flowing prose. Be warm, informative, and occasionally funny. 
Call out key discussions, decisions, announcements, and any drama or spicy takes.
If someone solved a problem, give them a shoutout.
Group related topics naturally.
Keep it to 3-6 paragraphs. Use emojis sparingly to add flavor.
Format for Telegram Markdown (use *bold* and _italic_ where it helps).

Start with: {header}

Chat transcript (last {hours} hours):
---
{transcript}
---

Write the summary now:"""

    resp = await client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ──────────────────────────────────────────────────────────────────────────────
# /whois
# ──────────────────────────────────────────────────────────────────────────────

async def generate_whois(username: str, messages: List[dict]) -> str:
    transcript = _format_messages(messages)

    prompt = f"""You are a witty chat analyst who writes hilarious but affectionate personality profiles 
based on someone's messages. Think of it like a roast that's actually charming.

Based ONLY on what @{username} has said in this chat, write a short personality profile.
Include:
- Their apparent vibe/personality (2-3 sentences)
- What they clearly care about based on their messages  
- Their communication style (are they brief? verbose? full of questions? memes?)
- A fun "verdict" line at the end — like a one-liner summary of who they are

Keep it under 200 words. Make it funny but kind — roast, not destroy.
Format for Telegram Markdown.

Their messages:
---
{transcript}
---

Write the profile now:"""

    resp = await client.messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


# ──────────────────────────────────────────────────────────────────────────────
# /support
# ──────────────────────────────────────────────────────────────────────────────

async def generate_support(question: str, messages: List[dict]) -> str:
    transcript = _format_messages(messages)

    prompt = f"""You are a helpful support assistant for a group chat community.
You have access to the chat's recent conversation history. 
Your job is to answer a question using relevant info from the chat.

Rules:
- If the answer (or partial answer) exists in the chat, cite it naturally ("According to what Maya shared earlier...", "Based on the discussion on Tuesday...")
- If no relevant info exists, say so honestly and give your best general answer
- Be concise, clear, and friendly
- Format for Telegram Markdown
- Don't quote messages verbatim — paraphrase naturally

Question: {question}

Recent chat history:
---
{transcript}
---

Answer the question now:"""

    resp = await client.messages.create(
        model=MODEL,
        max_tokens=768,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
