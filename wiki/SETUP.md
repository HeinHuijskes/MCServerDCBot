
## Setup

### 1. The Minecraft server (Paper)

A short pointer; the [Paper documentation](https://docs.papermc.io) covers the details.

1. Install a Java runtime that matches your Paper version (recent versions need Java 21 or newer; on Debian-based systems that is for example `openjdk-21-jre-headless`).
2. Download Paper from [papermc.io/downloads](https://papermc.io/downloads/paper) into `/opt/minecraft/server/` and start it once to generate its files. Accept the EULA by setting `eula=true` in `eula.txt`.
3. In `server.properties`, enable RCON and the whitelist:
   ```properties
   enable-rcon=true
   rcon.port=25575
   rcon.password=<a long random password>
   white-list=true
   enforce-whitelist=true
   ```
4. Create a systemd service named **`minecraft.service`**. A minimal example (adjust the user, paths and memory to your system):
   ```ini
   [Unit]
   Description=Minecraft (Paper) server
   After=network.target

   [Service]
   User=minecraft
   WorkingDirectory=/opt/minecraft/server
   ExecStart=/usr/bin/java -Xms2G -Xmx3G -jar paper.jar nogui
   Restart=on-failure

   [Install]
   WantedBy=multi-user.target
   ```
5. Make sure the **Spark** profiler works on your server (run `/spark` in-game). `/sparkhealth` depends on it; install the plugin if your Paper version does not include it.
6. **Do not forward the RCON port (25575) on your router.** Only the Minecraft port (25565) should be reachable from outside.

The bot also needs to **read** the server folder: `logs/latest.log`, `whitelist.json`, `usercache.json`, `server.properties` and the world folder. If Minecraft runs as a different user than the bot, add the bot's user to that user's group and make the files group-readable. Note that `server.properties` contains the RCON password, so it should not be world-readable.

### 2. The Discord application

1. Create an application at the [Discord Developer Portal](https://discord.com/developers/applications) and add a **Bot**. Copy its token (this becomes `DISCORD_TOKEN`).
2. Under **Bot → Privileged Gateway Intents**, enable **Message Content Intent**. It is required for the chat relay (Discord → Minecraft).
3. Invite the bot to your server with the scopes `bot` and `applications.commands`. In the channels it uses it needs these permissions: View Channel, Send Messages, Embed Links, and **Manage Webhooks** (the chat relay posts as the player through a webhook; without this permission it falls back to plain bot messages).
4. In your Discord server, create two roles: **MC Player** (may use the player commands) and **dev** (may use the admin commands). Create a channel for server notifications, and optionally a channel for the chat relay.
5. Turn on **Developer Mode** in Discord (Settings → Advanced) so you can right-click roles, channels and yourself and choose **Copy ID**. You will need these IDs below.

### 3. Install the bot after cloning

```bash
git clone https://github.com/<github-username>/MCServerDCBot.git /home/admin/Projects/MCServerDCBot
cd /home/admin/Projects/MCServerDCBot
```

The auto-deploy workflow expects the project at `/home/admin/Projects/MCServerDCBot`. If you use another location or user, update `.github/workflows/deploy.yml` as well.

**Install the dependencies.** `setup.sh` creates a virtual environment named `mcbot-venv` and installs `requirements.txt` into it:

```bash
chmod +x setup.sh
./setup.sh
```

**Create your `.env`.** This file holds your secrets and is ignored by git:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

| Variable | Required | Description |
|---|---|---|
| `DISCORD_TOKEN` | yes | The bot token from the Developer Portal |
| `RCON_PASSWORD` | yes | Must match `rcon.password` in `server.properties` |
| `RCON_HOST` | no | Defaults to `127.0.0.1` |
| `RCON_PORT` | no | Defaults to `25575` |
| `DISCORD_USER_ID` | yes | Your own Discord user ID. The owner passes every role check |
| `DISCORD_CHANNEL_ID` | yes | Channel for server notifications (server online, auto-shutdown) |
| `DISCORD_ROLE_ID` | yes | ID of the **MC Player** role |
| `DEV_ROLE_ID` | yes | ID of the **dev** role |
| `DISCORD_CHAT_CHANNEL_ID` | no | Channel for the two-way chat relay. Leave it out (or set `0`) to disable the relay |

The bot checks the required variables at startup and tells you which one is missing.

**Create your `info/` files.** These two files are the texts the bot shows to your players. They are ignored by git, so they are specific to your machine and are never overwritten by an update:

```bash
cp info/server_info.txt.example  info/server_info.txt
cp info/server_rules.txt.example info/server_rules.txt
nano info/server_info.txt
nano info/server_rules.txt
```

| File | Shown by | Notes |
|---|---|---|
| `info/server_info.txt` | The "how to join" section of `/help` | Discord markdown works. Keep it under 1024 characters; anything longer is cut off |
| `info/server_rules.txt` | `/serverrules` | Sent as a single message, so keep it under about 1900 characters |

If a file is missing, the bot still works but shows that section empty.

### 4. Run the bot

**Quick test** (stop it with Ctrl+C):

```bash
cd /home/admin/Projects/MCServerDCBot
mcbot-venv/bin/python bot.py
```

**As a service**, so it starts on boot and restarts on failure. Create `/etc/systemd/system/minecraft-discord-bot.service` (this is the name the deploy workflow restarts):

```ini
[Unit]
Description=Minecraft Discord bot
After=network-online.target
Wants=network-online.target

[Service]
User=admin
WorkingDirectory=/home/admin/Projects/MCServerDCBot
ExecStart=/home/admin/Projects/MCServerDCBot/mcbot-venv/bin/python bot.py
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now minecraft-discord-bot.service
journalctl -u minecraft-discord-bot.service -f      # follow the logs
```

The bot loads `.env` from the project folder, so the service needs no `EnvironmentFile`.

**Passwordless `sudo` for two commands.** The bot starts the Minecraft service with `sudo systemctl start minecraft.service`, and the deploy workflow restarts the bot with `sudo -n systemctl restart minecraft-discord-bot.service`. Neither can ask for a password, so allow exactly these two commands and nothing else. Create the file with `sudo visudo -f /etc/sudoers.d/mcbot`:

```
admin ALL=(root) NOPASSWD: /usr/bin/systemctl start minecraft.service
admin ALL=(root) NOPASSWD: /usr/bin/systemctl restart minecraft-discord-bot.service
```

Replace `admin` with the user that runs the bot. (Checking whether the server is running uses `systemctl is-active`, which needs no `sudo`.)

The first start registers the slash commands with Discord. They can take a short while to appear; restarting the Discord app helps.