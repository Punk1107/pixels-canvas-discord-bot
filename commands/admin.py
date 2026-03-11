import discord
from discord.ext import commands
from discord import app_commands
from database.postgres import db
from canvas.renderer import is_valid_color, canvas_cache
from config import CANVAS_WIDTH, CANVAS_HEIGHT
from PIL import Image, ImageDraw, ImageFont

class AdminCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="protect", description="Protect a pixel from being modified (Admin only)")
    @app_commands.describe(x="X coordinate", y="Y coordinate")
    @app_commands.default_permissions(administrator=True)
    async def protect(self, interaction: discord.Interaction, x: int, y: int):
        await interaction.response.defer()
        try:
            await db.set_pixel_protection(x, y, True)
            embed = discord.Embed(
                title="🛡️ Pixel Protected",
                description=f"Pixel at `({x}, {y})` is now protected and can no longer be modified by standard users.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            
            # Send Mod Log
            if interaction.guild_id:
                log_channel_id = await db.get_log_channel(interaction.guild_id)
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="🛡️ Admin Action: Pixel Protected",
                            description=f"**Admin:** {interaction.user.mention}\n**Location:** `({x}, {y})`\n**Channel:** {interaction.channel.mention}",
                            color=discord.Color.brand_red()
                        )
                        await log_channel.send(embed=log_embed)
                        
        except Exception as e:
            await interaction.followup.send(f"❌ Error protecting pixel: {str(e)}")

    @app_commands.command(name="unprotect", description="Unprotect a pixel (Admin only)")
    @app_commands.describe(x="X coordinate", y="Y coordinate")
    @app_commands.default_permissions(administrator=True)
    async def unprotect(self, interaction: discord.Interaction, x: int, y: int):
        await interaction.response.defer()
        try:
            await db.set_pixel_protection(x, y, False)
            embed = discord.Embed(
                title="🔓 Pixel Unprotected",
                description=f"Pixel at `({x}, {y})` is now unprotected and can be modified again.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed)
            
            # Send Mod Log
            if interaction.guild_id:
                log_channel_id = await db.get_log_channel(interaction.guild_id)
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="🔓 Admin Action: Pixel Unprotected",
                            description=f"**Admin:** {interaction.user.mention}\n**Location:** `({x}, {y})`\n**Channel:** {interaction.channel.mention}",
                            color=discord.Color.orange()
                        )
                        await log_channel.send(embed=log_embed)
                        
        except Exception as e:
            await interaction.followup.send(f"❌ Error unprotecting pixel: {str(e)}")

    @app_commands.command(name="fill", description="Admin tool to instantly fill a rectangle of pixels (Admin only)")
    @app_commands.describe(
        x1="Top Left X",
        y1="Top Left Y",
        x2="Bottom Right X",
        y2="Bottom Right Y",
        color="Color to fill with"
    )
    @app_commands.default_permissions(administrator=True)
    async def fill(self, interaction: discord.Interaction, x1: int, y1: int, x2: int, y2: int, color: str):
        if not is_valid_color(color):
            await interaction.response.send_message("❌ Invalid color string.", ephemeral=True)
            return

        # Clamp bounding box
        x_min = max(0, min(x1, x2))
        x_max = min(CANVAS_WIDTH - 1, max(x1, x2))
        y_min = max(0, min(y1, y2))
        y_max = min(CANVAS_HEIGHT - 1, max(y1, y2))
        
        total_pixels = (x_max - x_min + 1) * (y_max - y_min + 1)
        if total_pixels > 50000:
            await interaction.response.send_message("❌ Cannot fill more than 50,000 pixels in a single command. Please use smaller rectangles.", ephemeral=True)
            return

        await interaction.response.defer()
        
        try:
            # Build payload
            pixels_list = []
            for ix in range(x_min, x_max + 1):
                for iy in range(y_min, y_max + 1):
                    pixels_list.append((ix, iy, color))
            
            # Use batch update pipeline
            await db.batch_update_pixels(interaction.guild_id, pixels_list, interaction.user.id)
            await canvas_cache.batch_update_pixels(interaction.guild_id, pixels_list)
            
            embed = discord.Embed(
                title="🖌️ Canvas Area Filled",
                description=f"Instantly painted `{total_pixels:,}` pixels from `({x_min}, {y_min})` to `({x_max}, {y_max})` with `{color}`.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            
            # Send Mod Log
            if interaction.guild_id:
                log_channel_id = await db.get_log_channel(interaction.guild_id)
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="🖌️ Admin Action: Area Fill",
                            description=f"**Admin:** {interaction.user.mention}\n**Area:** `({x_min}, {y_min})` to `({x_max}, {y_max})`\n**Color:** `{color}`\n**Total:** `{total_pixels:,}` pixels",
                            color=discord.Color.brand_red()
                        )
                        await log_channel.send(embed=log_embed)
                        
        except Exception as e:
            await interaction.followup.send(f"❌ Error filling area: {str(e)}")

    @app_commands.command(name="drawtext", description="Instantly draw a word onto the canvas (Admin only)")
    @app_commands.describe(
        x="Starting X coordinate",
        y="Starting Y coordinate",
        text="The word to draw",
        color="Color for the text"
    )
    @app_commands.default_permissions(administrator=True)
    async def drawtext(self, interaction: discord.Interaction, x: int, y: int, text: str, color: str):
        if not is_valid_color(color):
            await interaction.response.send_message("❌ Invalid color string.", ephemeral=True)
            return
            
        if len(text) > 20:
            await interaction.response.send_message("❌ Text is too long. Limit to 20 characters.", ephemeral=True)
            return

        await interaction.response.defer()
        
        try:
            # Create a tiny sandbox image to draw the text onto
            font = ImageFont.load_default()
            # In PIL > 10.0 getbbx is preferred, but getsize works in older. Use a generic large enough canvas
            sandbox_width, sandbox_height = 200, 30
            sandbox = Image.new('1', (sandbox_width, sandbox_height), color=0)
            draw = ImageDraw.Draw(sandbox)
            draw.text((0, 0), text, font=font, fill=1)
            
            # Map the drawn pixels from sandbox back to real coordinates
            pixels_list = []
            for ix in range(sandbox_width):
                for iy in range(sandbox_height):
                    # Check if pixel is drawn (white/1)
                    if sandbox.getpixel((ix, iy)) == 1:
                        target_x = x + ix
                        target_y = y + iy
                        if 0 <= target_x < CANVAS_WIDTH and 0 <= target_y < CANVAS_HEIGHT:
                            pixels_list.append((target_x, target_y, color))
            
            if not pixels_list:
                await interaction.followup.send("❌ Could not generate any pixels for that text.")
                return
                
            # Use batch update pipeline
            await db.batch_update_pixels(interaction.guild_id, pixels_list, interaction.user.id)
            await canvas_cache.batch_update_pixels(interaction.guild_id, pixels_list)
            
            embed = discord.Embed(
                title="📝 Text Drawn",
                description=f"Instantly painted `{text}` at `({x}, {y})` using `{len(pixels_list):,}` pixels.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            
            # Send Mod Log
            if interaction.guild_id:
                log_channel_id = await db.get_log_channel(interaction.guild_id)
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="📝 Admin Action: Text Drawn",
                            description=f"**Admin:** {interaction.user.mention}\n**Text:** `{text}` at `({x}, {y})`\n**Color:** `{color}`\n**Total:** `{len(pixels_list):,}` pixels",
                            color=discord.Color.brand_red()
                        )
                        await log_channel.send(embed=log_embed)
                        
        except Exception as e:
            await interaction.followup.send(f"❌ Error drawing text: {str(e)}")

    @app_commands.command(name="sync", description="Sync slash commands to the current server immediately (Admin only)")
    @app_commands.default_permissions(administrator=True)
    async def sync_commands(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            self.bot.tree.copy_global_to(guild=interaction.guild)
            await self.bot.tree.sync(guild=interaction.guild)
            await interaction.followup.send("✅ Slash commands manually synchronized to this server successfully! You should see `/color` and other commands immediately.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error syncing commands: {str(e)}")

async def setup(bot):
    await bot.add_cog(AdminCommand(bot))
