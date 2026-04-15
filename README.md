# Fuqaz

A simple local Discord bot powered by Ollama, with lightweight SQLite chat memory and optional vision support.

The goal of this bot is to stay fast, practical, and easy to tweak. It runs locally, keeps recent chat context plus a small memory database, and can answer normal text questions or image-based questions depending on the model you use. The current code uses Ollama’s `/api/generate` endpoint for text and vision requests.

This was/is just a personal experimental project I did out of boredum, but found it convenient and simple enough I decided to share it. Two birds with one stone, provides an entertaining Discord bot while also allowing you remote access to local LLM's through discord.

## Features

- Local Discord bot using `discord.py`
- Runs against a local Ollama model.
- SQLite-based memory for:
  - recent per-channel messages,
  - per-channel summaries,
  - per-user facts/preferences.
- Basic vision flow for image attachments and replied-to images.
- Simple, hackable code layout with only a few files.

## Files

- `bot.py` — Discord bot event handling, slash commands, conversation flow.
- `ai.py` — Ollama request handling for text and vision.
- `memory.py` — SQLite memory tables, recent history formatting, prompt builders.

## Requirements

- Python 3.10+ recommended.
- A local Ollama install with at least one working model.
- A Discord bot token from the Discord Developer Portal.
- Optional: a local SearXNG stack if you want to allow internet searches. (no direct scraping/fetches)


## Install

1. Clone the repo.
2. Create and activate a virtual environment.
3. Install dependencies.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure Ollama

Make sure Ollama is installed and running locally. The current bot expects Ollama to be available at `http://localhost:11434/api/generate`, which is the normal/default endpoint.

Pull a model you want to use, by default the bot is configured for Ministral-3:8b:

```bash
ollama pull ministral-3:8b
```

Then confirm your chosen model name matches what you put in `.env` and towards the top of 'ai.py'

## Environment variables

Create a `.env` file in the project root.

Example:

```.env
DISCORD_TOKEN=YOUR_BOT_TOKEN_GOES_HERE_KEEP_IT_PRIVATE
GUILD_ID=YOUR_SERVER_TOKEN_GOES_HERE
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=ministral-3:8b
SEARXNG_URL=http://127.0.0.1:8080/search
LOCAL_TIMEZONE=America/New_York

```

### Notes

- `DISCORD_TOKEN` is required and aquired through the Discord developer portal (instructions below)
- `GUILD_ID` is your server's ID, you can see this by enabling developer mode in discord's settings then right clicking on your server icon in discord.
- `OLLAMA_URL` defaults to `http://localhost:11434/api/generate` in the current code.
- `OLLAMA_MODEL` is the model the bot will run and should match a model you already have pulled in Ollama. 'ollama list' lists pulled models and names you currently have available.
- `SEARXNG_URL` can stay in the file even if you are not using search yet. It does not hurt anything by being present but provides a search tool to the bot if you decide to install SearXNG.
- `LOCAL_TIMEZONE` IANA timezone name used for date/time grounding in prompts, for example `America/New_York`.

## Discord bot setup

### 1. Create an application

Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.  
Then open the **Bot** tab and add a bot user for the application.

### 2. Copy the bot token

In the **Bot** page, reset/copy the token and place it in your `.env` file as `DISCORD_TOKEN`.  
Keep this token private. Anyone who gets it can control your bot.

### 3. Make the bot private

If you are running this bot against your own local Ollama instance, it is strongly recommended to keep the bot private.

In the Developer Portal under **Bot**, leave **Public Bot** unchecked.  
Discord’s bot authorization flow states that when **Public Bot** is disabled, only the bot owner can add the bot to servers; if it is enabled, anyone with the invite URL can add it to servers where they have permission.

This is the safest default for a self-hosted bot, because it prevents other people from inviting your bot into their own servers and sending traffic to your local LLM.

### 4. Enable Message Content Intent

This project uses `intents.message_content = True`, so you need to enable **Message Content Intent** in the Developer Portal under **Bot** → **Privileged Gateway Intents**.  
The `discord.py` intents documentation notes that privileged intents must be enabled in the portal and also enabled in code.

This matters because message content intent is used when a bot needs access to message content, attachments, embeds, components, or similar fields.

### 5. Generate an invite URL

In the Developer Portal, go to **OAuth2** → **URL Generator** and select:

- `bot`
- `applications.commands`

Discord’s OAuth2 documentation notes that `applications.commands` is included by default with the `bot` scope, but selecting both in the UI is still common and harmless for clarity.

For permissions, a practical starting point is:

- View Channels
- Send Messages
- Read Message History
- Attach Files
- Use Application Commands

Try to avoid over-permissioning the bot. You do **not** need Administrator for this project. Discord’s OAuth2 bot authorization flow uses the permissions value in the invite link to request only the permissions you choose.

### 6. Invite the bot to your server

Open the generated invite URL in your browser and add the bot to your server.  
Discord’s bot authorization flow also supports `guild_id` and `disable_guild_select=true` in the invite URL if you want to preselect a specific server and stop the installer from choosing another one.

## Running the bot

Once Ollama is running and your `.env` is configured:

```bash
python bot.py
```

If everything is set up correctly, the bot should log in and print its connected username in the console.

### Getting the bot in your channels

Worth mentioning that if you have any server requirements on new users joining, such as reading and agreeing to rules, you (or a moderator) will need to manually give your bot the roles to get it in channels. Most people will probably create a new role on their server for the bot.  But if you're not seeing it pop up in channels right away after configuring and running, go look for it your welcome channel or whatever and get it situated on its role and server permissions.

## How it works

### `bot.py`

`bot.py` handles:
- Discord login,
- direct message replies,
- mention-based replies in servers,
- short follow-up conversations,
- slash commands like `/ask` and `/vision`,
- message splitting for long responses,
- and collecting images from attachments or replied-to messages.

### `memory.py`

`memory.py` stores lightweight local memory in SQLite:

- `messages` for raw recent chat history,
- `conversation_summaries` for longer channel context,
- `user_facts` for small user-specific facts or preferences.

It also builds the full prompts used for text and vision replies by combining:
- system instructions,
- channel summary,
- user facts,
- recent history,
- and the latest user message.

### `ai.py`

`ai.py` sends prompts to Ollama using the local HTTP API. The current version uses:
- text generation through `/api/generate`,
- image generation requests through the same endpoint with base64-encoded images for multimodal models.

## Vision support

The bot supports image questions if your Ollama model supports images. In normal chat flow, it can:

- read directly attached images,
- or read images from a referenced/replied-to message.

If no text is included with an image, the bot falls back to a default prompt like “What’s in this image?” before sending the request.

## Development notes

A few practical things to know:

- The memory database is local: `fuqaz_memory.db`.
- The bot uses a short recent-history window for context rather than stuffing massive chat logs into every prompt.
- The current code is intentionally simple and easy to edit, not a giant framework.

## License

This project is licensed under the MIT License. See the `LICENSE.txt` file for details.