import discord
from discord.ext import commands
from discord import app_commands
from database.postgres import db

class ModCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setlogchannel", description="Set the channel where moderation logs will be sent (Admin only)")
    @app_commands.describe(channel="The text channel to send logs to")
    @app_commands.default_permissions(administrator=True)
    async def setlogchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer()
        
        try:
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send("❌ This command can only be used in a server.")
                return
                
            # Verify bot can send messages there
            permissions = channel.permissions_for(interaction.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                await interaction.followup.send("❌ I need 'Send Messages' and 'Embed Links' permissions in that channel.")
                return
                
            await db.set_log_channel(guild_id, channel.id)
            
            embed = discord.Embed(
                title="⚙️ Moderation Channel Set",
                description=f"Action logs like `/reset` and `/protect` will now be sent to {channel.mention}.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error setting log channel: {str(e)}")

    @app_commands.command(name="blacklist", description="Ban a user from interacting with the canvas (Admin only)")
    @app_commands.describe(user="The user to ban")
    @app_commands.default_permissions(administrator=True)
    async def blacklist(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer()
        try:
            await db.ban_user(user.id)
            embed = discord.Embed(
                title="⛔ User Blacklisted",
                description=f"{user.mention} has been banned from placing pixels.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            
            # Log it
            if interaction.guild_id:
                log_channel_id = await db.get_log_channel(interaction.guild_id)
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="⛔ Admin Action: User Blacklisted",
                            description=f"**Admin:** {interaction.user.mention}\n**Target:** {user.mention}",
                            color=discord.Color.brand_red()
                        )
                        await log_channel.send(embed=log_embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error blacklisting user: {str(e)}")

    @app_commands.command(name="unblacklist", description="Unban a user from the canvas (Admin only)")
    @app_commands.describe(user="The user to unban")
    @app_commands.default_permissions(administrator=True)
    async def unblacklist(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer()
        try:
            await db.unban_user(user.id)
            embed = discord.Embed(
                title="✅ User Unblacklisted",
                description=f"{user.mention} can now interact with the canvas again.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            
            # Log it
            if interaction.guild_id:
                log_channel_id = await db.get_log_channel(interaction.guild_id)
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_embed = discord.Embed(
                            title="✅ Admin Action: User Unblacklisted",
                            description=f"**Admin:** {interaction.user.mention}\n**Target:** {user.mention}",
                            color=discord.Color.green()
                        )
                        await log_channel.send(embed=log_embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error unblacklisting user: {str(e)}")

async def setup(bot):
    await bot.add_cog(ModCommand(bot))
