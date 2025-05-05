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

user_data = {}  # Stocke les réservations par utilisateur {user_id: [{"reservation_id": id, "start": start, ...}, ...]}

def clean_server_name(name):
    """Remove any text in parentheses from server names."""
    name = re.sub(r'\([^)]*\)', '', name)
    return name.strip()

# Configurer la Rich Presence au démarrage
@bot.event
async def on_ready():
    print(f'Connecté en tant que {bot.user}')
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name="!help",
        state="Playing 6s on serveme.tf",
        details="Competitive"
    )
    await bot.change_presence(activity=activity)
    print("Rich Presence mise à jour")

# Gérer les erreurs de commande
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        command_name = ctx.message.content[len(ctx.prefix):].split()[0]
        available_commands = [cmd.name for cmd in bot.commands]
        suggestions = difflib.get_close_matches(command_name, available_commands, n=1, cutoff=0.6)
        if suggestions:
            await ctx.send(f"Commande `{command_name}` introuvable. Voulez-vous dire `!{suggestions[0]}` ?")
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        if ctx.command.name == "reserve":
            await ctx.send("Erreur : il manque l'heure de début. Utilisez `!reserve <heure>` (ex: `!reserve 20h00`) ou `!reserve <date> <heure>` (ex: `!reserve 2025-05-05 20h00`).")
        elif ctx.command.name == "fastr":
            await ctx.send("Erreur : il manque l'heure de début. Utilisez `!fastr now|<heure> [password] [rcon]` (ex: `!fastr now`, `!fastr 20h00`, or `!fastr 20h00 mypass myrcon`).")
        elif ctx.command.name == "confirm":
            await ctx.send("Erreur : il manque des arguments. Utilisez `!confirm <server_id> <password>` (ex: `!confirm 12345 mypassword`).")
        else:
            await ctx.send(f"Erreur : argument manquant pour `{ctx.command.name}`. Vérifiez avec `!help`.")
        return
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
        raise error

@bot.command(name="help")
async def help_command(ctx):
    """
    Affiche l'aide pour les commandes du bot.
    """
    help_text = (
        "**Aide pour les commandes du bot :**\n\n"
        "**!reserve [<date>] <heure>**\n"
        "- Réserve un serveur pour 2 heures.\n"
        "- Exemples : `!reserve 20h00` (aujourd'hui ou demain si l'heure est passée)\n"
        "             `!reserve 2025-05-05 20h00` (date spécifique)\n\n"
        "**!fastr now|<heure> [password] [rcon]**\n"
        "- Réserve rapidement un serveur ElzasBrigade pour 2 heures.\n"
        "- Utilise `now` pour un démarrage immédiat.\n"
        "- Exemples : `!fastr now` (démarrage immédiat, valeurs par défaut)\n"
        "             `!fastr 20h00` (démarre à 20h00)\n"
        "             `!fastr now mypass myrcon` (démarrage immédiat, mot de passe et RCON spécifiés)\n\n"
        "**!confirm <server_id> <password>**\n"
        "- Confirme une réservation avec l'ID du serveur et un mot de passe.\n"
        "- Le RCON est demandé en message privé si non fourni.\n"
        "- Exemple : `!confirm 12345 mypassword`\n\n"
        "**!list**\n"
        "- Affiche la liste de tes réservations actives.\n"
        "- Exemple : `!list`\n\n"
        "**!end [<reservation_id>]**\n"
        "- Termine une réservation active. Si plusieurs réservations, spécifie l'ID.\n"
        "- Exemples : `!end` (termine la dernière réservation)\n"
        "             `!end 12345` (termine une réservation spécifique)\n\n"
        "**Notes**:\n"
        "- Les heures sont basées sur le fuseau horaire de Paris (Europe/Paris).\n"
        "- Assure-toi que les messages privés du bot sont activés pour fournir/recevoir le RCON.\n"
        "- Utilise `!help` pour revoir cette aide."
    )
    await ctx.send(help_text)

