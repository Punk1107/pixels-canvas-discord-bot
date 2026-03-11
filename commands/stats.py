import discord
from discord.ext import commands
from discord import app_commands
from database.postgres import db

class StatsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="info", description="Get info about a specific pixel")
    @app_commands.describe(x="X coordinate", y="Y coordinate")
    @app_commands.checks.cooldown(1, 3.0)
    async def info(self, interaction: discord.Interaction, x: int, y: int):
        await interaction.response.defer()
        
        try:
            record = await db.get_pixel_info(x, y)
            if not record:
                await interaction.followup.send(f"🏳️ No pixel has ever been placed at `({x}, {y})`.")
                return
                
            user_id = record['user_id']
            color = record['color']
            created_at = record['created_at']
            
            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except discord.NotFound:
                    user = None
            user_name = user.name if user else f"Unknown User ({user_id})"
            
            embed = discord.Embed(
                title=f"Pixel Info ({x}, {y})",
                color=discord.Color.blue()
            )
            embed.add_field(name="Color", value=f"`{color}`", inline=True)
            embed.add_field(name="Placed By", value=user_name, inline=True)
            embed.add_field(name="Placed At", value=created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), inline=False)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error retrieving pixel info: {str(e)}")

    @app_commands.command(name="stats", description="Check pixel placement stats for a user")
    @app_commands.describe(user="The user to check stats for (defaults to you)")
    @app_commands.checks.cooldown(1, 5.0)
    async def stats(self, interaction: discord.Interaction, user: discord.Member = None):
        await interaction.response.defer()
        
        target_user = user or interaction.user
        
        try:
            record = await db.get_user_stats(target_user.id)
            if not record:
                embed = discord.Embed(
                    title=f"📊 Stats for {target_user.name}",
                    description="This user hasn't placed any pixels yet.",
                    color=discord.Color.light_grey()
                )
                await interaction.followup.send(embed=embed)
                return
                
            pixels_drawn = record['pixels_drawn']
            rank = record['rank']
            
            embed = discord.Embed(
                title=f"📊 Stats for {target_user.name}",
                color=target_user.color
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.add_field(name="Pixels Placed", value=f"`{pixels_drawn}`", inline=True)
            embed.add_field(name="Global Rank", value=f"`#{rank}`", inline=True)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching stats: {str(e)}")

async def setup(bot):
    await bot.add_cog(StatsCommand(bot))
