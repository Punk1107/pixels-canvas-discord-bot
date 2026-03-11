import discord
from discord.ext import commands
from discord import app_commands
from database.postgres import db
import time

class LeaderboardCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cache_time = 0
        self._cached_users = None
        self._cache_ttl = 60 # 60 seconds

    @app_commands.command(name="leaderboard", description="Show the top pixel contributors")
    @app_commands.checks.cooldown(1, 10.0)
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            current_time = time.time()
            if self._cached_users and (current_time - self._cache_time) < self._cache_ttl:
                top_users = self._cached_users
            else:
                top_users = await db.get_top_users(10)
                self._cached_users = top_users
                self._cache_time = current_time
            
            if not top_users:
                embed = discord.Embed(
                    title="🏆 Pixel Canvas Leaderboard",
                    description="No pixels have been placed yet! Be the first!",
                    color=discord.Color.gold()
                )
                await interaction.followup.send(embed=embed)
                return
                
            embed = discord.Embed(title="🏆 Pixel Canvas Leaderboard", color=discord.Color.gold())
            
            medals = ["🥇", "🥈", "🥉"]
            
            for i, record in enumerate(top_users):
                user_id = record['user_id']
                pixels_drawn = record['pixels_drawn']
                
                # Retrieve from cache or fallback
                user = self.bot.get_user(user_id)
                if not user:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        user = None
                user_name = user.name if user else f"Unknown User ({user_id})"
                
                prefix = medals[i] if i < len(medals) else f"#{i+1}"
                
                embed.add_field(name=f"{prefix} {user_name}", value=f"`{pixels_drawn}` pixels drawn", inline=False)
                
            embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching leaderboard: {str(e)}")

    @app_commands.command(name="local_board", description="View the top 10 pixel contributors in this specific server")
    async def local_board(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used inside a server.")
            return
            
        try:
            # We fetch a large chunk of global stats, but filter natively to matching guild members
            top_users = await db.get_top_users(1000) 
            
            # Filter locally 
            local_members = []
            for record in top_users:
                member = interaction.guild.get_member(record['user_id'])
                if member:
                    local_members.append({"name": member.display_name, "pixels": record['pixels_drawn']})
                if len(local_members) >= 10:
                    break
                    
            if not local_members:
                await interaction.followup.send("📊 Nobody in this server has placed any pixels yet!")
                return
                
            embed = discord.Embed(
                title=f"🏆 Local Leaderboard: {interaction.guild.name}",
                description="Top 10 contributors from this server:",
                color=discord.Color.gold()
            )
            
            medals = ["🥇", "🥈", "🥉"]
            for i, user in enumerate(local_members):
                prefix = medals[i] if i < len(medals) else f"#{i+1}"
                
                embed.add_field(
                    name=f"{prefix} {user['name']}",
                    value=f"`{user['pixels']:,}` pixels",
                    inline=False
                )
                
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching local leaderboard: {str(e)}")

async def setup(bot):
    await bot.add_cog(LeaderboardCommand(bot))
