## MESSAGES ##
MSG_NO_PERMISSION = "❌ **You don't have permission to use this command.**"
MSG_ONLINE = "🟢 **Minecraft server is online!**"
MSG_STARTING = "🟡 **Server is booting up...**"
MSG_OFFLINE = "🔴 **Minecraft server is currently offline.**"
MSG_SHUTDOWN = "🔴 **Minecraft server has shut down due to inactivity.**"
MSG_CONFIRM_SHUTDOWN = "⚠️ **Are you sure you want to shut down Minecraft?**\n" \
    "The world will be saved before the server stops."

MSG_RULES = "📜 **Minecraft Server Rules**\n\n"
MSG_COMMANDS = "📋 Bot Commands"
MSG_HOWTO = "🌍 How to Join"
MSG_HELP = "🤖 Minecraft Server Help"
MSG_SPARK = "📊 **Live Spark Health Dashboard:**\n"
MSG_TOO_LONG = "❌ Your message is too long. Maximum length is 500 characters."

def MSG_FAIL(e):
    return f"❌ Action failed: `{e}`"
