
## Configuration reference

### Environment variables
| Variable name | Obtained at | Explanation | 
|---|---|---|
| DISCORD_TOKEN | Discord Developer Portal | Bot authentication token, generated |
| RCON_HOST | Default value in `.env.example` | MCRCON IP (`127.0.0.1` when run locally) |
| RCON_PORT | Default value in `.env.example` | MCRCON IP (standard `25575`) |
| RCON_PASSWORD | Configured with mcrcon | Password used to connect to MCRCON |
| DISCORD_USER_ID | Discord (Developer Mode enabled) | ID of the owner of the Discord server |
| DISCORD_CHANNEL_ID | Discord Server | ID of the channel the bot will be sending responses in |
| DISCORD_ROLE_ID | Discord Server | ID of MC Player role |
| DEV_ROLE_ID | Discord Server | ID of dev role |
| MAP_URL | DNS Configuration | URL that points to the Pi, where Nginx redirects it to the local squaremap URL |

### Other values
Besides `.env`, a few values live in the code:

| Setting | Where | Default |
|---|---|---|
| Minecraft service name | `SERVICE_NAME` in `mcbot/minecraft.py` | `minecraft.service` |
| Minecraft server folder | `SERVER_DIR` in `mcbot/misc.py` | `/opt/minecraft/server` |
| Server log file | `LOG_FILE` in `mcbot/misc.py` | `/opt/minecraft/server/logs/latest.log` |
| Inactivity limit | `INACTIVITY_LIMIT` in `bot.py` | `900` seconds |
| Webhook name for server events | `CHAT_WEBHOOK_NAME` in `mcbot/misc.py` | `Minecraft` |
| Icon of that webhook (optional) | `info/server_icon.png` | not set |

The world folder is read from `level-name` in `server.properties`. Both the older (`world/advancements`) and newer (`world/players/advancements`) save layouts are supported.
