# Pixel Canvas Discord Bot

A Discord Bot that allows users to collaborate on a pixel canvas, built with Python, discord.py, and PostgreSQL.

## Tech Stack
- Python
- discord.py
- PostgreSQL
- asyncpg
- Pillow

## Concepts
- 2D Array
- Async Programming
- Database Persistence
- Image Rendering
- Slash Commands API

## Features
- Update pixels with `/color`
- View the canvas with `/canvas`
- Keep track of top contributors with `/leaderboard`

## Setup
1. Define environment variables in `.env` (use `DISCORD_TOKEN`, `DATABASE_URL` or DB credentials).
2. Install pip requirements.
3. Run `main.py`. The database tables will be automatically initialized when the bot starts.
