# Free Members Discord Bot

A small Discord bot for server tracking and administrative notifications.

## Safety boundary

The supplied source included OAuth access/refresh-token collection, storage in `auths.txt`, token refresh, and mass member-joining. Those features were not copied: they can enable unauthorized account access and mass-adding users, and may violate Discord's Terms of Service. The supplied `auths.txt` credentials were not written to the project or used.

This bot never requests, stores, refreshes, validates, or transfers user OAuth tokens.

## Setup

1. Create a Discord application and bot in the [Discord Developer Portal](https://discord.com/developers/applications).
2. Enable only the intents the bot needs. No privileged intent is required by this version.
3. Install Python 3.10 or newer.
4. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

5. Set environment variables. Copy `.env.example` to `.env` only if your local process loads environment files, or export the variables directly:

   ```bash
   export DISCORD_BOT_TOKEN='your-bot-token'
   export MAIN_SERVER_ID='your-main-server-id'
   export LEAVE_AFTER_DAYS='14'
   ```

   Never commit the token or paste it into source code.

6. Invite the bot with only View Channel and Send Messages permissions, then run:

   ```bash
   python bot.py
   ```

## Commands

- `!help` — show available commands
- `!servers` — list servers where the bot is installed
- `!server_age [SERVER_ID]` — show tracking age and departure estimate
- `!invite` — generate a least-privilege invite URL

The bot records server join times in memory. It notifies the configured main server when it joins or leaves a non-main server and automatically leaves non-main servers after `LEAVE_AFTER_DAYS`.
