![Fuqaz banner](banner.png)

# Fuqaz

A simple local Discord bot powered by Ollama, with lightweight SQLite chat memory and optional vision support.

The goal of this bot is to stay fast, practical, and easy to tweak. It runs locally, keeps recent chat context plus a small memory database, and can answer normal text questions or image-based questions depending on the model you use. The current code uses Ollama’s `/api/generate` endpoint for text and vision requests.

This started as a personal experiment I built out of boredom, but it turned out useful and simple enough that I decided to share it. Two birds with one stone: an entertaining Discord bot that also gives you remote access to your local LLMs through Discord.

## Features

- Local Discord bot using `discord.py`
- Runs against a local Ollama model.
- SQLite-based memory for:
  - recent per-channel messages,
  - per-channel summaries,
  - per-user facts/preferences.
- Basic vision flow for image attachments and replied-to images.
- Simple, tinker-friendly code layout with only a few files.

## Files

- `bot.py` — Discord bot event handling, slash commands, conversation flow.
- `ai.py` — Ollama request handling for text and vision.
- `memory.py` — SQLite memory tables, recent history formatting, prompt builders.

## Requirements

- [Python](https://www.python.org/downloads/) 3.10+ recommended.
- A local [Ollama](https://ollama.com/download) install with at least one working model.
- A Discord bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
- Optional: a local [SearXNG](https://docs.searxng.org/) stack if you want to allow internet searches.


## Install

1. Clone the repo.
2. Enter 'fuqaz' directory.
3. Create and activate a virtual environment.
4. Install dependencies.

```
git clone https://github.com/ZiRRuSH/fuqaz
```

```
cd fuqaz
```

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configure Ollama

Make sure [Ollama](https://ollama.com/download) is installed and running locally. The current bot expects Ollama to be available at `http://localhost:11434/api/generate`, which is the normal/default endpoint.

Pull a model you want to use. By default, the bot is configured for Ministral-3 8B.

- If you use a model outside the Ministral-3 family, you may need to adjust the sampling values near the top of `ai.py`. (a quick web search of your chosen model's recommended sampling values should land you quick results.)
- If the chosen model does not support vision, the bot will still work, but image parsing will not.
    
```bash
ollama pull ministral-3:8b
```

Then confirm your chosen model name matches what you put in `.env`.

```bash
ollama list
```

## Environment variables

Create a `.env` file in the project root. A `.env.example` file is included.

Example:

```.env
DISCORD_TOKEN=YOUR_BOT_TOKEN_GOES_HERE_KEEP_IT_PRIVATE
GUILD_ID=YOUR_SERVER_ID_GOES_HERE
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=ministral-3:8b
SEARXNG_URL=http://127.0.0.1:8080/search
LOCAL_TIMEZONE=America/New_York

```

### Notes

- `DISCORD_TOKEN` is required and acquired through the [Discord Developer Portal](https://discord.com/developers/applications) (instructions below).
- `GUILD_ID` is your server's ID, you can see this by enabling developer mode in discord's settings then right clicking on your server icon in Discord and 'Copy Server Info > Copy Server ID'.
- `OLLAMA_URL` defaults to `http://localhost:11434/api/generate` in the current code.
- `OLLAMA_MODEL` is the model the bot will run and should match a model you already have pulled in Ollama. `ollama list` lists pulled models and names you currently have available.
- `SEARXNG_URL` can stay in the file even if you are not using search yet. It does not hurt anything by being present, but provides a search tool to the bot if you decide to install [SearXNG](https://docs.searxng.org/).
- `LOCAL_TIMEZONE` [IANA TimeZone](https://nodatime.org/TimeZones) name used for date/time grounding in prompts, for example `America/New_York`.

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
Discord’s bot authorization flow states that when **Public Bot** is disabled, only the bot owner can add the bot to servers; if it is enabled, your Bot's profile within Discord will have an "Add" button allowing anyone to invite it to their server as well as allowing anyone with the invite link to do the same.

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


## Running the bot

Once Ollama is running and your `.env` is configured, within the activated virtual environment:

```bash
python bot.py
```

If everything is set up correctly, the bot should log in and print its connected username in the console.
- Users can interact with the bot within Discord by @ tagging it in chat, by DM, or with the slash commands /ask and /vision.
  - After tagging the bot in a chat channel, it will remain interactive with the user for 300 seconds (5 minutes) if no other users are chatting in the channel.
  - If the user responds with a `STOP_WORD` it will end the persistent interaction, STOP_WORDS are located near the top of the bot.py file and can be customized.

NOTE: Before executing `python bot.py` you need to be in the virtual environment. Your terminal will show a `(.venv)` or similar prepending the usual `C:\` or `[user@hostname ~]$` in your terminal while in the virtual environment (if you don't see that, you're not in the venv). You'll have to activate the venv anytime you restart or close out the terminal, or `deactivate` the venv within the terminal. Listed below are the commands for activating the venv:

  - Linux/Mac (from within the 'fuqaz' directory):
  - ```
    source .venv/bin/activate
    ```
  - Windows Powershell (from within the 'fuqaz' directory):
    ```
    .venv\Scripts\Activate.ps1
    ```

  
### Getting the bot in your channels

Worth mentioning that if you have any server requirements such as reading and agreeing to rules to gain channel permissions, you (or a moderator) will need to manually give your bot the required roles/permissions it needs to access channels.

## How it works

### `bot.py`

`bot.py` handles:
- Discord login,
- direct message replies,
- mention-based replies in servers,
- short follow-up conversations,
- slash commands like `/ask` and `/vision`,
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
- image analysis requests through the same endpoint with base64-encoded images for multimodal models.

## Vision support

The bot supports image questions if your Ollama model supports images. In normal chat flow, it can:

- read directly attached images,
- or read images from a referenced/replied-to message.

If no text is included with an image, the bot falls back to a default prompt like “What’s in this image?” before sending the request.

## Development notes

A few practical things to know:

- The memory database is local: `fuqaz_memory.db`.
- The bot uses a short recent-history window for context rather than stuffing massive chat logs into every prompt.
- If you experience context rot, try reducing the "limit: int = 10" values in memory.py.
- The current code is intentionally simple and easy to edit, not a giant framework.
- It does not play well with every model in Ollama (It doesn't like thinking models like qwen 3.5, I intend to iron those wrinkles out in time. Gemma4 works but is quirky as well, but I think that may be on the Ollama side right now 🤷‍♂️ ).  If you encounter problems, feel free to post an issue and ensure you include the model used. No promises, but when I'm bored and tinkering I may look into them.
- I encourage experimenting with the prompting in memory.py, this is a good place to try and work out quirks or dial-in specific personas/attitudes with your bot.
- The code has SOME basic error handling in it, in particular for 503 errors it may encounter. It will end its process after a few failed retries, pairing the bot with [NSSM](https://nssm.cc/) in Windows or a systemd unit file in Linux can allow automated recovery if that occurs while you're away (Error Handling will get implemented as I encounter errors xD ).
- This is a 'for-fun' project I began out of boredom and curiosity, I felt it was useful and simple enough to get set up that others may enjoy it too. I will likely make improvements and adjustments over time, but this is not a high priority project.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