@bot.command(name="reserve")
async def reserve(ctx, *, args: str = None):
    """
    Réserve un serveur pour une période donnée.
    Format : !reserve [<date>] <heure>
    """
    if not args:
        await ctx.send("Erreur : veuillez fournir une heure de début.\nExemple : `!reserve 20h00` ou `!reserve 2025-05-05 20h00`")
        return

    parts = args.split()
    date_str = None
    time_str = parts[-1]

    if len(parts) > 1:
        if re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
            date_str = parts[0]

    try:
        time_obj = datetime.strptime(time_str, "%Hh%M")
    except ValueError:
        await ctx.send("Erreur : format d'heure invalide. Utilise HHhMM, ex: `20h00`.")
        return

    paris_tz = pytz.timezone("Europe/Paris")
    now = datetime.now(paris_tz)

    if date_str:
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            start_dt = date_obj.replace(
                hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0, tzinfo=paris_tz
            )
        except ValueError:
            await ctx.send("Erreur : format de date invalide. Utilise YYYY-MM-DD, ex: `2025-05-05`.")
            return
    else:
        start_dt = now.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)
        if start_dt < now:
            start_dt += timedelta(days=1)

    end_dt = start_dt + timedelta(hours=2)
    start_time_iso = start_dt.isoformat()
    end_time_iso = end_dt.isoformat()

    await ctx.send(f"Recherche de serveurs disponibles pour {start_dt.strftime('%Y-%m-%d %H:%M')} à {end_dt.strftime('%H:%M')} ...")
    data = await find_servers(start_time_iso, end_time_iso)

    servers = data.get("servers", [])
    server_configs = data.get("server_configs", [])
    if not servers:
        await ctx.send("Aucun serveur disponible.")
        return

    server_config_id = None
    for config in server_configs:
        if config.get("file") == "etf2l_6v6_5cp":
            server_config_id = config.get("id")
            break

    server_groups = {}
    for s in servers:
        group_name = s['name'].split('#')[0].strip()
        if group_name not in server_groups:
            server_groups[group_name] = []
        server_groups[group_name].append(s)

    limited_servers = []
    for group in server_groups:
        server_groups[group].sort(key=lambda x: x['id'])
        limited_servers.extend(server_groups[group][:3])

    messages = []
    current_msg = "**Serveurs disponibles :**\n"
    char_limit = 1900
    for s in limited_servers:
        location = s.get('location', {}).get('name', 'Inconnu')
        if 'Inconnu' in location:
            location = ''
        server_line = f"`{s['id']}`: {clean_server_name(s['name'])} ({location})\n"
        if len(current_msg) + len(server_line) > char_limit:
            messages.append(current_msg)
            current_msg = "**Serveurs disponibles (suite) :**\n"
        current_msg += server_line

    if current_msg.strip() != "**Serveurs disponibles (suite) :**":
        messages.append(current_msg)

    for msg in messages:
        await ctx.send(msg)

    if ctx.author.id not in user_data:
        user_data[ctx.author.id] = []

    user_data[ctx.author.id].append({
        "start": start_time_iso,
        "end": end_time_iso,
        "available_servers": servers,
        "server_configs": server_configs,
        "server_config_id": server_config_id
    })

    await ctx.send("Utilise `!confirm <server_id> <password>` pour réserver.")

