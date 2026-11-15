## MESSAGES ##
MSG_NO_PERMISSION = "❌ **You don't have permission to use this command.**"
MSG_ONLINE = "🟢 **Minecraft server is online!**"
MSG_STARTING = "🟡 **Server is booting up...**"
MSG_OFFLINE = "🔴 **Minecraft server is currently offline.**"
MSG_SHUTDOWN = "🔴 **Minecraft server has shut down due to inactivity.**"
MSG_SHUT_CMD = "🟡 Sending shutdown command..."
MSG_SHUTTING = "**Shutdown command sent!** Minecraft is saving the world and shutting down."
MSG_NO_SHUT = "Shutdown cancelled."
MSG_CONFIRM_SHUTDOWN = "⚠️ **Are you sure you want to shut down Minecraft?**\n" \
    "The world will be saved before the server stops."

MSG_HELP = "🤖 **Minecraft Server Help**"
MSG_HOWTO = "🌍 **How to Join**"
MSG_RULES = "📜 **Minecraft Server Rules**\n\n"
MSG_SPARK = "📊 **Live Spark Health Dashboard:**\n"
MSG_COMMANDS = "📋 **Bot Commands**"
MSG_WHITELIST = "📋 **Minecraft Whitelist:**\n"

MSG_TOO_LONG = "❌ Your message is too long. Maximum length is 500 characters."
MSG_INVALID = "Invalid input."

def MSG_SUCCEED(msg):
    return f"✅ Action success:\n`{msg or 'Command excuted.'}`"
def MSG_FAIL(e):
    return f"❌ Action failed:\n`{e}`"
