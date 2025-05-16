import discord
from discord.ext import commands
from datetime import datetime, timedelta
from utils import end_reservation, clean_server_name
from config import Config
from rcon.source import Client
import asyncio
import concurrent.futures
from discord.ext import tasks

class UtilityCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._user_data = None
        self.cleanup_old_reservations.start()

    def cog_unload(self):
        """Annule la tâche de nettoyage lors du déchargement."""
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

    @property
    def user_data(self):
        if self._user_data is None:
            reservation_cog = self.bot.get_cog("ReservationCommands")
            if reservation_cog is None:
                raise RuntimeError("ReservationCommands cog not loaded")
            self._user_data = reservation_cog.user_data
        return self._user_data

    async def find_reservation(self, ctx, target: discord.Member | int = None):
        """Trouve une réservation active pour un utilisateur ou un ID."""
        reservations = []
        for user_id, user_reservations in self.user_data.items():
            reservations.extend([res for res in user_reservations if "reservation_id" in res])

        if not reservations:
            await ctx.send(embed=discord.Embed(title="Erreur", description=Config.ERROR_MESSAGES["general"]["no_reservation"], color=discord.Color.red()))
            return None, reservations

        target_id = target.id if isinstance(target, discord.Member) else ctx.author.id
        reservation_id = target if isinstance(target, int) else None

        if len(reservations) > 1 and not target:
            reservation_list = "\n".join(
                f"ID `{res['reservation_id']}`: {clean_server_name(res['server_name'])} (Créateur : {res['creator_name']})"
                for res in reservations
            )
            await ctx.send(embed=discord.Embed(
                title="Erreur",
                description=f"Plusieurs réservations actives. Utilise `!changelevel @createur` ou `!changelevel <reservation_id>`.\n\n**Réservations actives :**\n{reservation_list}",
                color=discord.Color.red()
            ))
            return None, reservations

        if reservation_id:
            reservation = next((res for res in reservations if res["reservation_id"] == reservation_id), None)
            if not reservation:
                await ctx.send(embed=discord.Embed(title="Erreur", description=f"Aucune réservation avec l'ID {reservation_id}. Vérifie avec `!list`.", color=discord.Color.red()))
                return None, reservations
        elif isinstance(target, discord.Member):
            reservation = next((res for res in self.user_data.get(target_id, []) if "reservation_id" in res), None)
            if not reservation:
                await ctx.send(embed=discord.Embed(title="Erreur", description=f"Aucune réservation active pour {target.name}.", color=discord.Color.red()))
                return None, reservations
        else:
            reservation = next((res for res in reservations if res["creator_id"] == ctx.author.id), None)
            if not reservation and len(reservations) == 1:
                reservation = reservations[0]
            elif not reservation:
                await ctx.send(embed=discord.Embed(title="Erreur", description="Aucune réservation confirmée pour toi.", color=discord.Color.red()))
                return None, reservations

        now = datetime.now(Config.TIMEZONE)
        start_dt = datetime.fromisoformat(reservation["start"]).astimezone(Config.TIMEZONE)
        end_dt = datetime.fromisoformat(reservation["end"]).astimezone(Config.TIMEZONE)
        if now < start_dt or now > end_dt:
            await ctx.send(embed=discord.Embed(title="Erreur", description=f"La réservation ID `{reservation['reservation_id']}` n'est pas active.", color=discord.Color.red()))
            return None, reservations

        return reservation, reservations

    async def verify_rcon(self, ctx, reservation, rcon_prompt_msg=None):
        """Vérifie le mot de passe RCON via DM."""
        try:
            if rcon_prompt_msg:
                await rcon_prompt_msg.edit(embed=discord.Embed(
                    description="Vérifie tes DMs pour fournir le mot de passe RCON.", 
                    color=discord.Color.blue()
                ))
            await ctx.author.send(f"Veuillez fournir le mot de passe RCON pour la réservation ID `{reservation['reservation_id']}`.")
            def check(m):
                return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)
            response = await self.bot.wait_for('message', check=check, timeout=60.0)
            rcon = response.content.strip()
            if rcon != reservation["rcon"]:
                raise ValueError("RCON incorrect")
            if rcon_prompt_msg:
                await rcon_prompt_msg.delete()
            return True
        except (asyncio.TimeoutError, discord.Forbidden, ValueError) as e:
            error_msg = Config.ERROR_MESSAGES["general"]["invalid_rcon"]
            if isinstance(e, asyncio.TimeoutError):
                error_msg = Config.ERROR_MESSAGES["general"]["timeout"]
            if rcon_prompt_msg:
                await rcon_prompt_msg.delete()
            await ctx.send(embed=discord.Embed(description=error_msg, color=discord.Color.red()))
            return False

    async def run_rcon_command(self, ip, port, rcon_password, command, *args):
        """Exécute une commande RCON dans un thread pool."""
        def rcon_task():
            with Client(ip, port, passwd=rcon_password, timeout=10.0) as client:
                return client.run(command, *args)
        
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = await loop.run_in_executor(pool, rcon_task)
            return result
        except Exception as e:
            raise RuntimeError(f"Erreur RCON : {str(e)}")

    @commands.command(name="help")
    async def help_command(self, ctx):
        """Affiche le message d'aide."""
        embed = discord.Embed(
            title="Aide du Bot",
            description=Config.HELP_TEXT,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command(name="changelevel")
    async def changelevel(self, ctx, target: discord.Member | int = None, map_name: str = None):
        """Change la carte du serveur."""
        reservation, _ = await self.find_reservation(ctx, target)
        if not reservation:
            return

        if ctx.author.id != reservation["creator_id"]:
            rcon_prompt_msg = await ctx.send(embed=discord.Embed(
                description="Vérification du RCON en cours...", 
                color=discord.Color.blue()
            ))
            if not await self.verify_rcon(ctx, reservation, rcon_prompt_msg):
                return

        try:
            ip_port = reservation["ip_and_port"].split(":")
            ip = ip_port[0]
            port = int(ip_port[1])
            rcon_password = reservation["rcon"]
        except (IndexError, ValueError):
            await ctx.send(embed=discord.Embed(
                description="Erreur : Informations RCON invalides.",
                color=discord.Color.red()
            ))
            return

        if map_name:
            try:
                response = await self.run_rcon_command(ip, port, rcon_password, "changelevel", map_name)
                # Tronquer la réponse pour éviter les erreurs de limite de caractères
                response_truncated = response[:1000] + ("..." if len(response) > 1000 else "")
                await ctx.send(embed=discord.Embed(
                    title="✅ Map changée",
                    description=f"La map a été changée en **{map_name}**.\nRéponse du serveur : `{response_truncated}`",
                    color=discord.Color.green()
                ))
            except Exception as e:
                await ctx.send(embed=discord.Embed(
                    description=f"Erreur lors du changement de map : {str(e)}",
                    color=discord.Color.red()
                ))
            return

        embed = discord.Embed(
            title="Choisir une nouvelle carte",
            description="\n".join(f"{i+1}. {m}" for i, m in enumerate(Config.AVAILABLE_MAPS)),
            color=discord.Color.blue()
        )
        msg = await ctx.send(embed=embed)
        for i in range(len(Config.AVAILABLE_MAPS)):
            await msg.add_reaction(f"{i+1}\u20e3")

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == msg.id and reaction.emoji in [f"{i+1}\u20e3" for i in range(len(Config.AVAILABLE_MAPS))]

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=60.0)
            map_name = Config.AVAILABLE_MAPS[int(reaction.emoji[0]) - 1]
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                description=Config.ERROR_MESSAGES["general"]["timeout"],
                color=discord.Color.red()
            ))
            return

        try:
            response = await self.run_rcon_command(ip, port, rcon_password, "changelevel", map_name)
            # Tronquer la réponse pour éviter les erreurs de limite de caractères
            response_truncated = response[:1000] + ("..." if len(response) > 1000 else "")
            await ctx.send(embed=discord.Embed(
                title="✅ Map changée",
                description=f"La map a été changée en **{map_name}**.\nRéponse du serveur : `{response_truncated}`",
                color=discord.Color.green()
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"Erreur lors du changement de map : {str(e)}",
                color=discord.Color.red()
            ))

    @commands.command(name="exec")
    async def exec_config(self, ctx, target: discord.Member | int = None, config: str = None):
        """Exécute une configuration sur le serveur."""
        reservation, _ = await self.find_reservation(ctx, target)
        if not reservation:
            return

        if ctx.author.id != reservation["creator_id"]:
            rcon_prompt_msg = await ctx.send(embed=discord.Embed(
                description="Vérification du RCON en cours...", 
                color=discord.Color.blue()
            ))
            if not await self.verify_rcon(ctx, reservation, rcon_prompt_msg):
                return

        try:
            ip_port = reservation["ip_and_port"].split(":")
            ip = ip_port[0]
            port = int(ip_port[1])
            rcon_password = reservation["rcon"]
        except (IndexError, ValueError):
            await ctx.send(embed=discord.Embed(
                description="Erreur : Informations RCON invalides.",
                color=discord.Color.red()
            ))
            return

        if config:
            try:
                response = await self.run_rcon_command(ip, port, rcon_password, "exec", config)
                # Tronquer la réponse pour éviter les erreurs de limite de caractères
                response_truncated = response[:1000] + ("..." if len(response) > 1000 else "")
                await ctx.send(embed=discord.Embed(
                    title="✅ Configuration exécutée",
                    description=f"La configuration **{config}** a été exécutée.\nRéponse du serveur : `{response_truncated}`",
                    color=discord.Color.green()
                ))
            except Exception as e:
                await ctx.send(embed=discord.Embed(
                    description=f"Erreur lors de l'exécution de la configuration : {str(e)}",
                    color=discord.Color.red()
                ))
            return

        embed = discord.Embed(
            title="Choisir une configuration",
            description="\n".join(f"{i+1}. {c}" for i, c in enumerate(Config.SERVER_CONFIG_FILES)),
            color=discord.Color.blue()
        )
        msg = await ctx.send(embed=embed)
        for i in range(len(Config.SERVER_CONFIG_FILES)):
            await msg.add_reaction(f"{i+1}\u20e3")

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == msg.id and reaction.emoji in [f"{i+1}\u20e3" for i in range(len(Config.SERVER_CONFIG_FILES))]

        try:
            reaction, _ = await self.bot.wait_for('reaction_add', check=check, timeout=60.0)
            config_name = Config.SERVER_CONFIG_FILES[int(reaction.emoji[0]) - 1]
        except asyncio.TimeoutError:
            await ctx.send(embed=discord.Embed(
                description=Config.ERROR_MESSAGES["general"]["timeout"],
                color=discord.Color.red()
            ))
            return

        try:
            response = await self.run_rcon_command(ip, port, rcon_password, "exec", config_name)
            # Tronquer la réponse pour éviter les erreurs de limite de caractères
            response_truncated = response[:1000] + ("..." if len(response) > 1000 else "")
            await ctx.send(embed=discord.Embed(
                title="✅ Configuration exécutée",
                description=f"La configuration **{config_name}** a été exécutée.\nRéponse du serveur : `{response_truncated}`",
                color=discord.Color.green()
            ))
        except Exception as e:
            await ctx.send(embed=discord.Embed(
                description=f"Erreur lors de l'exécution de la configuration : {str(e)}",
                color=discord.Color.red()
            ))

    @commands.command(name="connect")
    async def connect(self, ctx, target: discord.Member | int = None):
        """Affiche les informations de connexion pour une réservation."""
        target_id = target.id if isinstance(target, discord.Member) else ctx.author.id
        target_name = target.name if isinstance(target, discord.Member) else None
        reservation_id = target if isinstance(target, int) else None

        if target_id not in self.user_data or not self.user_data[target_id]:
            await ctx.send(embed=discord.Embed(
                title="Erreur", 
                description=f"Aucune réservation active pour {'toi' if target_id == ctx.author.id else target_name}.",
                color=discord.Color.red()
            ))
            return

        reservations = [res for res in self.user_data[target_id] if "reservation_id" in res]
        if not reservations:
            await ctx.send(embed=discord.Embed(
                title="Erreur", 
                description=f"Aucune réservation confirmée pour {'toi' if target_id == ctx.author.id else target_name}.",
                color=discord.Color.red()
            ))
            return

        target_res = next((res for res in reservations if res["reservation_id"] == reservation_id), reservations[-1])
        if reservation_id and target_res["reservation_id"] != reservation_id:
            await ctx.send(embed=discord.Embed(
                title="Erreur", 
                description=f"Aucune réservation avec l'ID {reservation_id}. Vérifie avec `!list`.",
                color=discord.Color.red()
            ))
            return

        start_dt = datetime.fromisoformat(target_res["start"]).astimezone(Config.TIMEZONE)
        embed = discord.Embed(
            title="🔗 Connexion",
            description=(
                f"**Serveur :** {clean_server_name(target_res['server_name'])}\n"
                f"**Connect info :**\n"
                f"```\nconnect {target_res['ip_and_port']}; password \"{target_res['password']}\"\n```"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"ID {target_res['reservation_id']} | Créateur : {target_res['creator_name']} | Début : {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)")
        await ctx.send(embed=embed)

    @commands.command(name="list")
    async def list_reservations(self, ctx):
        """Liste toutes les réservations actives."""
        if not self.user_data:
            await ctx.send(embed=discord.Embed(
                title="Aucune réservation", 
                description="Aucune réservation active.",
                color=discord.Color.red()
            ))
            return

        now = datetime.now(Config.TIMEZONE)
        message = ""
        for user_id, reservations in self.user_data.items():
            for res in reservations:
                if "reservation_id" in res:
                    end_dt = datetime.fromisoformat(res["end"]).astimezone(Config.TIMEZONE)
                    if now > end_dt + timedelta(hours=1):
                        continue
                    start_dt = datetime.fromisoformat(res["start"]).astimezone(Config.TIMEZONE)
                    message += (
                        f"**ID `{res['reservation_id']}`**: {clean_server_name(res['server_name'])}\n"
                        f" - **Créateur** : {res['creator_name']}\n"
                        f" - **Début** : {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
                        f" - **Fin** : {end_dt.strftime('%Y-%m-%d %H:%M')} (Paris)\n"
                    )
                else:
                    start_dt = datetime.fromisoformat(res["start"]).astimezone(Config.TIMEZONE)
                    message += f"En attente de confirmation pour {start_dt.strftime('%Y-%m-%d %H:%M')} (Paris) par {res['creator_name']}\n"

        message += "\nUtilise `!end <reservation_id>` ou `!end` pour terminer tes réservations."
        await ctx.send(embed=discord.Embed(
            title="📋 Réservations actives", 
            description=message or "Aucune réservation active.", 
            color=discord.Color.blue()
        ))

    @commands.command(name="end")
    async def end(self, ctx, target: discord.Member | int = None):
        """Termine une réservation."""
        reservation, _ = await self.find_reservation(ctx, target)
        if not reservation:
            return

        if ctx.author.id != reservation["creator_id"]:
            rcon_prompt_msg = await ctx.send(embed=discord.Embed(
                description="Vérification du RCON en cours...", 
                color=discord.Color.blue()
            ))
            if not await self.verify_rcon(ctx, reservation, rcon_prompt_msg):
                return

        response, status = await end_reservation(reservation["reservation_id"])
        if status in (200, 204):
            if reservation["reservation_id"] in self.bot.get_cog("ReservationCommands").notify_tasks:
                task = self.bot.get_cog("ReservationCommands").notify_tasks[reservation["reservation_id"]]
                task.cancel()
                del self.bot.get_cog("ReservationCommands").notify_tasks[reservation["reservation_id"]]

            if reservation["creator_id"] in self.user_data:
                self.user_data[reservation["creator_id"]] = [
                    res for res in self.user_data[reservation["creator_id"]] 
                    if res.get("reservation_id") != reservation["reservation_id"]
                ]
                if not self.user_data[reservation["creator_id"]]:
                    del self.user_data[reservation["creator_id"]]
            await ctx.send(embed=discord.Embed(
                title="✅ Réservation terminée", 
                description=f"Réservation ID `{reservation['reservation_id']}` terminée.",
                color=discord.Color.green()
            ))
        else:
            await ctx.send(embed=discord.Embed(
                title="Erreur", 
                description=f"Échec de la terminaison : {response}",
                color=discord.Color.red()
            ))

    @commands.command(name="rcon")
    async def rcon(self, ctx):
        """Envoie le mot de passe RCON en DM."""
        if ctx.author.id not in self.user_data or not self.user_data[ctx.author.id]:
            await ctx.send(embed=discord.Embed(
                title="Erreur", 
                description=Config.ERROR_MESSAGES["general"]["no_reservation"], 
                color=discord.Color.red()
            ))
            return

        reservation = next((res for res in self.user_data[ctx.author.id] if "reservation_id" in res), None)
        if not reservation:
            await ctx.send(embed=discord.Embed(
                title="Erreur", 
                description="Aucune réservation confirmée.", 
                color=discord.Color.red()
            ))
            return

        rcon_info = discord.Embed(
            title=f"RCON pour {clean_server_name(reservation['server_name'])}",
            description=f"```\nrcon_address {reservation['ip_and_port']}; rcon_password \"{reservation['rcon']}\"\n```",
            color=discord.Color.blue()
        )
        try:
            await ctx.author.send(embed=rcon_info)
            await ctx.send(embed=discord.Embed(
                description="RCON envoyé en DM.", 
                color=discord.Color.blue()
            ))
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                description=Config.ERROR_MESSAGES["general"]["dm_blocked"], 
                color=discord.Color.red()
            ))

    @commands.command(name="dispo")
    async def dispo(self, ctx):
        """Permet aux utilisateurs d'indiquer leurs disponibilités."""
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        today = datetime.now(Config.TIMEZONE)
        start_date = today - timedelta(days=today.weekday())

        instruction_embed = discord.Embed(
            title="Indiquez vos disponibilités",
            description=(
                "Veuillez indiquer votre disponibilité en réagissant aux messages des jours suivants avec l'emoji correspondant :\n\n"
                "✅ 20h\n"
                "☑️ 21h\n"
                "❌ Pas disponible\n"
                "🐟 Sub"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=instruction_embed)

        for i in range(7):
            embed = discord.Embed(
                title=f"Disponibilité pour {days[i]}",
                description="Réagissez avec l'emoji correspondant à votre disponibilité.",
                color=discord.Color.blue()
            )
            msg = await ctx.send(embed=embed)
            for emoji in ["✅", "☑️", "❌", "🐟"]:
                await msg.add_reaction(emoji)
                await asyncio.sleep(0.1)  # Petite pause pour éviter les rate limits

async def setup(bot):
    await bot.add_cog(UtilityCommands(bot))
