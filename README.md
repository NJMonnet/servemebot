# TF2 Server Reservation Bot

This Discord bot allows users to reserve and manage Team Fortress 2 (TF2) servers for matches or practice sessions using the [serveme.tf](https://serveme.tf/) API. It provides commands to book servers, change maps, execute configurations, and indicate availability, all within a Discord server.

## Features

- **Reserve Servers**: Book a TF2 server for a 2-hour slot with `!reserve`.
- **Manage Servers**: Change maps (`!changelevel`), execute configs (`!exec`), or retrieve RCON details (`!rcon`).
- **View Reservations**: List active reservations (`!list`) or get connection details (`!connect`).
- **End Reservations**: Terminate a reservation with `!end`.
- **Indicate Availability**: Share weekly availability with `!dispo`.
- **Help Command**: Display all commands and usage with `!help`.

The bot operates in the Europe/Paris timezone and supports one active reservation per user. Users must enable DMs to receive RCON passwords.

## Prerequisites

- **Python**: Version 3.8 or higher.
- **Discord Bot Token**: Obtain from the [Discord Developer Portal](https://discord.com/developers/applications).
- **ServeMe API Key**: Obtain from [serveme.tf](https://serveme.tf/) (requires a premium account or free trial).
- **Dependencies**: Python libraries listed in `requirements.txt`.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/tf2-reservation-bot.git
   cd tf2-reservation-bot
   ```

2. **Install Python Dependencies**:
   Create a virtual environment (optional but recommended) and install required libraries:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

   The `requirements.txt` should include:
   ```
   discord.py==2.3.2
   python-rcon==1.4.0
   aiohttp==3.9.5
   python-dotenv==1.0.1
   ```

3. **Set Up the Discord Bot**:
   - Create a bot in the [Discord Developer Portal](https://discord.com/developers/applications).
   - Enable the following bot permissions: `Send Messages`, `Embed Links`, `Add Reactions`, `Read Message History`.
   - Copy the bot token for configuration.

## Configuration

1. **Create a `.env` File**:
   In the project root, create a file named `.env` and add the following:
   ```bash
   DISCORD_BOT_TOKEN=your-bot-token-here
   SERVEME_API_KEY=your-serveme-api-key-here
   ```

   - **DISCORD_BOT_TOKEN**: Get this from the Discord Developer Portal after creating your bot.
   - **SERVEME_API_KEY**: Obtain from [serveme.tf](https://serveme.tf/) by logging in, navigating to your profile, and generating an API key (requires a premium account or free trial).

2. **Customize `config.py`** (Optional):
   Modify `config.py` to adjust additional settings:
   - **TIMEZONE**: Set to your preferred timezone (default: `Europe/Paris`).
     ```python
     TIMEZONE = pytz.timezone("Europe/Paris")
     ```
   - **DEFAULT_RCON**: Default RCON password for servers (default: `fishrcon`).
     ```python
     DEFAULT_RCON = "fishrcon"
     ```
   - **SERVER_CONFIG_FILES**: List of TF2 config files (e.g., `etf2l_6v6_5cp`, `etf2l_6v6_koth`).
   - **AVAILABLE_MAPS**: List of supported TF2 maps (e.g., `cp_process_f12`, `koth_product_final`).

3. **Verify Permissions**:
   Ensure the bot has the necessary permissions in your Discord server (e.g., send messages, add reactions). Invite the bot using the invite link from the Developer Portal.

## Running the Bot

1. **Start the Bot**:
   From the project directory, run:
   ```bash
   python bot.py
   ```

2. **Verify the Bot is Online**:
   - Check if the bot appears online in your Discord server.
   - Run `!help` in a channel to confirm the bot responds.

## Usage

1. **Test the Bot**:
   - Run `!help` to see all available commands.
   - Example: Reserve a server immediately:
     ```bash
     !reserve now
     ```
   - Example: Check active reservations:
     ```bash
     !list
     ```

2. **Common Commands**:
   - `!reserve 20:00 pass`: Reserve a server for 8:00 PM with a custom password.
   - `!changelevel cp_process_f12`: Change the server map to `cp_process_f12`.
   - `!dispo`: Indicate your availability for the week by reacting to day-specific messages.
   - `!rcon`: Receive the RCON password via DM.

3. **Notes**:
   - Ensure your DMs are open to receive RCON details.
   - Only one reservation per user is allowed at a time.
   - Use `!end` to terminate a reservation early.
   - The bot interacts with serveme.tf to reserve servers, so a valid `SERVEME_API_KEY` is required.

## Troubleshooting

- **Bot Not Responding**:
  - Check `bot_output.log` or console for errors.
  - Verify `DISCORD_BOT_TOKEN` and `SERVEME_API_KEY` in `.env` are correct.
  - Ensure the bot has the required permissions in the Discord server.

- **API Errors**:
  - Confirm your `SERVEME_API_KEY` is valid and that [serveme.tf](https://serveme.tf/) is reachable.
  - Check for network issues or rate limits from the ServeMe API.

- **Rate Limit Issues**:
  - If the bot is slow to add reactions, increase the `asyncio.sleep` delay in `commands/reservation.py` or `commands/utility.py` (e.g., from 0.1 to 0.2 seconds).
    ```python
    await asyncio.sleep(0.2)
    ```
