import aiohttp
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("SERVEME_API_KEY")

HEADERS = {
    "Content-Type": "application/json"
}

BASE_URL = "https://serveme.tf/api/reservations"

async def get_prefilled_reservation():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/new?api_key={API_KEY}", headers=HEADERS) as resp:
            return await resp.json()

async def find_servers(start, end):
    prefilled = await get_prefilled_reservation()
    find_url = prefilled["actions"]["find_servers"]
    payload = {
        "reservation": {
            "starts_at": start,
            "ends_at": end
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{find_url}?api_key={API_KEY}", headers=HEADERS, json=payload) as resp:
            data = await resp.json()
            return data  # Retourne l'ensemble des données, y compris servers et server_configs

async def create_reservation(start, end, server_id, password, rcon, server_config_id=None):
    payload = {
        "reservation": {
            "starts_at": start,
            "ends_at": end,
            "server_id": server_id,
            "password": password,
            "rcon": rcon,
            "first_map": "cp_process_f12",  # Définir la carte par défaut
            "server_config_id": server_config_id  # Ajouter l'ID de la config
        }
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BASE_URL}?api_key={API_KEY}", headers=HEADERS, json=payload) as resp:
            return await resp.json(), resp.status

async def end_reservation(reservation_id):
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{BASE_URL}/{reservation_id}?api_key={API_KEY}", headers=HEADERS) as resp:
            return await resp.text(), resp.status
