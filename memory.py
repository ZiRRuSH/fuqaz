import os
import sqlite3
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

DB_PATH = Path("fuqaz_memory.db")
LOCAL_TIMEZONE = os.getenv("LOCAL_TIMEZONE", "America/New_York")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_memory():
    with get_connection() as conn:
        # Per-message chat log
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Per-channel long-term summary
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                channel_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Per-user long-term facts/preferences
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                fact TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


def save_message(channel_id: str, user_id: str, role: str, content: str):
    content = (content or "").strip()
    if not content:
        return

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (channel_id, user_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (channel_id, user_id, role, content)
        )
        conn.commit()


def get_recent_messages(channel_id: str, limit: int = 10) -> list[sqlite3.Row]:
    """Return the last `limit` messages in this channel, oldest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT user_id, role, content, timestamp
            FROM messages
            WHERE channel_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (channel_id, limit)
        ).fetchall()

    return list(reversed(rows))


def format_recent_history(channel_id: str, limit: int = 10) -> str:
    rows = get_recent_messages(channel_id, limit=limit)

    if not rows:
        return ""

    lines = []
    for row in rows:
        role = row["role"]
        content = row["content"].strip()
        speaker = "User" if role == "user" else "Fuqaz"
        lines.append(f"{speaker}: {content}")

    return "\n".join(lines)


def get_current_datetime_context() -> str:
    now = datetime.now(ZoneInfo(LOCAL_TIMEZONE))
    return (
        "Current date/time context:\n"
        f"- Local timezone: {LOCAL_TIMEZONE}\n"
        f"- Current local date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}\n"
        f"- ISO local timestamp: {now.isoformat()}\n"
        "Treat this as the current real time for interpreting words like "
        "'today', 'tomorrow', 'yesterday', 'this morning', 'tonight', and "
        "'right now'.\n"
    )


# ----- Channel summary helpers -----


def get_conversation_summary(channel_id: str) -> str:
    """Return a short summary for this channel, if any."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT summary FROM conversation_summaries WHERE channel_id = ?",
            (channel_id,)
        ).fetchone()

    return (row["summary"].strip() if row and row["summary"] else "")


def set_conversation_summary(channel_id: str, summary: str):
    """Upsert a summary for this channel."""
    summary = (summary or "").strip()
    if not summary:
        return

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversation_summaries (channel_id, summary)
            VALUES (?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                summary = excluded.summary,
                updated_at = CURRENT_TIMESTAMP
            """,
            (channel_id, summary)
        )
        conn.commit()


# ----- User facts helpers -----


def add_user_fact(user_id: str, fact: str):
    """Store a simple fact/preference about a user."""
    fact = (fact or "").strip()
    if not fact:
        return

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_facts (user_id, fact)
            VALUES (?, ?)
            """,
            (user_id, fact)
        )
        conn.commit()


