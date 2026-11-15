import minecraft
import discord
from bot import has_dev_permission, no_permission, server_is_not_running


whitelist_group = discord.app_commands.Group(
    name="whitelist",
    description="Manage the Minecraft whitelist (dev only)"
)


@whitelist_group.command(name="add", description="Add a player to the whitelist")
async def whitelist_add(interaction: discord.Interaction, playername: str):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command(f"whitelist add {playername}")
        await interaction.followup.send(
            f"✅ Whitelist add result:\n```{result or 'Command executed.'}```",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to add player: `{e}`",
            ephemeral=True
        )


@whitelist_group.command(name="remove", description="Remove a player from the whitelist")
async def whitelist_remove(interaction: discord.Interaction, playername: str):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command(f"whitelist remove {playername}")
        await interaction.followup.send(
            f"✅ Whitelist remove result:\n```{result or 'Command executed.'}```",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to remove player: `{e}`",
            ephemeral=True
        )


@whitelist_group.command(name="list", description="List all whitelisted players")
async def whitelist_list(interaction: discord.Interaction):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command("whitelist list")
        if result:
            result = "".join([f"{i+1}. {name}\n" for i, name in enumerate(result.split(": ")[1].split(", "))])

        await interaction.followup.send(
            f"📋 **Minecraft Whitelist:**\n```{result or 'The whitelist is empty.'}```",
            ephemeral=True
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to retrieve whitelist: `{e}`",
            ephemeral=True
        )
