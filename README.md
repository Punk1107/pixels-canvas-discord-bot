# 🎨 Pixels Canvas Discord Bot

A collaborative, real-time pixel art experience for Discord communities. Built with **Python**, **discord.py**, and **PostgreSQL**.

## 🚀 Key Features

- **Collaborative Canvas**: Draw together on a persistent 2D grid.
- **Faction System**: Form groups and compete for global dominance on the faction leaderboard.
- **Web API Viewer**: View the live canvas from any browser at `http://localhost:8080/canvas.png`.
- **Personal Stats**: Track your placement history, rank, and total contributions.
- **Admin Tools**: Protect areas, batch-fill regions, and draw text instantly.
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
- `/canvas` - View the current state of the canvas.
- `/leaderboard` - View the top global contributors.
- `/info <x> <y>` - Get details about a specific pixel (who placed it and when).
- `/stats [user]` - Check your or someone else's pixel placement statistics.

### Faction Commands
- `/join_faction <name>` - Join or create a faction.
- `/leave_faction` - Leave your current faction.
- `/faction_board` - View the top factions by total pixels placed.

### Admin/Mod Commands
- `/protect <x> <y>` - Lock a pixel from being modified by standard users.
- `/unprotect <x> <y>` - Unlock a pixel.
- `/fill <x1> <y1> <x2> <y2> <color>` - Instantly paint a rectangular area.
- `/drawtext <x> <y> <text> <color>` - Render text onto the canvas.

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
