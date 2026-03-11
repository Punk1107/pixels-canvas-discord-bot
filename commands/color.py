import discord
from discord.ext import commands
from discord import app_commands
from database.postgres import db
from canvas.renderer import is_valid_color, canvas_cache
from PIL import ImageColor
from config import CANVAS_WIDTH, CANVAS_HEIGHT

class ColorCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def color_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        colors = ['red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'brown', 'black', 'white', 
                  'cyan', 'magenta', 'lime', 'teal', 'navy', 'maroon', 'olive', 'silver', 'gray', '#FF0000', 
                  '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF']
        return [
            app_commands.Choice(name=c, value=c)
            for c in colors if current.lower() in c.lower()
        ][:25] # max 25 choices for autocomplete
        
    @app_commands.command(name="color", description="Change a pixel's color on the canvas")
    @app_commands.describe(x="X coordinate of the pixel", y="Y coordinate of the pixel", color="Color name or hex code (e.g. red, #FF0000)")
    @app_commands.autocomplete(color=color_autocomplete)
    @app_commands.checks.cooldown(1, 3.0)
    async def color(self, interaction: discord.Interaction, x: int, y: int, color: str):
        # Validation checks
        if not (0 <= x < CANVAS_WIDTH) or not (0 <= y < CANVAS_HEIGHT):
            await interaction.response.send_message(
                f"❌ Coordinates must be within 0-{CANVAS_WIDTH - 1} for X and 0-{CANVAS_HEIGHT - 1} for Y.", 
                ephemeral=True
            )
            return
            
        if not is_valid_color(color):
            await interaction.response.send_message(
                f"❌ Invalid color. Use a valid CSS color name (e.g., 'red', 'blue') or Hex Code (e.g., '#FF0000').",
                ephemeral=True
            )
            return
            
        # Blacklist check (do this before deferring to save time)
        if await db.is_blacklisted(interaction.user.id):
            await interaction.response.send_message("❌ **You are blacklisted from using the canvas.**", ephemeral=True)
            return
            
        # Duplicate Pixel Check
        # Convert the passed color to a standard RGB hex to compare accurately against DB
        try:
            r, g, b = ImageColor.getrgb(color)
            hex_color = '#{:02x}{:02x}{:02x}'.format(r, g, b).lower()
            current_db_color = await db.get_current_pixel_color(interaction.guild_id, x, y)
            
            # Compare standard CSS hexes or direct string matches if the original was inserted raw
            if current_db_color:
                try:
                    curr_r, curr_g, curr_b = ImageColor.getrgb(current_db_color)
                    current_db_hex = '#{:02x}{:02x}{:02x}'.format(curr_r, curr_g, curr_b).lower()
                    if hex_color == current_db_hex:
                        await interaction.response.send_message(f"ℹ️ That pixel is already `{color}`!", ephemeral=True)
                        return
                except ValueError:
                    if color.lower() == current_db_color.lower():
                        await interaction.response.send_message(f"ℹ️ That pixel is already `{color}`!", ephemeral=True)
                        return
        except ValueError:
            pass # fallback to full processing if PIL fails parsing strangely

        # Defer the response for stability when DB operations take slightly longer
        await interaction.response.defer()
            
        try:
            # We defer before updating the db
            total_pixels = await db.update_pixel(interaction.guild_id, x, y, color, interaction.user.id)
            await canvas_cache.update_pixel(interaction.guild_id, x, y, color)
            
            # UX Improvement: Make the embed match the requested color
            r, g, b = ImageColor.getrgb(color)
            embed_color = discord.Color.from_rgb(r, g, b)
            
            embed = discord.Embed(
                title="Pixel Updated! 🎨",
                description=f"**{interaction.user.mention}** changed pixel at `({x}, {y})` to `{color}`.",
                color=embed_color
            )
            await interaction.followup.send(embed=embed)
            
            # Milestone Check (Every 10,000 pixels)
            if total_pixels and total_pixels % 10000 == 0:
                await self.broadcast_milestone(interaction, total_pixels)
            
        except Exception as e:
            if "administratively protected" in str(e):
                await interaction.followup.send("🛡️ ❌ This pixel is protected by an admin and cannot be overwritten.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error updating pixel: {str(e)}")

    @app_commands.command(name="undo", description="Undo your last pixel placement (within 5 minutes)")
    @app_commands.checks.cooldown(1, 10.0)
    async def undo(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            # 1. Get the last pixel
            last_record = await db.get_last_user_pixel(interaction.guild_id, interaction.user.id)
            if not last_record:
                await interaction.followup.send("❌ Could not find a recent pixel placement (within the last 5 minutes) to undo.", ephemeral=True)
                return
                
            record_id = last_record['id']
            x = last_record['x']
            y = last_record['y']
            
            # 2. Check if pixel is protected
            protected = await db.pool.fetchval('SELECT is_protected FROM pixels WHERE guild_id = $1 AND x = $2 AND y = $3', interaction.guild_id, x, y)
            if protected:
                await interaction.followup.send("❌ Cannot pull an undo on this pixel, it has since been protected.", ephemeral=True)
                return
            
            # 3. Get the color it was BEFORE this placement
            previous_color = await db.get_previous_pixel_color(interaction.guild_id, x, y, record_id)
            
            # 4. Apply the rollback
            await db.undo_pixel(interaction.guild_id, record_id, x, y, previous_color, interaction.user.id)
            await canvas_cache.update_pixel(interaction.guild_id, x, y, previous_color)
            
            embed = discord.Embed(
                title="↩️ Pixel Undone",
                description=f"Reverted your pixel at `({x}, {y})` back to `{previous_color}`.",
                color=discord.Color.yellow()
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error undoing pixel: {str(e)}")

    async def broadcast_milestone(self, interaction: discord.Interaction, count: int):
        # Look for the log channel to shout out the milestone
        if not interaction.guild:
            return
            
        log_channel_id = await db.get_log_channel(interaction.guild_id)
        if not log_channel_id:
            return
            
        channel = self.bot.get_channel(log_channel_id)
        if not channel:
            return
            
        embed = discord.Embed(
            title="🎊 MAJOR MILESTONE REACHED! 🎊",
            description=f"The community has just placed the **{count:,}th** pixel on the canvas!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Thank you for being part of the masterpiece.")
        await channel.send(content="@everyone", embed=embed)

async def setup(bot):
    await bot.add_cog(ColorCommand(bot))
