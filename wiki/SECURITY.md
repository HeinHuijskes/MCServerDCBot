
## Security

**Secrets and configuration**
- `.env` and `info/*.txt` are in `.gitignore`. Only placeholder templates (`.env.example`, `*.example`) are committed.
- Missing required settings stop the bot at startup with a clear message, instead of failing halfway through a command.

**Access control**
- Role checks run on the bot side for every command. Hiding commands in `/help` is only cosmetic; the check itself is what protects them.
- Admin groups (`/whitelist`, `/time`) are protected as a whole, so a command added to them later cannot be forgotten. The name autocomplete for player lookups is checked as well, because Discord does not apply command checks to autocomplete requests.
- The shutdown confirmation button checks the dev role again when it is pressed.
- Role-gated commands are limited to servers and are not available in DMs.
- Note that the owner (`DISCORD_USER_ID`) passes every role check.

**Input handling**
- Player names are validated before being placed in an RCON command, so they cannot carry extra commands.
- `/godtext` and Discord → Minecraft chat are sent as JSON text components through `tellraw`, so user text can never be interpreted as a command or as formatting. Lengths are capped.
- Minecraft → Discord messages are sent with mentions disabled, so typing `@everyone` in-game cannot ping anyone, and Markdown is escaped.

**RCON**
- RCON defaults to `127.0.0.1`. It gives full console access, so keep it off the internet: do not port-forward 25575, use a long random password, and keep `server.properties` readable only by the users that need it.

**Deployment**
- The deploy job has read-only repository permissions, joins your tailnet as a temporary tagged node, and the Pi is not reachable from the public internet.
- SSH uses a dedicated key (key-only, `BatchMode`), a pinned host key (`StrictHostKeyChecking=yes`) and a non-default port.
- The Pi only fast-forwards (`git pull --ff-only`), so the deploy cannot rewrite or merge anything on the Pi.
- The restart goes through `sudo -n` for one specific command, which is meant to be allowed through a narrow `sudoers` rule rather than blanket sudo.

**Recommended host hardening** (this is outside what the repository enforces):
- SSH: key-only login, password login disabled, and no root login.
- A firewall that only allows the Minecraft port publicly (for example `ufw` with 25565 open and 25575 closed), plus `fail2ban` or similar if SSH is reachable from outside the tailnet.
- Run Minecraft under its own unprivileged user, and turn on automatic security updates.
- Two-factor authentication on your GitHub and Discord developer accounts. If the bot token ever leaks, reset it in the Developer Portal right away.
- Consider pinning dependency versions and the GitHub Action to commit SHAs if you want reproducible, tamper-resistant builds.


## Privacy and external services

- The chat relay copies in-game chat and server messages into a Discord channel, so only give that channel to people who are fine with seeing them. The relay also posts other server system messages (such as plugin broadcasts), not just chat.
- Player head images are loaded from [mc-heads.net](https://mc-heads.net) using the player name, both by the bot (for emojis) and by Discord (for webhook avatars). That third-party service therefore sees those player names. You can change the address in `head_url()` in `mcbot/misc.py` to use another skin service.
- Offline-mode servers and Bedrock/Floodgate names will show a default skin.