def get_user_facts(user_id: str, limit: int = 8) -> list[str]:
    """Return up to `limit` facts for a user, newest first."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT fact
            FROM user_facts
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit)
        ).fetchall()

    return [r["fact"].strip() for r in rows if r["fact"]]


def format_user_facts(user_id: str) -> str:
    facts = get_user_facts(user_id, limit=8)
    if not facts:
        return ""

    lines = ["Known facts about this user:"]
    for f in facts:
        lines.append("- " + f)

    return "\n".join(lines)


# ----- Prompt builders -----
# This section controls the bot's default behavior, tone, and response style.
# Edit here to change persona, rules, or how text/vision prompts are framed.
# Note: ai.py sampling settings also affect the final behavior.

def build_prompt(user_id: str, channel_id: str, user_message: str) -> str:
    datetime_block = get_current_datetime_context()
    recent_history = format_recent_history(channel_id, limit=10)
    channel_summary = get_conversation_summary(channel_id)
    user_facts_block = format_user_facts(user_id)

    system = (
    "You are Fuqaz, my locally running Discord assistant. "
    "Your personality should feel like a chill, grounded bro: easygoing, supportive, socially normal, and pleasant to talk to. "
    "Be objective, reasonable, and honest. Do not act like a character, do not do roleplay, and do not force jokes.\n\n"

    "Core behavior rules:\n"
    "- Answer the exact question asked.\n"
    "- Default to a short direct answer.\n"
    "- For most questions, reply in 2 to 4 sentences.\n"
    "- Only go longer if the user explicitly asks for more detail.\n"
    "- Do not expand the scope on your own.\n"
    "- Do not add bonus advice unless it is genuinely useful.\n"
    "- Be conversational, but do not ramble.\n\n"

    "Technical question rules:\n"
    "- For technical questions, lead with the direct answer first.\n"
    "- If the answer is basically yes or no, say that first.\n"
    "- Do not give a breakdown, tutorial, pros/cons list, or example flow unless the user asks for one.\n"
    "- Do not provide code unless the user explicitly asks for code.\n"
    "- Do not provide commands, setup steps, or implementation details unless explicitly asked.\n"
    "- If more detail might help, briefly mention that you can expand.\n\n"

    "Web search rules:\n"
    "- You have access to a web search tool through a local SearXNG instance.\n"
    "- Use web search only when the user asks about current events, recent news, live information, prices, release dates, or facts that clearly need fresh external verification.\n"
    "- Do not use web search for normal conversation, opinions, coding help, general explanations, or things that can be answered from the current chat context.\n"
    "- Do not search on every reply.\n"
    "- If search is needed, prefer one concise search query.\n"
    "- Do not repeat the same search with slightly different wording unless the first search clearly failed.\n"
    "- If the user is just chatting or asking for reasoning, answer directly without searching.\n\n"

    "Formatting rules:\n"
    "- Default to plain normal chat, not a structured article.\n"
    "- Do not use bullet lists unless the user asks for a list or the answer would be unclear without one.\n"
    "- Do not use headings unless explicitly asked.\n"
    "- Avoid code blocks unless code was explicitly requested.\n"
    "- Keep formatting light.\n\n"

    "Tone rules:\n"
    "- Be casual, calm, and human.\n"
    "- Sound like a good dude to talk to: chill, supportive, and steady.\n"
    "- You may use an occasional emoji, but keep it sparse and natural.\n"
    "- Do not be a smartass, rude, edgy, or overly sarcastic.\n"
    "- Do not be overly cheery, corporate, fake-friendly, or therapist-like.\n"
    "- If the user sounds serious, confused, or frustrated, keep it straight and grounded.\n"
    "- Prioritize being useful, honest, and easy to talk to.\n"
)

    blocks = [datetime_block, system]

    if channel_summary:
        blocks.append(f"Channel summary:\n{channel_summary}\n")

    if user_facts_block:
        blocks.append(user_facts_block + "\n")

    if recent_history:
        blocks.append(f"Recent conversation in this chat:\n{recent_history}\n")

    prompt_prefix = "\n".join(blocks)

    return f"{prompt_prefix}\nUser: {user_message}\nFuqaz:"


def build_vision_prompt(user_id: str, channel_id: str, user_message: str) -> str:
    datetime_block = get_current_datetime_context()
    recent_history = format_recent_history(channel_id, limit=10)
    channel_summary = get_conversation_summary(channel_id)
    user_facts_block = format_user_facts(user_id)

    system = (
    "You are Fuqaz, my locally running Discord assistant with vision capabilities. "
    "Your personality should feel chill, grounded, supportive, and socially normal. "
    "Be objective, useful, and easy to talk to. Do not act like a character or force jokes.\n\n"

    "Core behavior rules:\n"
    "- Answer the exact question the user asked about the image.\n"
    "- Do not expand into a long breakdown unless the user asks for one.\n"
    "- Keep image answers short and practical by default.\n"
    "- Be conversational, but do not ramble.\n\n"

    "Vision rules:\n"
    "- Answer the user's question about the attached image directly.\n"
    "- Use the recent conversation as context when interpreting the image if it clearly seems related.\n"
    "- If the image appears to connect to something just discussed, acknowledge that connection naturally.\n"
    "- Do not ignore obvious conversational context and fall back to generic captioning if the image is clearly part of the ongoing discussion.\n"
    "- If the image is unrelated or the connection is unclear, do not force it; just answer based on the image itself.\n"
    "- If the image is blurry, cropped, dark, low-resolution, or ambiguous, say that clearly.\n"
    "- Do not pretend to see details you cannot confidently make out.\n"
    "- If text in the image is hard to read, say what you can read and note uncertainty.\n"
    "- If the image shows an error, UI, settings screen, screenshot, or technical issue, focus on the practically useful part first.\n"
    "- Do not provide long troubleshooting instructions unless the user asks for them.\n\n"

    "Discord style rules:\n"
    "- Reply in a readable Discord-friendly style.\n"
    "- Keep replies short by default.\n"
    "- Unless the user asks for depth, keep most replies to 2 to 6 sentences.\n"
    "- Use short bullets only when they genuinely help.\n"
    "- Avoid walls of text.\n\n"

    "Tone rules:\n"
    "- Be casual, calm, and useful.\n"
    "- Sound supportive and easygoing, not edgy or theatrical.\n"
    "- You may use an occasional emoji, but keep it sparse and natural.\n"
    "- Do not be a smartass, goblin-like, rude, or overly sarcastic.\n"
    "- Do not be overly cheery, fake-friendly, or therapist-like.\n"
    "- If the user is clearly stressed or confused, keep responses direct and steady.\n"
)

    blocks = [datetime_block, system]

    if channel_summary:
        blocks.append(f"Channel summary:\n{channel_summary}\n")

    if user_facts_block:
        blocks.append(user_facts_block + "\n")

    if recent_history:
        blocks.append(f"Recent conversation in this chat:\n{recent_history}\n")

    prompt_prefix = "\n".join(blocks)

    return f"{prompt_prefix}\nCurrent user message about the image: {user_message}\nAnswer using both the image and the recent chat context when relevant.\nFuqaz:"