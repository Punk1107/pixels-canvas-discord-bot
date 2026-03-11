# 🎨 Pixels Canvas Discord Bot

A collaborative, real-time pixel art experience for Discord communities. Built with **Python**, **discord.py**, and **PostgreSQL**.

## 🚀 Key Features

- **Collaborative Canvas**: Draw together on a persistent 2D grid.
- **Per-Server Isolation**: Every Discord server gets its own separate canvas and statistics.
- **Faction System**: Form groups and compete for global dominance on the faction leaderboard.
- **Web API Viewer**: View the live canvas from any browser at `http://localhost:8080/canvas/{server_id}.png`.
- **Personal Stats**: Track your placement history, rank, and total contributions.
- **Admin Tools**: Protect areas, batch-fill regions, draw text, and moderate users.
- **System Reliability**: 
    - **Automated Backups**: Hourly snapshots of the canvas saved as JSON.
    - **Self-Healing DB**: Automatic connection pool monitoring and recovery.

## 🛠️ Tech Stack

- **Core**: Python 3.10+, [discord.py](https://github.com/Rapptz/discord.py)
- **Database**: PostgreSQL with [asyncpg](https://github.com/MagicStack/asyncpg)
- **Image Engine**: [Pillow (PIL)](https://python-pillow.org/)
- **Web API**: [aiohttp](https://docs.aiohttp.org/)
- **Configuration**: [python-dotenv](https://github.com/theskumar/python-dotenv)

## ⌨️ Command Reference

### User Commands
- `/color <x> <y> <color>` - Place a pixel on the canvas.
- `/undo` - Undo your last pixel placement (within 5 minutes).
- `/cooldown` - Check how long until you can draw another pixel.
- `/palette` - See a visual swatch of common colors.
- `/canvas` - View the current state of the canvas.
- `/view [x] [y] [zoom]` - View a zoomed section of the canvas.
- `/timelapse` - Generate a GIF timelapse of the canvas history.
- `/leaderboard` - View the top global contributors.
- `/local_board` - View the top contributors in this specific server.
- `/info <x> <y>` - Get details about a specific pixel (who placed it and when).
- `/stats [user]` - Check your or someone else's pixel placement statistics.
- `/help` - Show information and commands for the bot.

### Faction Commands
- `/join_faction <name>` - Join or create a faction.
- `/leave_faction` - Leave your current faction.
- `/faction_board` - View the top factions by total pixels placed.

### Admin/Mod Commands
- `/protect <x> <y>` - Protect a pixel from being modified.
- `/unprotect <x> <y>` - Unprotect a pixel.
- `/fill <x1> <y1> <x2> <y2> <color>` - Instantly paint a rectangular area.
- `/drawtext <x> <y> <text> <color>` - Render text onto the canvas.
- `/reset` - Reset the entire canvas.
- `/blacklist <user>` - Ban a user from interacting with the canvas.
- `/unblacklist <user>` - Unban a user from the canvas.
- `/setlogchannel <channel>` - Set the channel where moderation logs will be sent.
- `/sync` - Sync slash commands to the current server immediately.

## ⚙️ Setup & Installation

1. **Environment**: Create a `.env` file in the root directory:
   ```env
   DISCORD_TOKEN=your_bot_token_here
   DATABASE_URL=postgres://user:password@localhost:5432/pixel_db
   ```
2. **Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run**:
   ```bash
   python main.py
   ```
   *The database schema will be automatically initialized on first run.*

---
*Developed with 💖 for the Pixels community.*
