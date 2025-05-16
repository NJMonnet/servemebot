from datetime import timedelta
import pytz

class Config:
    TIMEZONE = pytz.timezone("Europe/Paris")
    RESERVATION_DURATION = timedelta(hours=2)
    DEFAULT_RCON = "fishrcon"
    SERVER_CONFIG_FILE_5CP = "etf2l_6v6_5cp"
    SERVER_CONFIG_FILE_KOTH = "etf2l_6v6_koth"
    SERVER_CONFIG_FILES = [SERVER_CONFIG_FILE_5CP, SERVER_CONFIG_FILE_KOTH]
    
    EMOJIS = ['🇦', '🇧', '🇨', '🇩', '🇪', '🇫', '🇬', '🇭', '🇮', '🇯']

    ERROR_MESSAGES = {
        "reserve": {
            "invalid_format": "Utilisez `!reserve now|<heure> [<mot de passe>]` (ex: `!reserve now`, `!reserve 20:00 mypassword`) ou `!reserve <date> <heure> [<mot de passe>]` (ex: `!reserve 2025-05-05 20:00`). Heure au format HH:MM ou HHhMM.",
            "already_active": "Erreur : Tu as déjà une réservation active. Termine-la avec `!end`.",
            "no_servers": "Erreur : Aucun serveur disponible.",
            "invalid_date": "Erreur : Utilise YYYY-MM-DD, ex: `2025-05-05`.",
            "invalid_time": "Erreur : Utilise 'now', HHhMM ou HH:MM, ex: `20h00` ou `20:00`.",
            "date_too_far": "Erreur : La date est trop éloignée (max 1 an)."
        },
        "general": {
            "dm_blocked": "Erreur : DMs bloqués. Ouvre tes DMs pour recevoir le RCON.",
            "timeout": "Erreur : Temps écoulé pour répondre.",
            "no_reservation": "Erreur : Aucune réservation active.",
            "invalid_rcon": "Erreur : RCON incorrect ou impossible de recevoir le RCON."
        }
    }

    HELP_TEXT = (
        "📖 **Aide du Bot de Réservation**\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔹 **Commandes de Réservation**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🖥️ `!reserve now | <heure> | [<date> <heure>] [<mot de passe>]`\n"
        " ↪ Réserve un serveur pour 2h\n"
        "  Exemples : `!reserve now`, `!reserve 2025-05-05 20:00`\n\n"

        "🔗 `!connect [<@user> | <ID>]`\n"
        " ↪ Affiche les infos de connexion\n"
        "  Exemples : `!connect`, `!connect 12345`\n\n"

        "📋 `!list`\n"
        " ↪ Liste les réservations actives\n\n"

        "🛑 `!end [<@user> | <ID>]`\n"
        " ↪ Termine une réservation\n"
        "  Exemples : `!end`, `!end 12345`\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🔹 **Commandes Serveur**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔄 `!changelevel [<@user> | <ID>] [<map>]`\n"
        " ↪ Change la map actuelle\n"
        "  Exemples : `!changelevel`, `!changelevel @user cp_process_f12`\n\n"

        "⚙️ `!exec [<@user> | <ID>] [<config>]`\n"
        " ↪ Lance une configuration serveur\n"
        "  Exemples : `!exec`, `!exec @user etf2l_6v6_5cp`\n\n"

        "🔐 `!rcon`\n"
        " ↪ Envoie le mot de passe RCON en DM\n\n"

        "━━━━━━━━━━━━━━━━━━\n"
        "🔹 **Utilitaires**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📅 `!dispo`\n"
        " ↪ Indique tes disponibilités pour la semaine\n\n"

        "❓ `!help`\n"
        " ↪ Affiche ce message d’aide\n"
    )

    AVAILABLE_MAPS = [
        "cp_granary_pro_rc16f", "cp_process_f12", "cp_gullywash_f9", "cp_metalworks_f5",
        "cp_snakewater_final1", "cp_sultry_b8a", "cp_sunshine",
        "koth_bagel_rc10", "koth_product_final"
    ]
