from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import re
from utils import find_servers, create_reservation, clean_server_name
from config import Config
import logging
from discord.ext import tasks

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReservationCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_data = {}
        self.notify_tasks = {}
        self.cleanup_old_reservations.start()

    def cog_unload(self):
        """Annule les tâches de notification lors du déchargement."""
        for task in self.notify_tasks.values():
            task.cancel()
        self.notify_tasks.clear()
        self.cleanup_old_reservations.cancel()

    @tasks.loop(hours=6)
    async def cleanup_old_reservations(self):
        """Nettoie les réservations terminées depuis plus d'une heure."""
        now = datetime.now(Config.TIMEZONE)
        for user_id in list(self.user_data.keys()):
            self.user_data[user_id] = [
                res for res in self.user_data[user_id]
                if "reservation_id" not in res or datetime.fromisoformat(res["end"]).astimezone(Config.TIMEZONE) > now - timedelta(hours=1)
            ]
            if not self.user_data[user_id]:
                del self.user_data[user_id]

    async def select_option(self, ctx, title, options, timeout=60.0):
        """Permet à l'utilisateur de sélectionner une option via des réactions."""
        emojis = Config.EMOJIS[:len(options)]
        embed = discord.Embed(title=title, description="\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options)), color=discord.Color.blue())
        msg = await ctx.send(embed=embed)
        for emoji in emojis:
            await msg.add_reaction(emoji)
            await asyncio.sleep(0.1)  # Réduit de 0.5 à 0.1 pour plus de réactivité

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in emojis

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=timeout)
            logger.info(f"Réaction reçue : {reaction.emoji}, Utilisateur : {ctx.author.name}")
            return options[emojis.index(str(reaction.emoji))]
        except asyncio.TimeoutError:
            logger.warning("Timeout lors de la sélection")
            await ctx.send(embed=discord.Embed(description=Config.ERROR_MESSAGES["general"]["timeout"], color=discord.Color.red()))
            return None

    async def notify_server_open(self, ctx, server_name, ip_and_port, password, start_dt, reservation_id):
        """Notifie l'ouverture du serveur à l'heure prévue."""
        now = datetime.now(Config.TIMEZONE)
        seconds_until_start = (start_dt - now).total_seconds()
        if seconds_until_start > 0:
            await asyncio.sleep(seconds_until_start)
        
        if reservation_id in self.notify_tasks:
            embed = discord.Embed(
                title="🔔 Serveur ouvert",
                description=(
                    f"**Serveur :** {clean_server_name(server_name)}\n"
                    f"**Connect info :**\n"
                    f"```\nconnect {ip_and_port}; password \"{password}\"\n```\n"
                    f"Ouvert à {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)"
                ),
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            del self.notify_tasks[reservation_id]

    async def get_rcon(self, ctx, rcon_prompt_msg=None):
        """Demande le mot de passe RCON via DM."""
        try:
            if rcon_prompt_msg:
                await rcon_prompt_msg.edit(embed=discord.Embed(
                    description="Vérifie tes DMs pour fournir le mot de passe RCON.", 
                    color=discord.Color.blue()
                ))
            await ctx.author.send("Veuillez fournir le mot de passe RCON.")
            def check(m):
                return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
            response = await self.bot.wait_for('message', check=check, timeout=60.0)
            rcon = response.content.strip()
            if not rcon:
                raise ValueError("RCON vide")
            if rcon_prompt_msg:
                await rcon_prompt_msg.delete()
            return rcon
        except (asyncio.TimeoutError, discord.Forbidden, ValueError) as e:
            error_msg = Config.ERROR_MESSAGES["general"]["invalid_rcon"]
            if isinstance(e, asyncio.TimeoutError):
                error_msg = Config.ERROR_MESSAGES["general"]["timeout"]
            if rcon_prompt_msg:
                await rcon_prompt_msg.delete()
            await ctx.send(embed=discord.Embed(description=error_msg, color=discord.Color.red()))
            return None

    @commands.command(name="reserve")
    async def reserve(self, ctx, *, args: str = None):
        """Réserve un serveur pour une période donnée."""
        if ctx.guild is None:
            await ctx.send(embed=discord.Embed(
                description="Erreur : Cette commande ne peut être utilisée que dans un serveur, pas en DM.",
                color=discord.Color.red()
            ))
            return

        now = datetime.now(Config.TIMEZONE)
        if ctx.author.id in self.user_data:
            active_reservations = [
                res for res in self.user_data[ctx.author.id]
                if "reservation_id" in res and datetime.fromisoformat(res["end"]).astimezone(Config.TIMEZONE) > now - timedelta(hours=1)
            ]
            if active_reservations:
                await ctx.send(embed=discord.Embed(
                    description=Config.ERROR_MESSAGES["reserve"]["already_active"],
                    color=discord.Color.red()
                ))
                return

        if not args:
            await ctx.send(embed=discord.Embed(
                description=Config.ERROR_MESSAGES["reserve"]["invalid_format"],
                color=discord.Color.red()
            ))
            return

        parts = args.split()
        date_str = None
        time_str = None
        password = "fish"
        use_default_rcon = True

        if parts[0].lower() == "now":
            if len(parts) == 1:
                time_str = "now"
            elif len(parts) == 2:
                time_str = "now"
                password = parts[1]
                use_default_rcon = False
        elif re.match(r"\d{4}-\d{2}-\d{2}", parts[0]):
            date_str = parts[0]
            time_str = parts[1]
            if len(parts) >= 3:
                password = parts[2]
                use_default_rcon = False
        else:
            time_str = parts[0]
            if len(parts) >= 2:
                password = parts[1]
                use_default_rcon = False

        if time_str.lower() == "now":
            start_dt = now
        else:
            try:
                time_str = time_str.replace(":", "h")
                time_obj = datetime.strptime(time_str, "%Hh%M")
                start_dt = now.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)
                if start_dt < now:
                    start_dt += timedelta(days=1)
            except ValueError:
                await ctx.send(embed=discord.Embed(
                    description=Config.ERROR_MESSAGES["reserve"]["invalid_time"],
                    color=discord.Color.red()
                ))
                return

        if date_str:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if date_obj.year > now.year + 1:
                    await ctx.send(embed=discord.Embed(description=Config.ERROR_MESSAGES["reserve"]["date_too_far"], color=discord.Color.red()))
                    return
                start_dt = date_obj.replace(
                    hour=start_dt.hour, minute=start_dt.minute, second=0, microsecond=0, tzinfo=Config.TIMEZONE
                )
            except ValueError:
                await ctx.send(embed=discord.Embed(
                    description=Config.ERROR_MESSAGES["reserve"]["invalid_date"],
                    color=discord.Color.red()
                ))
                return

        end_dt = start_dt + Config.RESERVATION_DURATION
        start_time_iso = start_dt.isoformat()
        end_time_iso = end_dt.isoformat()

        await ctx.send(f"Recherche de serveurs pour {start_dt.strftime('%Y-%m-%d %H:%M')}...")

        try:
            data = await find_servers(start_time_iso, end_time_iso)
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=str(e), color=discord.Color.red()))
            return

        servers = data.get("servers", [])
        server_configs = data.get("server_configs", [])
        if not servers:
            await ctx.send(embed=discord.Embed(
                description=Config.ERROR_MESSAGES["reserve"]["no_servers"],
                color=discord.Color.red()
            ))
            return

        server_groups = {}
        for s in servers:
            group_name = s['name'].split('#')[0].strip()
            server_groups.setdefault(group_name, []).append(s)

        if not server_groups:
            await ctx.send(embed=discord.Embed(
                description=Config.ERROR_MESSAGES["reserve"]["no_servers"],
                color=discord.Color.red()
            ))
            return

        if not ctx.channel.permissions_for(ctx.guild.me).add_reactions:
            await ctx.send(embed=discord.Embed(
                description="Erreur : Le bot n'a pas la permission d'ajouter des réactions.",
                color=discord.Color.red()
            ))
            return

        group_names = sorted(server_groups.keys())[:10]
        selected_group = await self.select_option(ctx, "Choisir un serveur", group_names)
        if not selected_group:
            return

        selected_server = sorted(server_groups[selected_group], key=lambda x: x['id'])[0]
        server_id = selected_server['id']

        maps = Config.AVAILABLE_MAPS[:10]
        map_name = await self.select_option(ctx, "Choisir une carte", maps)
        if not map_name:
            return

        server_config_file = Config.SERVER_CONFIG_FILE_5CP if map_name.startswith("cp_") else Config.SERVER_CONFIG_FILE_KOTH
        server_config_id = next((config["id"] for config in server_configs if config.get("file") == server_config_file), None)

        rcon = Config.DEFAULT_RCON if use_default_rcon else None
        if not rcon:
            rcon_prompt_msg = await ctx.send(embed=discord.Embed(
                description="Préparation de la réservation...", 
                color=discord.Color.blue()
            ))
            rcon = await self.get_rcon(ctx, rcon_prompt_msg)
            if rcon is None:
                return

        try:
            reservation, status = await create_reservation(
                start_time_iso, end_time_iso, server_id, password, rcon, server_config_id, first_map=map_name
            )
        except Exception as e:
            await ctx.send(embed=discord.Embed(description=f"Erreur : {str(e)}", color=discord.Color.red()))
            return

        if status == 200:
            res = reservation["reservation"]
            is_now = time_str.lower() == "now"

            if is_now:
                embed = discord.Embed(
                    title="🔔 Serveur ouvert",
                    description=(
                        f"**Serveur :** {clean_server_name(res['server']['name'])}\n"
                        f"**Connect info :**\n"
                        f"```\nconnect {res['server']['ip_and_port']}; password \"{res['password']}\"\n```\n"
                        f"Ouvert à {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)"
                    ),
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="✅ Réservation confirmée",
                    description=(
                        f"{ctx.author.mention} Réservation confirmée !\n\n"
                        f"**Serveur :** {clean_server_name(res['server']['name'])}\n"
                        f"**Début :** {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
                        f"**Connect info :**\n"
                        f"```\nconnect {res['server']['ip_and_port']}; password \"{res['password']}\"\n```\n"
                        f"RCON envoyé en DM."
                    ),
                    color=discord.Color.green()
                )

            await ctx.send(embed=embed)

            rcon_info = discord.Embed(
                title=f"RCON pour {clean_server_name(res['server']['name'])}",
                description=f"```\nrcon_address {res['server']['ip_and_port']}; rcon_password \"{rcon}\"\n```",
                color=discord.Color.blue()
            )
            try:
                await ctx.author.send(embed=rcon_info)
            except discord.Forbidden:
                await ctx.send(embed=discord.Embed(
                    description=Config.ERROR_MESSAGES["general"]["dm_blocked"],
                    color=discord.Color.red()
                ))

            if ctx.author.id not in self.user_data:
                self.user_data[ctx.author.id] = []
            self.user_data[ctx.author.id].append({
                "reservation_id": res["id"],
                "start": start_time_iso,
                "end": end_time_iso,
                "server_name": res['server']['name'],
                "ip_and_port": res['server']['ip_and_port'],
                "password": res['password'],
                "rcon": rcon,
                "creator_id": ctx.author.id,
                "creator_name": ctx.author.name
            })

            if not is_now:
                self.notify_tasks[res["id"]] = self.bot.loop.create_task(self.notify_server_open(
                    ctx, res['server']['name'], res['server']['ip_and_port'], res['password'], start_dt, res["id"]
                ))
        else:
            await ctx.send(embed=discord.Embed(
                description=f"Erreur : Impossible de réserver.",
                color=discord.Color.red()
            ))

async def setup(bot):
    await bot.add_cog(ReservationCommands(bot))
