import aiohttp
import os
import re
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("SERVEME_API_KEY")

# Validation de la clé API
if not API_KEY:
    raise ValueError("La clé API de serveme.tf n'est pas définie dans le fichier .env")

BASE_URL = "https://serveme.tf/api/reservations"

async def get_prefilled_reservation():
    """Récupère une réservation pré-remplie via l'API."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        async with session.get(f"{BASE_URL}/new?api_key={API_KEY}", headers={"Content-Type": "application/json"}) as resp:
            return await resp.json()

async def find_servers(start, end):
    """Recherche des serveurs disponibles pour une période donnée."""
    prefilled = await get_prefilled_reservation()
    payload = {"reservation": {"starts_at": start, "ends_at": end}}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        async with session.post(f"{prefilled['actions']['find_servers']}?api_key={API_KEY}", 
                              headers={"Content-Type": "application/json"}, json=payload) as resp:
            if resp.status >= 400:
                error_data = await resp.json()
                raise Exception(f"Erreur API : {error_data.get('errors', 'Erreur inconnue')}")
            return await resp.json()

async def create_reservation(start, end, server_id, password, rcon, server_config_id=None, first_map=None):
    """Crée une réservation de serveur via l'API."""
    payload = {
        "reservation": {
            "starts_at": start,
            "ends_at": end,
            "server_id": server_id,
            "password": password,
            "rcon": rcon,
            "first_map": first_map or "cp_process_f12",
            "server_config_id": server_config_id,
            "auto_end": True,
            "enable_plugins": True,
            "enable_demos_tf": True
        }
    }
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        async with session.post(f"{BASE_URL}?api_key={API_KEY}", 
                              headers={"Content-Type": "application/json"}, json=payload) as resp:
            if resp.status == 429:
                raise Exception("Erreur : Limite de requêtes atteinte. Réessayez plus tard.")
            if resp.status >= 400:
                error_data = await resp.json()
                raise Exception(f"Erreur API : {error_data.get('reservation', {}).get('errors', 'Erreur inconnue')}")
            return await resp.json(), resp.status

async def end_reservation(reservation_id):
    """Termine une réservation via l'API."""
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        async with session.delete(f"{BASE_URL}/{reservation_id}?api_key={API_KEY}", 
                                headers={"Content-Type": "application/json"}) as resp:
            return await resp.text(), resp.status

def clean_server_name(name):
    """Remove parentheses, brackets, and extra whitespace from server names."""
    name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', name)  # Supprime ( ), [ ], { }
    return name.strip()
