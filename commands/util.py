import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageColor
import io

class UtilCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show information and commands for the Pixel Canvas Bot")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎨 Pixel Canvas Help",
            description="Welcome to the Pixel Canvas! Collaborate with others to draw art one pixel at a time.",
            color=discord.Color.blurple()
        )
        embed.add_field(name="🖌️ /color <x> <y> <color>", value="Place a pixel at the coordinates. Type color to see suggestions.", inline=False)
        embed.add_field(name="🖼️ /canvas", value="View the entire canvas as an image.", inline=False)
        embed.add_field(name="🔍 /view <x> <y> <radius>", value="View a zoomed-in section of the canvas.", inline=False)
        embed.add_field(name="⏳ /timelapse", value="Generate an animated GIF of the canvas history.", inline=False)
        embed.add_field(name="↩️ /undo", value="Undo your last pixel placement (within 5 minutes).", inline=False)
        embed.add_field(name="ℹ️ /info <x> <y>", value="See who placed a specific pixel.", inline=False)
        embed.add_field(name="📊 /stats [user]", value="Check a user's total pixels drawn and global rank.", inline=False)
        embed.add_field(name="🏆 /leaderboard", value="View the top 10 pixel contributors.", inline=False)
        embed.add_field(name="🎨 /palette", value="See a visual swatch of all basic supported colors.", inline=False)
        
        # Admin section
        if interaction.user.guild_permissions.administrator:
            embed.add_field(name="🛡️ Admin Commands", value="`/protect`, `/unprotect`, `/reset`, `/setlogchannel`, `/blacklist`, `/unblacklist`", inline=False)
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="palette", description="See a visual swatch of common colors")
    async def palette(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        colors = ['red', 'blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'brown', 'black', 'white', 
                  'cyan', 'magenta', 'lime', 'teal', 'navy', 'maroon', 'olive', 'silver', 'gray']
                  
        box_size = 50
        columns = 5
        rows = (len(colors) + columns - 1) // columns
        
        img = Image.new('RGB', (columns * box_size, rows * box_size), color='white')
        draw = ImageDraw.Draw(img)
        
        for i, color_name in enumerate(colors):
            x = (i % columns) * box_size
            y = (i // columns) * box_size
            rgb = ImageColor.getrgb(color_name)
            draw.rectangle([x, y, x + box_size, y + box_size], fill=rgb)
            # Outline
            draw.rectangle([x, y, x + box_size, y + box_size], outline='black', width=1)
            
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        file = discord.File(fp=buffer, filename="palette.png")
        embed = discord.Embed(
            title="🎨 Color Palette",
            description="Use these names in the `/color` command, or use standard Hex Codes (`#FF0000`).",
            color=discord.Color.blurple()
        )
        embed.set_image(url="attachment://palette.png")
        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(name="cooldown", description="Check how long until you can draw another pixel")
    async def cooldown_check(self, interaction: discord.Interaction):
        # We find the color command in the bot's tree to check its exact cooldown state
        color_cmd = self.bot.tree.get_command('color')
        if not color_cmd:
            await interaction.response.send_message("❌ Command not found.", ephemeral=True)
            return
            
        # Get the cooldown wait time 
        retry_after = color_cmd._buckets.get_bucket(interaction).get_retry_after()
        if retry_after:
            await interaction.response.send_message(f"⏳ You must wait **{retry_after:.1f} more seconds** before placing another pixel.", ephemeral=True)
        else:
            await interaction.response.send_message("✅ You are ready! You can place a pixel right now.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(UtilCommand(bot))
