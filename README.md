TF2 Server Reservation Bot

This Discord bot allows users to reserve and manage Team Fortress 2 (TF2) servers for matches or practice sessions. It provides commands to book servers, change maps, execute configurations, and indicate availability, all within a Discord server.

Features





Reserve Servers: Book a TF2 server for a 2-hour slot with !reserve.



Manage Servers: Change maps (!changelevel), execute configs (!exec), or retrieve RCON details (!rcon).



View Reservations: List active reservations (!list) or get connection details (!connect).



End Reservations: Terminate a reservation with !end.



Indicate Availability: Share weekly availability with !dispo.



Help Command: Display all commands and usage with !help.

The bot operates in the Europe/Paris timezone and supports one active reservation per user. Users must enable DMs to receive RCON passwords.

Prerequisites





Python: Version 3.8 or higher.



Discord Bot Token: Obtain from the Discord Developer Portal.



Dependencies: Python libraries listed in requirements.txt.



Server API: Access to a TF2 server reservation API (e.g., for find_servers and create_reservation).



RCON Access: Credentials for TF2 server control (default RCON password configurable).

Installation





Clone the Repository:

git clone https://github.com/yourusername/tf2-reservation-bot.git
cd tf2-reservation-bot



Install Python Dependencies: Create a virtual environment (optional but recommended) and install required libraries:

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

The requirements.txt should include:

discord.py==2.3.2
python-rcon==1.4.0
aiohttp==3.9.5



Set Up the Discord Bot:





Create a bot in the Discord Developer Portal.



Enable the following bot permissions: Send Messages, Embed Links, Add Reactions, Read Message History.



Copy the bot token for configuration.

Configuration

Edit the config.py file to customize the bot:





DISCORD_TOKEN: Replace with your bot token from the Discord Developer Portal.

DISCORD_TOKEN = "your-bot-token-here"



TIMEZONE: Set to your preferred timezone (default: Europe/Paris).

TIMEZONE = pytz.timezone("Europe/Paris")



DEFAULT_RCON: Default RCON password for servers (default: fishrcon).

DEFAULT_RCON = "fishrcon"



SERVER_CONFIG_FILES: List of TF2 config files (e.g., etf2l_6v6_5cp, etf2l_6v6_koth).



AVAILABLE_MAPS: List of supported TF2 maps (e.g., cp_process_f12, koth_product_final).



API Settings: Configure API endpoints for find_servers and create_reservation in utils.py if needed.

Ensure the bot has the necessary permissions in your Discord server and that the API for server reservations is accessible.

Running the Bot





Start the Bot: From the project directory, run:

python bot.py



Verify the Bot is Online:





Invite the bot to your Discord server using the invite link from the Developer Portal.



Check if the bot appears online in your server.

Usage





Test the Bot:





Run !help in a Discord channel to see all available commands.



Example: Reserve a server immediately:

!reserve now



Example: Check active reservations:

!list



Common Commands:





!reserve 20:00 pass: Reserve a server for 8:00 PM with a custom password.



!changelevel cp_process_f12: Change the server map to cp_process_f12.



!dispo: Indicate your availability for the week by reacting to day-specific messages.



!rcon: Receive the RCON password via DM.



Notes:





Ensure your DMs are open to receive RCON details.



Only one reservation per user is allowed at a time.



Use !end to terminate a reservation early.

Troubleshooting





Bot Not Responding:





Check bot_output.log or console for errors.



Verify the DISCORD_TOKEN in config.py is correct.



Ensure the bot has the required permissions in the Discord server.



API Errors:





Confirm the server reservation API is reachable and configured in utils.py.



Check for network issues or incorrect API credentials.
