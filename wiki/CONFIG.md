
## Configuration reference

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
