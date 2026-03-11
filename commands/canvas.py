import discord
from discord.ext import commands
from discord import app_commands
from database.postgres import db
from canvas.renderer import canvas_cache

class CanvasCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="canvas", description="Display the current canvas")
    @app_commands.checks.cooldown(1, 5.0)
    async def canvas(self, interaction: discord.Interaction):
        # We process from the in-memory cache directly!
        await interaction.response.defer()
        
        try:
            image_buffer = await canvas_cache.get_image_bytes(interaction.guild_id)
            
            file = discord.File(fp=image_buffer, filename="canvas.png")
            
            embed = discord.Embed(
                title="🖼️ Pixel Canvas",
                description="Current canvas state.",
                color=discord.Color.blurple()
            )
            embed.set_image(url="attachment://canvas.png")
            embed.set_footer(text=f"Requested by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(f"❌ Error rendering canvas: {str(e)}")

    @app_commands.command(name="reset", description="Reset the entire canvas (Admin only)")
    @app_commands.describe(hard="Whether to completely wipe pixel history and stats as well")
    @app_commands.default_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction, hard: bool = False):
        await interaction.response.defer()
        try:
            await db.reset_canvas(interaction.guild_id, hard)
            await canvas_cache.reset(interaction.guild_id)
            
            desc = "The canvas has been completely wiped (hard reset)." if hard else "The canvas has been cleared."
            embed = discord.Embed(
                title="🧹 Canvas Reset",
                description=desc,
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            
            # Send Mod Log
            if interaction.guild_id:
                log_channel_id = await db.get_log_channel(interaction.guild_id)
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="🧹 Admin Action: Canvas Reset",
                            description=f"**Admin:** {interaction.user.mention}\n**Type:** `{'Hard Reset' if hard else 'Soft Clear'}`\n**Channel:** {interaction.channel.mention}",
                            color=discord.Color.dark_red()
                        )
                        await log_channel.send(embed=log_embed)
                        
        except Exception as e:
            await interaction.followup.send(f"❌ Error resetting canvas: {str(e)}")

    @app_commands.command(name="view", description="View a zoomed section of the canvas")
    @app_commands.describe(
        x="X coordinate to center the view on",
        y="Y coordinate to center the view on",
        radius="Radius of the zoomed view (max 20)"
    )
    @app_commands.checks.cooldown(1, 3.0)
    async def view(self, interaction: discord.Interaction, x: int, y: int, radius: int = 5):
        await interaction.response.defer()
        
        radius = min(max(1, radius), 20)
        
        try:
            image_buffer = await canvas_cache.get_zoomed_image_bytes(interaction.guild_id, x, y, radius)
            
            file = discord.File(fp=image_buffer, filename="view.png")
            
            embed = discord.Embed(
                title=f"🔍 Zoomed Canvas: ({x}, {y})",
                description=f"Showing a {radius} radius around the center.",
                color=discord.Color.blurple()
            )
            embed.set_image(url="attachment://view.png")
            embed.set_footer(text=f"Requested by {interaction.user.name}")
            
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(f"❌ Error rendering view: {str(e)}")

    @app_commands.command(name="timelapse", description="Generate a GIF timelapse of the canvas history")
    @app_commands.checks.cooldown(1, 60.0) # 1 min cooldown due to heavy process
    async def timelapse(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            await interaction.followup.send("⏳ Generating timelapse... this might take a moment!")
            
            history_data = await db.get_pixel_history_stream(interaction.guild_id)
            if not history_data:
                await interaction.channel.send("No pixels have been drawn yet!")
                return
                
            gif_buffer = await canvas_cache.generate_timelapse_gif(interaction.guild_id, history_data)
            file = discord.File(fp=gif_buffer, filename="timelapse.gif")
            
            embed = discord.Embed(
                title="⏳ Canvas Timelapse",
                description="The entire history of the pixel canvas!",
                color=discord.Color.magenta()
            )
            embed.set_image(url="attachment://timelapse.gif")
            
            await interaction.channel.send(embed=embed, file=file)
        except Exception as e:
            await interaction.channel.send(f"❌ Error generating timelapse: {str(e)}")

async def setup(bot):
    await bot.add_cog(CanvasCommand(bot))
