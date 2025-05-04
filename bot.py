import discord
from discord.ext import commands
from utils import find_servers, create_reservation, end_reservation
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import asyncio
import difflib  # Pour suggérer des commandes similaires
import re  # Pour supprimer les parenthèses

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Activer les intents nécessaires
intents = discord.Intents.default()
intents.message_content = True  # Pour les commandes basées sur les messages
intents.presences = True  # Pour gérer la présence (Rich Presence)

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)  # Disable default help command

user_data = {}  # Stocke temporairement les infos utilisateur

def clean_server_name(name):
    """Remove any text in parentheses from server names."""
    # Supprimer tout texte entre parenthèses
    name = re.sub(r'\([^)]*\)', '', name)
    # Supprimer les espaces en trop
    return name.strip()

# Configurer la Rich Presence au démarrage
@bot.event
async def on_ready():
    print(f'Connecté en tant que {bot.user}')
    # Définir l'activité Rich Presence
    activity = discord.Activity(
        type=discord.ActivityType.playing,  # Type "Playing"
        name="Team Fortress 2",  # Nom de l'application (optionnel, pour contexte)
        state="Playing 6s",  # État (bas de la Rich Presence)
        details="Competitive",  # Détails (haut de la Rich Presence)
        assets={
            "large_image": "icon",  # Image principale
            "large_text": "Numbani",  # Texte au survol de l'image principale
            "small_image": "icon",  # Image secondaire
            "small_text": "ETF2L 6v6"  # Texte au survol de l'image secondaire
        }
    )
    await bot.change_presence(activity=activity)
    print("Rich Presence mise à jour")

# Gérer les erreurs de commande
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        # Récupérer la commande saisie
        command_name = ctx.message.content[len(ctx.prefix):].split()[0]
        # Liste des commandes disponibles
        available_commands = [cmd.name for cmd in bot.commands]
        # Trouver des suggestions proches
        suggestions = difflib.get_close_matches(command_name, available_commands, n=1, cutoff=0.6)
        if suggestions:
            await ctx.send(f"Commande `{command_name}` introuvable. Voulez-vous dire `!{suggestions[0]}` ?")
        return  # Ignorer silencieusement si aucune suggestion
    elif isinstance(error, commands.MissingRequiredArgument):
        # Gérer les arguments manquants
        if ctx.command.name == "reserve":
            await ctx.send("Erreur : il manque l'heure de début. Utilisez `!reserve <heure>` (ex: `!reserve 20h00`).")
        elif ctx.command.name == "confirm":
            await ctx.send("Erreur : il manque des arguments. Utilisez `!confirm <server_id> <password>` (ex: `!confirm 12345 mypassword`).")
        else:
            await ctx.send(f"Erreur : argument manquant pour `{ctx.command.name}`. Vérifiez avec `!help`.")
        return
    # Laisser les autres erreurs remonter pour le débogage
    raise error

# Gérer les erreurs des slash commands
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CommandNotFound):
        await interaction.response.send_message(
            "Ce bot utilise les commandes avec `!` (ex: `!reserve 20h00`). Les slash commands (`/`) ne sont pas supportées.",
            ephemeral=True
        )
    else:
        # Laisser les autres erreurs remonter pour le débogage
        raise error

@bot.command(name="help")
async def help_command(ctx):
    """
    Affiche l'aide pour les commandes du bot.
    """
    help_text = (
        "**Aide pour les commandes du bot :**\n\n"
        "**!reserve <heure>**\n"
        "- Réserve un serveur à partir de l'heure indiquée (format HHhMM, ex: 20h00) pour aujourd'hui à Paris.\n"
        "- Durée par défaut : 2 heures.\n"
        "- Exemple : `!reserve 20h00`\n\n"
        "**!showmore**\n"
        "- Affiche la liste complète des serveurs disponibles après une réservation.\n"
        "- Exemple : `!showmore`\n\n"
        "**!confirm <server_id> <password>**\n"
        "- Confirme une réservation avec l'ID du serveur et un mot de passe.\n"
        "- Le RCON est demandé en message privé si non fourni.\n"
        "- Fournit les détails de connexion (connect) dans le canal et RCON (rcon_address) en message privé.\n"
        "- Exemple : `!confirm 12345 mypassword`\n\n"
        "**!end**\n"
        "- Termine une réservation active.\n"
        "- Exemple : `!end`\n\n"
        "**Notes**:\n"
        "- Les heures sont basées sur le fuseau horaire de Paris (Europe/Paris).\n"
        "- Assure-toi que les messages privés du bot sont activés pour fournir/recevoir le RCON.\n"
        "- Utilise `!help` pour revoir cette aide."
    )
    await ctx.send(help_text)