@bot.command(name="fastr")
async def fastr(ctx, time_str: str, password: str = "fish", rcon: str = "fishrcon"):
    """
    Réserve rapidement un serveur ElzasBrigade avec mot de passe et RCON spécifiés ou par défaut.
    Format : !fastr now|<heure> [password] [rcon]
    Exemples : !fastr now (démarrage immédiat)
               !fastr 20h00 (démarre à 20h00)
               !fastr now mypass myrcon (démarrage immédiat avec mot de passe et RCON)
    """
    paris_tz = pytz.timezone("Europe/Paris")
    now = datetime.now(paris_tz)

    if time_str.lower() == "now":
        start_dt = now + timedelta(minutes=1)
    else:
        try:
            time_obj = datetime.strptime(time_str, "%Hh%M")
            start_dt = now.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)
            if start_dt < now:
                start_dt += timedelta(days=1)
        except ValueError:
            await ctx.send("Erreur : format d'heure invalide. Utilise 'now' ou HHhMM, ex: `20h00`.")
            return

    end_dt = start_dt + timedelta(hours=2)
    start_time_iso = start_dt.isoformat()
    end_time_iso = end_dt.isoformat()

    await ctx.send(f"Recherche d'un serveur ElzasBrigade pour {start_dt.strftime('%Y-%m-%d %H:%M')} à {end_dt.strftime('%H:%M')} ...")
    data = await find_servers(start_time_iso, end_time_iso)

    servers = data.get("servers", [])
    server_configs = data.get("server_configs", [])
    if not servers:
        await ctx.send("Aucun serveur disponible.")
        return

    server_config_id = None
    for config in server_configs:
        if config.get("file") == "etf2l_6v6_5cp":
            server_config_id = config.get("id")
            break

    elzas_server = None
    for server in servers:
        if "ElzasBrigade" in server['name']:
            elzas_server = server
            break

    if not elzas_server:
        await ctx.send("❌ Aucun serveur ElzasBrigade disponible pour cette période.")
        return

    server_id = elzas_server['id']

    reservation, status = await create_reservation(
        start_time_iso, end_time_iso, server_id, password, rcon, server_config_id
    )
    if status == 200:
        res = reservation["reservation"]
        start_dt = datetime.fromisoformat(start_time_iso).astimezone(paris_tz)
        public_info = (
            f"✅ Réservation confirmée sur **{clean_server_name(res['server']['name'])}**\n"
            f"**Date et heure d'ouverture :** {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
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

        if ctx.author.id not in user_data:
            user_data[ctx.author.id] = []
        user_data[ctx.author.id].append({
            "reservation_id": res["id"],
            "start": start_time_iso,
            "end": end_time_iso,
            "server_name": res['server']['name'],
            "rcon": rcon
        })

        bot.loop.create_task(notify_server_open(
            ctx, res['server']['name'], res['server']['ip_and_port'], res['password'], start_dt
        ))
    else:
        await ctx.send("❌ Erreur lors de la création de la réservation.")
        await ctx.send(str(reservation.get("reservation", {}).get("errors", {})))

async def notify_server_open(ctx, server_name, ip_and_port, password, start_dt):
    """Send a notification when the server is open."""
    paris_tz = pytz.timezone("Europe/Paris")
    now = datetime.now(paris_tz)
    seconds_until_start = (start_dt - now).total_seconds()
    
    if seconds_until_start > 0:
        await asyncio.sleep(seconds_until_start)
    
    notification = (
        f"🔔 **Le serveur est maintenant ouvert !**\n"
        f"Serveur : **{clean_server_name(server_name)}**\n"
        f"**Connect info :**\n"
        f"```\nconnect {ip_and_port}; password \"{password}\"\n```\n"
    )
    await ctx.send(notification)

@bot.command(name="confirm")
async def confirm(ctx, server_id: int, password: str, rcon: str = None):
    """
    Confirme la réservation d'un serveur.
    Exemple : !confirm 12345 mypassword
    """
    if ctx.author.id not in user_data or not user_data[ctx.author.id]:
        await ctx.send("Aucune réservation en attente. Utilise `!reserve` d'abord.")
        return

    # Get the latest reservation data
    data = user_data[ctx.author.id][-1]

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

    server_config_id = data.get("server_config_id")
    reservation, status = await create_reservation(
        data["start"], data["end"], server_id, password, rcon, server_config_id
    )
    if status == 200:
        res = reservation["reservation"]
        start_dt = datetime.fromisoformat(data["start"]).astimezone(pytz.timezone("Europe/Paris"))
        public_info = (
            f"✅ Réservation confirmée sur **{clean_server_name(res['server']['name'])}**\n"
            f"**Date et heure d'ouverture :** {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
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
        
        # Update the reservation data
        data["reservation_id"] = res["id"]
        data["server_name"] = res['server']['name']
        data["rcon"] = rcon
        bot.loop.create_task(notify_server_open(
            ctx, res['server']['name'], res['server']['ip_and_port'], res['password'], start_dt
        ))
    else:
        await ctx.send("❌ Erreur lors de la création de la réservation.")
        await ctx.send(str(reservation.get("reservation", {}).get("errors", {})))

@bot.command(name="list")
async def list_reservations(ctx):
    """
    Affiche la liste des réservations actives de l'utilisateur.
    Exemple : !list
    """
    if ctx.author.id not in user_data or not user_data[ctx.author.id]:
        await ctx.send("Tu n'as aucune réservation active.")
        return

    reservations = user_data[ctx.author.id]
    message = "**Tes réservations actives :**\n"
    for res in reservations:
        if "reservation_id" in res:
            start_dt = datetime.fromisoformat(res["start"]).astimezone(pytz.timezone("Europe/Paris"))
            end_dt = datetime.fromisoformat(res["end"]).astimezone(pytz.timezone("Europe/Paris"))
            message += (
                f"ID `{res['reservation_id']}`: {clean_server_name(res['server_name'])}\n"
                f" - Début : {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
                f" - Fin : {end_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
            )
        else:
            start_dt = datetime.fromisoformat(res["start"]).astimezone(pytz.timezone("Europe/Paris"))
            message += (
                f"En attente de confirmation pour {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
            )

    message += "\nUtilise `!end <reservation_id>` pour terminer une réservation spécifique ou `!end` pour la dernière."
    await ctx.send(message)

@bot.command(name="end")
async def end(ctx, reservation_id: int = None):
    """
    Termine une réservation active.
    Exemple : !end [reservation_id]
    """
    if ctx.author.id not in user_data or not user_data[ctx.author.id]:
        await ctx.send("Aucune réservation à terminer.")
        return

    reservations = [res for res in user_data[ctx.author.id] if "reservation_id" in res]
    if not reservations:
        await ctx.send("Aucune réservation confirmée à terminer.")
        return

    if reservation_id:
        target_res = None
        for res in reservations:
            if res["reservation_id"] == reservation_id:
                target_res = res
                break
        if not target_res:
            await ctx.send(f"Aucune réservation trouvée avec l'ID {reservation_id}. Vérifie avec `!list`.")
            return
        res_id = target_res["reservation_id"]
    else:
        target_res = reservations[-1]  # Dernière réservation confirmée
        res_id = target_res["reservation_id"]

    response, status = await end_reservation(res_id)
    if status == 200 or status == 204:
        await ctx.send(f"✅ Réservation terminée (ID {res_id})")
        user_data[ctx.author.id].remove(target_res)
        if not user_data[ctx.author.id]:
            del user_data[ctx.author.id]
    else:
        await ctx.send("❌ Impossible de terminer la réservation.")
        await ctx.send(response)

bot.run(TOKEN)
