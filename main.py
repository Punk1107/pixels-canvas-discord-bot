import discord
from discord.ext import commands
import logging
import logging.handlers
from config import DISCORD_TOKEN
from database.postgres import db
from canvas.renderer import canvas_cache
import traceback
import sys
from discord.ext import tasks
import asyncio
import json
import os
from datetime import datetime
from api.server import start_web_server

# Setup rotating file logger + console output
logger = logging.getLogger('pixelbot')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Console Handler
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

# File Handler (10MB max per file, keep 3 backups)
fh = logging.handlers.RotatingFileHandler(
    filename='pixelbot.log',
    encoding='utf-8',
    maxBytes=10 * 1024 * 1024,
    backupCount=3
)
fh.setFormatter(formatter)
logger.addHandler(fh)

class PixelBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix='!', 
            intents=intents
        )
        self.initial_extensions = [
            'commands.color',
            'commands.canvas',
            'commands.leaderboard',
            'commands.stats',
            'commands.admin',
            'commands.mod',
            'commands.util',
            'commands.factions'
        ]

    async def setup_hook(self):
        # Connect to DB and init schema
        await db.connect()
        
        # Build initial canvas cache
        pixels = await db.get_all_pixels()
        await canvas_cache.build_from_db(pixels)
        
        # Load extensions
        for ext in self.initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension '{ext}'")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}")
            
        # Global Error Handler for Slash Commands
        self.tree.on_error = self.on_app_command_error
            
        # Sync slash commands globally
        await self.tree.sync()
        logger.info("Bot setup complete. Commands synced.")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        
        # Status update
        activity = discord.Activity(type=discord.ActivityType.watching, name="the Pixel Canvas")
        await self.change_presence(status=discord.Status.online, activity=activity)
        
        # Start background tasks
        if not self.auto_backup_canvas.is_running():
            self.auto_backup_canvas.start()
        if not self.db_healthcheck.is_running():
            self.db_healthcheck.start()
            
        # Bind the AIOHTTP Web Server explicitly
        try:
            self.web_runner = await start_web_server()
        except Exception as e:
            logger.error(f"Failed to start Web API: {e}")
            
    @tasks.loop(minutes=5)
    async def db_healthcheck(self):
        try:
            # Ping the DB quietly to ensure pool integrity
            async with db.pool.acquire() as conn:
                await conn.execute('SELECT 1')
            logger.debug("Database healthcheck passed - Pool is healthy.")
        except Exception as e:
            logger.error(f"Database healthcheck failed! Rebuilding connections... : {e}")
            try:
                await db.connect()
                logger.info("Database successfully reconnected after self-healing.")
            except Exception as reconnect_err:
                logger.critical(f"Failed to self-heal database: {reconnect_err}")
                
    @db_healthcheck.before_loop
    async def before_db_healthcheck(self):
        await self.wait_until_ready()
            
    @tasks.loop(hours=1)
    async def auto_backup_canvas(self):
        try:
            logger.info("Starting automated canvas backup...")
            pixels = await db.get_all_pixels()
            
            # Ensure backups directory exists
            os.makedirs("backups", exist_ok=True)
            
            # Build payload
            payload = [{"x": p['x'], "y": p['y'], "color": p['color']} for p in pixels]
            
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backups/canvas_backup_{stamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(payload, f)
                
            logger.info(f"Successfully backed up {len(payload)} pixels to {filename}")
        except Exception as e:
            logger.error(f"Failed to auto-backup canvas: {e}")
            
    @auto_backup_canvas.before_loop
    async def before_auto_backup(self):
        await self.wait_until_ready()

    async def close(self):
        # Graceful shutdown handler
        logger.info("Initiating graceful shutdown...")
        
        # 1. Stop discord.ext.tasks loops
        if self.auto_backup_canvas.is_running():
            self.auto_backup_canvas.cancel()
        if self.db_healthcheck.is_running():
            self.db_healthcheck.cancel()

        # 2. Close Web API Server
        try:
            if hasattr(self, 'web_runner') and self.web_runner:
                await self.web_runner.cleanup()
                logger.info("Web API Server gracefully closed.")
        except Exception as e:
            logger.error(f"Error closing Web API: {e}")
            
        # 3. Close the Bot (Stops events and networking)
        logger.info("Closing Discord connection...")
        await super().close()

        # 4. Cancel any remaining pending asyncio tasks
        tasks_to_cancel = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} pending asyncio tasks...")
            for task in tasks_to_cancel:
                task.cancel()
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            
        # 5. Disconnect from database LAST to ensure tasks don't fail mid-execution
        try:
            await db.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting database: {e}")

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        embed = discord.Embed(
            title="❌ An Error Occurred", 
            description="Something went wrong while processing your command.",
            color=discord.Color.red()
        )
        
        # Expected Exceptions (Do not log tracebacks for these)
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            embed.description = f"This command is on cooldown. Try again in {error.retry_after:.2f}s."
            logger.info(f"User {interaction.user} hit cooldown on /{interaction.command.name if interaction.command else 'Unknown'}")
        elif isinstance(error, discord.app_commands.MissingPermissions):
            embed.description = "You don't have permission to use this command."
            logger.info(f"User {interaction.user} lacked perms for /{interaction.command.name if interaction.command else 'Unknown'}")
        else:
            # Unexpected Runtime Exceptions (Log these loudly)
            logger.error(f"Command Error [{interaction.command.name if interaction.command else 'Unknown'}]: {error}")
            traceback.print_exception(type(error), error, error.__traceback__)
            
        # Safely reply to the user
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            pass

if __name__ == '__main__':
    if not DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN is not set. Please check your .env file.")
        exit(1)
        
    bot = PixelBot()
    bot.run(DISCORD_TOKEN)
