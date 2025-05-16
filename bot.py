import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
from config import Config
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Validation du token
if not DISCORD_BOT_TOKEN:
    raise ValueError("Le token Discord n'est pas défini dans le fichier .env")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

async def load_extensions():
    extensions = ["commands.reservation", "commands.utility"]
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            logger.info(f"Extension {ext} chargée avec succès.")
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'extension {ext} : {e}")

@bot.event
async def on_ready():
    logger.info(f"Connecté en tant que {bot.user}")
    await bot.change_presence(activity=discord.Game(name="Team Fortress 2"))
    
    bot.remove_command("help")
    await load_extensions()

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    if bot.user in message.mentions:
        embed = discord.Embed(
            title="📋 Aide du Bot",
            description=Config.HELP_TEXT,
            color=discord.Color.blue()
        )
        await message.channel.send(embed=embed)
    
    await bot.process_commands(message)

bot.run(DISCORD_BOT_TOKEN)