@bot.command(name="reserve")
async def reserve(ctx, start_time: str = None):
    """
    Réserve un serveur pour une période donnée.
    Format de l'heure : HHhMM (ex: 20h00) pour aujourd'hui à Paris.
    Exemple : !reserve 20h00
    """
    if not start_time:
        await ctx.send("Erreur : veuillez fournir une heure de début.\nExemple : `!reserve 20h00`")
        return

    # Parse start_time (HHhMM format)
    try:
        time_obj = datetime.strptime(start_time, "%Hh%M")
    except ValueError:
        await ctx.send("Erreur : format d'heure invalide. Utilise HHhMM, ex: `20h00`.")
        return

    # Get current date in Paris timezone
    paris_tz = pytz.timezone("Europe/Paris")
    now = datetime.now(paris_tz)

    # Set start_time to today at the specified hour/minute
    start_dt = now.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)

    # If time is in the past, assume it's for the next day
    if start_dt < now:
        start_dt += timedelta(days=1)

    # Set end_time to 2 hours later
    end_dt = start_dt + timedelta(hours=2)

    # Format times in ISO 8601 for the API
    start_time_iso = start_dt.isoformat()
    end_time_iso = end_dt.isoformat()

    await ctx.send(f"Recherche de serveurs disponibles pour {start_dt.strftime('%Y-%m-%d %H:%M')} à {end_dt.strftime('%H:%M')} (Paris)...")
    data = await find_servers(start_time_iso, end_time_iso)

    servers = data.get("servers", [])
    server_configs = data.get("server_configs", [])  # Récupérer les server_configs
    if not servers:
        await ctx.send("Aucun serveur disponible.")
        return

    # Trouver l'ID de etf2l_6v6_5cp
    server_config_id = None
    for config in server_configs:
        if config.get("file") == "etf2l_6v6_5cp":
            server_config_id = config.get("id")
            break

    # Group servers by prefix (e.g., NewBrigade, ElzasBrigade)
    server_groups = {}
    for s in servers:
        # Extract group name (e.g., "NewBrigade" from "NewBrigade #1")
        group_name = s['name'].split('#')[0].strip()
        if group_name not in server_groups:
            server_groups[group_name] = []
        server_groups[group_name].append(s)

    # Select up to 3 servers per group
    limited_servers = []
    for group in server_groups:
        server_groups[group].sort(key=lambda x: x['id'])  # Sort by ID for consistency
        limited_servers.extend(server_groups[group][:3])  # Take first 3 servers

    # Build server list and split if too long
    messages = []
    current_msg = "**Serveurs disponibles :**\n"
    char_limit = 1900  # Leave buffer below 2000 chars
    for s in limited_servers:
        location = s.get('location', {}).get('name', 'Inconnu')
        if 'Inconnu' in location:
            location = ''
        server_line = f"`{s['id']}`: {clean_server_name(s['name'])} ({location})\n"
        if len(current_msg) + len(server_line) > char_limit:
            messages.append(current_msg)
            current_msg = "**Serveurs disponibles (suite) :**\n"
        current_msg += server_line

    # Append the last message if it has content
    if current_msg.strip() != "**Serveurs disponibles (suite) :**":
        messages.append(current_msg)

    # Send all messages
    for msg in messages:
        await ctx.send(msg)

    # Store all servers and configs in user_data for confirm and showmore commands
    user_data[ctx.author.id] = {
        "start": start_time_iso,
        "end": end_time_iso,
        "available_servers": servers,
        "server_configs": server_configs,
        "server_config_id": server_config_id
    }

    await ctx.send("Utilise `!confirm <server_id> <password>` pour réserver.\n*Note : utilise `!showmore` pour voir la liste complète des serveurs.*")

