import discord
from discord.ext import commands
from discord import app_commands
from database.postgres import db

class FactionsCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="join_faction", description="Join a faction to compete on the leaderboard")
    @app_commands.describe(name="The name of the faction to join")
    async def join_faction(self, interaction: discord.Interaction, name: str):
        if len(name) > 30:
            await interaction.response.send_message("❌ Faction name cannot exceed 30 characters.", ephemeral=True)
            return
            
        try:
            await db.join_faction(interaction.user.id, name)
            await interaction.response.send_message(f"✅ You have successfully joined the **{name}** faction!")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error joining faction: {str(e)}", ephemeral=True)

    @app_commands.command(name="leave_faction", description="Leave your current faction")
    async def leave_faction(self, interaction: discord.Interaction):
        try:
            await db.leave_faction(interaction.user.id)
            await interaction.response.send_message("👋 You have left your faction.")
        except Exception as e:
            await interaction.response.send_message(f"❌ Error leaving faction: {str(e)}", ephemeral=True)

    @app_commands.command(name="faction_board", description="View the top factions by total pixels placed")
    async def faction_board(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            top_factions = await db.get_faction_leaderboard(10)
            
            if not top_factions:
                await interaction.followup.send("🏁 No factions have been formed yet!")
                return
                
            embed = discord.Embed(
                title="🏁 Faction Leaderboard",
                description="Total pixels placed collectively by all faction members:",
                color=discord.Color.blue()
            )
            
            medals = ["🥇", "🥈", "🥉"]
            for i, record in enumerate(top_factions):
                name = record['faction_name']
                pixels = record['total_pixels']
                prefix = medals[i] if i < len(medals) else f"#{i+1}"
                
                embed.add_field(
                    name=f"{prefix} {name}",
                    value=f"`{pixels:,}` pixels placed",
                    inline=False
                )
                
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching faction leaderboard: {str(e)}")

async def setup(bot):
    await bot.add_cog(FactionsCommand(bot))
