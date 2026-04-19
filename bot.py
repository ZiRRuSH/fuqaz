import os
import time
import asyncio
import discord
from discord import app_commands
from dotenv import load_dotenv
from ai import ask_local_model, ask_local_model_with_images
from memory import (
    init_memory,
    save_message,
    build_prompt,
    build_vision_prompt,
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True

# ANSI colors for a normal dark terminal
RESET = "\033[0m"
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"

def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"

# Timeout value for the bot to remain interactive after being tagged in chat
CONVO_TIMEOUT_SECONDS = 300  # 5 minutes
# Commands to force the bot to return to an 'inactive' state after being tagged
STOP_WORDS = {
    "shut up", "stop", "stfu", "be quiet", "hush"
}

# (channel_id, user_id) -> last_active_timestamp
active_conversations = {}


class LocalAIBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        init_memory()

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()


bot = LocalAIBot()


def normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def is_stop_message(text: str) -> bool:
    cleaned = normalize_text(text)
    return cleaned in STOP_WORDS


def set_conversation_active(channel_id: str, user_id: str):
    active_conversations[(channel_id, user_id)] = time.time()


def clear_conversation_active(channel_id: str, user_id: str):
    active_conversations.pop((channel_id, user_id), None)


def is_conversation_active(channel_id: str, user_id: str) -> bool:
    key = (channel_id, user_id)
    last_active = active_conversations.get(key)

    if last_active is None:
        return False

    if time.time() - last_active > CONVO_TIMEOUT_SECONDS:
        active_conversations.pop(key, None)
        return False

    return True


def build_source_meta_for_message(message: discord.Message) -> dict:
    is_dm = isinstance(message.channel, discord.DMChannel)

    if is_dm:
        location = "DM"
    else:
        channel_name = getattr(message.channel, "name", None)
        location = f"#{channel_name}" if channel_name else f"channel:{message.channel.id}"

    return {
        "user": message.author.display_name,
        "location": location,
    }


def build_source_meta_for_interaction(interaction: discord.Interaction) -> dict:
    is_dm = interaction.guild is None

    if is_dm:
        location = "DM"
    else:
        channel_name = getattr(interaction.channel, "name", None)
        location = f"#{channel_name}" if channel_name else f"channel:{interaction.channel_id}"

    return {
        "user": interaction.user.display_name,
        "location": location,
    }


async def collect_image_bytes_from_message(message: discord.Message) -> list[bytes]:
    image_bytes = []

    for attachment in message.attachments:
        if attachment.content_type and attachment.content_type.startswith("image/"):
            image_bytes.append(await attachment.read())

    return image_bytes


async def collect_image_bytes_from_context(message: discord.Message) -> list[bytes]:
    image_bytes = await collect_image_bytes_from_message(message)

    if image_bytes:
        return image_bytes

    if message.reference and message.reference.resolved:
        ref = message.reference.resolved
        if isinstance(ref, discord.Message):
            return await collect_image_bytes_from_message(ref)

    return []


def is_discord_503(error: Exception) -> bool:
    if not isinstance(error, discord.errors.DiscordServerError):
        return False

    text = str(error)
    return "503" in text or "Service Unavailable" in text


def sanitize_discord_content(content: str) -> str:
    content = (content or "").strip()
    if not content:
        return "..."

    if len(content) > 2000:
        content = content[:1997] + "..."

    return content


async def safe_send(channel, content: str, retries: int = 3, base_delay: float = 2.0):
    content = sanitize_discord_content(content)
    last_error = None

    for attempt in range(retries):
        try:
            return await channel.send(content)
        except discord.errors.DiscordServerError as e:
            last_error = e

            if is_discord_503(e):
                delay = base_delay * (attempt + 1)
                print(
                    f"{color('[Fuqaz]', YELLOW)} Discord 503 while sending message. "
                    f"Retry {attempt + 1}/{retries} in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                continue

            raise

    print(f"{color('[Fuqaz]', RED)} Repeated Discord 503 on send. Exiting for external restart. Last error: {last_error}")
    os._exit(1)


async def safe_followup_send(interaction: discord.Interaction, content: str, retries: int = 3, base_delay: float = 2.0):
    content = sanitize_discord_content(content)
    last_error = None

    for attempt in range(retries):
        try:
            return await interaction.followup.send(content)
        except discord.errors.DiscordServerError as e:
            last_error = e

            if is_discord_503(e):
                delay = base_delay * (attempt + 1)
                print(
                    f"{color('[Fuqaz]', YELLOW)} Discord 503 while sending followup. "
                    f"Retry {attempt + 1}/{retries} in {delay:.1f}s"
                )
                await asyncio.sleep(delay)
                continue

            raise

    print(f"{color('[Fuqaz]', RED)} Repeated Discord 503 on followup send. Exiting for external restart. Last error: {last_error}")
    os._exit(1)


async def safe_send_error(channel, text: str):
    try:
        await safe_send(channel, text)
    except Exception as e:
        print(f"{color('[Fuqaz]', RED)} Failed to send error message to Discord: {e}")


async def safe_followup_error(interaction: discord.Interaction, text: str):
    try:
        await safe_followup_send(interaction, text)
    except Exception as e:
        print(f"{color('[Fuqaz]', RED)} Failed to send followup error message to Discord: {e}")


async def generate_reply_for_message(message: discord.Message, cleaned_text: str) -> str:
    image_bytes = await collect_image_bytes_from_context(message)

    if not cleaned_text and image_bytes:
        cleaned_text = "What's in this image?"
    elif not cleaned_text:
        cleaned_text = "hello"

    if image_bytes:
        prompt = build_vision_prompt(
            str(message.author.id),
            str(message.channel.id),
            cleaned_text
        )
        return ask_local_model_with_images(prompt, image_bytes)
    else:
        prompt = build_prompt(
            str(message.author.id),
            str(message.channel.id),
            cleaned_text
        )
        source_meta = build_source_meta_for_message(message)
        return ask_local_model(prompt, source_meta=source_meta)


@bot.event
async def on_ready():
    print(f"{color('[Fuqaz]', GREEN)} Logged in as {color(str(bot.user), CYAN)}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    user_id = str(message.author.id)
    is_dm = isinstance(message.channel, discord.DMChannel)
    cleaned = message.content.strip()

    # DMs: always listen
    if is_dm:
        if is_stop_message(cleaned):
            await safe_send(message.channel, "alright, i'll shut the fuck up 😌")
            return

        save_message(
            channel_id=channel_id,
            user_id=user_id,
            role="user",
            content=cleaned if cleaned else "[image only]"
        )

        async with message.channel.typing():
            try:
                reply = await generate_reply_for_message(message, cleaned)
            except Exception as e:
                await safe_send_error(message.channel, f"Local model error: {e}")
                return

        save_message(
            channel_id=channel_id,
            user_id=str(bot.user.id),
            role="assistant",
            content=reply
        )

        await safe_send(message.channel, reply)
        return

    mentioned = bot.user and bot.user in message.mentions
    active = is_conversation_active(channel_id, user_id)

    # Server: stop following if user tells it to stop
    if active and is_stop_message(cleaned):
        clear_conversation_active(channel_id, user_id)
        await safe_send(message.channel, "aight, muting myself unless you tag me again 👍")
        return

    # Server: reply if tagged OR if in active follow-up mode
    if mentioned or active:
        if mentioned:
            cleaned = (
                cleaned
                .replace(f"<@{bot.user.id}>", "")
                .replace(f"<@!{bot.user.id}>", "")
                .strip()
            )

        save_message(
            channel_id=channel_id,
            user_id=user_id,
            role="user",
            content=cleaned if cleaned else "[image only]"
        )

        async with message.channel.typing():
            try:
                reply = await generate_reply_for_message(message, cleaned)
            except Exception as e:
                await safe_send_error(message.channel, f"Local model error: {e}")
                return

        save_message(
            channel_id=channel_id,
            user_id=str(bot.user.id),
            role="assistant",
            content=reply
        )

        set_conversation_active(channel_id, user_id)
        await safe_send(message.channel, reply)


@bot.tree.command(name="ask", description="Ask your local AI")
@app_commands.describe(prompt="Your question for the local model")
async def ask(interaction: discord.Interaction, prompt: str):
    channel_id = str(interaction.channel_id)
    user_id = str(interaction.user.id)

    save_message(
        channel_id=channel_id,
        user_id=user_id,
        role="user",
        content=prompt
    )

    full_prompt = build_prompt(user_id, channel_id, prompt)
    source_meta = build_source_meta_for_interaction(interaction)

    await interaction.response.defer(thinking=True)

    try:
        reply = ask_local_model(full_prompt, source_meta=source_meta)
    except Exception as e:
        await safe_followup_error(interaction, f"Local model error: {e}")
        return

    save_message(
        channel_id=channel_id,
        user_id=str(bot.user.id),
        role="assistant",
        content=reply
    )

    set_conversation_active(channel_id, user_id)
    await safe_followup_send(interaction, reply)


@bot.tree.command(name="vision", description="Ask your local AI about an attached image")
@app_commands.describe(prompt="Your question about the image", image="Attach an image")
async def vision(interaction: discord.Interaction, prompt: str, image: discord.Attachment):
    channel_id = str(interaction.channel_id)
    user_id = str(interaction.user.id)

    await interaction.response.defer(thinking=True)

    if not image.content_type or not image.content_type.startswith("image/"):
        await safe_followup_send(interaction, "Please attach an image file.")
        return

    save_message(
        channel_id=channel_id,
        user_id=user_id,
        role="user",
        content=f"[image] {prompt}"
    )

    try:
        image_bytes = await image.read()
        full_prompt = build_vision_prompt(user_id, channel_id, prompt)
        reply = ask_local_model_with_images(full_prompt, [image_bytes])
    except Exception as e:
        await safe_followup_error(interaction, f"Local vision error: {e}")
        return

    save_message(
        channel_id=channel_id,
        user_id=str(bot.user.id),
        role="assistant",
        content=reply
    )

    set_conversation_active(channel_id, user_id)
    await safe_followup_send(interaction, reply)


bot.run(TOKEN)