@bot.command(name="showmore")
async def showmore(ctx):
    """
    Affiche la liste complète des serveurs disponibles après une réservation.
    Exemple : !showmore
    """
    data = user_data.get(ctx.author.id)
    if not data or "available_servers" not in data:
        await ctx.send("Aucune réservation en attente. Utilise `!reserve` d'abord.")
        return

    servers = data["available_servers"]
    if not servers:
        await ctx.send("Aucun serveur disponible.")
        return

    # Build server list and split if too long
    messages = []
    current_msg = "**Liste complète des serveurs disponibles :**\n"
    char_limit = 1900  # Leave buffer below 2000 chars
    for s in servers:
        location = s.get('location', {}).get('name', 'Inconnu')
        if 'Inconnu' in location:
            location = ''
        server_line = f"`{s['id']}`: {clean_server_name(s['name'])} ({location})\n"
        if len(current_msg) + len(server_line) > char_limit:
            messages.append(current_msg)
            current_msg = "**Liste complète des serveurs (suite) :**\n"
        current_msg += server_line

    # Append the last message if it has content
    if current_msg.strip() != "**Liste complète des serveurs (suite) :**":
        messages.append(current_msg)

    # Send all messages
    for msg in messages:
        await ctx.send(msg)

@bot.command(name="confirm")
async def confirm(ctx, server_id: int, password: str, rcon: str = None):
    """
    Confirme la réservation d'un serveur.
    Exemple : !confirm 12345 mypassword
    """
    data = user_data.get(ctx.author.id)
    if not data:
        await ctx.send("Aucune réservation en attente. Utilise `!reserve` d'abord.")
        return

    if rcon is None:
        try:
            await ctx.author.send("Veuillez fournir le mot de passe RCON pour votre réservation.")
        except discord.Forbidden:
            await ctx.send("❌ Impossible d'envoyer un message privé pour demander le RCON. Vérifie que tes DMs sont ouverts pour le bot ou utilise `!confirm <server_id> <password> <rcon>`.")
            return

        def check(m):
            return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)

        try:
            response = await bot.wait_for('message', check=check, timeout=60.0)
            rcon = response.content.strip()
            if not rcon:
                await ctx.author.send("Erreur : aucun RCON fourni. Réessaie avec `!confirm <server_id> <password>`.")
                await ctx.send("❌ Réservation annulée : aucun RCON fourni dans les 60 secondes.")
                return
        except asyncio.TimeoutError:
            await ctx.author.send("Erreur : temps écoulé pour fournir le RCON. Réessaie avec `!confirm <server_id> <password>`.")
            await ctx.send("❌ Réservation annulée : temps écoulé pour fournir le RCON.")
            return
        except discord.Forbidden:
            await ctx.send("❌ Impossible de recevoir ton RCON en message privé. Vérifie que tes DMs sont ouverts pour le bot ou utilise `!confirm <server_id> <password> <rcon>`.")
            return

    # Récupérer server_config_id depuis user_data
    server_config_id = data.get("server_config_id")
    reservation, status = await create_reservation(
        data["start"], data["end"], server_id, password, rcon, server_config_id
    )
    if status == 200:
        res = reservation["reservation"]
        public_info = (
            f"✅ Réservation confirmée sur **{clean_server_name(res['server']['name'])}**\n"
            f"**Connect info :**\n"
            f"```\nconnect {res['server']['ip_and_port']}; password \"{res['password']}\"\n```\n"
            f"RCON details sent via private message."
        )
        rcon_info = (
            f"**RCON for {clean_server_name(res['server']['name'])} :**\n"
            f"```\nrcon_address {res['server']['ip_and_port']}; rcon_password \"{rcon}\"\n```"
        )
        await ctx.send(public_info)
        try:
            await ctx.author.send(rcon_info)
        except discord.Forbidden:
            await ctx.send("❌ Impossible d'envoyer les détails RCON en message privé. Vérifie que tes DMs sont ouverts pour le bot.")
        user_data[ctx.author.id]["reservation_id"] = res["id"]
        user_data[ctx.author.id]["rcon"] = rcon  # Store RCON for potential future use
    else:
        await ctx.send("❌ Erreur lors de la création de la réservation.")
        await ctx.send(str(reservation.get("reservation", {}).get("errors", {})))

@bot.command(name="end")
async def end(ctx):
    """
    Termine une réservation active.
    Exemple : !end
    """
    data = user_data.get(ctx.author.id)
    if not data or "reservation_id" not in data:
        await ctx.send("Aucune réservation à terminer.")
        return

    res_id = data["reservation_id"]
    response, status = await end_reservation(res_id)
    if status == 200 or status == 204:
        await ctx.send(f"✅ Réservation terminée (ID {res_id})")
        del user_data[ctx.author.id]
    else:
        await ctx.send("❌ Impossible de terminer la réservation.")
        await ctx.send(response)

bot.run(TOKEN)
