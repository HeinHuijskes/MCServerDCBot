## Troubleshooting

| Problem | What to check |
|---|---|
| Bot exits with `Missing required .env variables` | Fill in the listed variables in `.env`. ID values must be plain numbers, not the `<ID>` placeholders |
| Slash commands do not appear | Wait a moment and restart Discord. Check the logs for errors during startup |
| `Connection refused` in the logs right after starting the server | Normal. RCON opens a while after the process starts. The bot treats this as "still booting" |
| `/serverstatus` always says the server is booting | RCON is not reachable. Check `enable-rcon`, the port and that the password matches `.env` |
| Chat relay does nothing | Is `DISCORD_CHAT_CHANNEL_ID` set? Is the **Message Content Intent** enabled? Can the bot read `logs/latest.log`? |
| Joins, deaths or chat are not recognised | The parser expects Paper's log format. The patterns are at the top of `mcbot/chat.py`; compare them with a real line from your log |
| Chat shows as the bot instead of the player | The bot needs the **Manage Webhooks** permission in the channel; check the logs for a warning |
| `/advanced` or `/time` say the data cannot be read | The bot cannot read the world folder. Check file permissions and the world's `advancements` / `stats` folders |
| Stats lag behind | Minecraft writes these files on autosave and when a player leaves. `/save-all` forces it |
| Player is missing from name suggestions | Suggestions only include players who have actually joined, not names that were only whitelisted |
| `/serverrules` or `/help` show an empty section | The files in `info/` are missing. Copy them from the `.example` files |
| Deploy workflow fails | Check that the Tailscale ACL allows `tag:ci` to reach port 2222, that `PI_SSH_KNOWN_HOSTS` matches the Pi, and that the `sudoers` rule exists |

Logs: `journalctl -u minecraft-discord-bot.service -f` (bot) and `/opt/minecraft/server/logs/latest.log` (Minecraft).