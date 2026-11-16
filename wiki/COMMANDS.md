
## Commands

Access levels: **everyone**, **MC Player** (the player role) and **dev** (the dev role). The owner (`DISCORD_USER_ID`) passes both role checks. Role-gated commands only work inside a server, not in DMs.

| Command | Access | What it does |
|---|---|---|
| `/help` | everyone | Lists the commands you can use plus the joining instructions. Devs also get a private (only visible to them) list of dev commands |
| `/serverrules` | everyone | Shows the server rules |
| `/serverstatus` | MC Player | Shows whether the server is online and who is playing, with head icons |
| `/startserver` | MC Player | Starts the server and announces when it is ready |
| `/advanced show <player>` | MC Player | A player's advancement progress and their 5 most recent advancements |
| `/advanced top` | MC Player | Advancement leaderboard (top 10) |
| `/shutdown` | dev | Stops the server after a confirmation button |
| `/sparkhealth` | dev | Posts a Spark health report link |
| `/godtext <message>` | dev | Sends an announcement to all players in-game (max 500 characters) |
| `/whitelist add\|remove\|list` | dev | Manages the whitelist |
| `/time show <player>` | dev | A player's total playtime |
| `/time top` | dev | Playtime leaderboard (top 10) |

Commands that need the server to be running (`/shutdown`, `/sparkhealth`, `/godtext`, `/whitelist ...`) tell you when it is offline.

**Chat relay.** With `DISCORD_CHAT_CHANNEL_ID` set, the bot mirrors everything between that channel and in-game chat. Messages typed in the channel appear in-game as `[Discord] Name: message`. Player chat appears in Discord under the player's name and head; join, leave, advancement, death and other server messages are posted as "Minecraft". Command feedback and the bot's own relayed lines are filtered out so nothing loops.

**Auto-shutdown.** When nobody has been online for 15 minutes, the bot stops the server through RCON and posts a notice in the notification channel.
