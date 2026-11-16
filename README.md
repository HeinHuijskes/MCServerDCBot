# Minecraft Discord Bot

A Discord bot that manages a [Paper](https://papermc.io) Minecraft server running on a Raspberry Pi. Start and stop the server, manage the whitelist, mirror in-game chat into Discord (and back), and look up player stats, all from Discord slash commands.

## Contents

- [Features](#features)
- [About the author](#about-the-author)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Requirements](#requirements)

## Wiki
The `wiki/` folder contains a lot of additional information about different parts of the system, such as:

- [Setup](./wiki/SETUP.md)
  - [1. The Minecraft server](./wiki/SETUP.md#1-the-minecraft-server-paper)
  - [2. The Discord application](./wiki/SETUP.md#2-the-discord-application)
  - [3. Install the bot after cloning](./wiki/SETUP.md#3-install-the-bot-after-cloning)
  - [4. Run the bot](./wiki/SETUP.md#4-run-the-bot)
- [Commands](./wiki/COMMANDS.md#commands)
- [Auto-deploy with GitHub Actions](./wiki/DEPLOY.md#auto-deploy-with-github-actions)
- [Configuration reference](./wiki/CONFIG.md#configuration-reference)
- [Security](./wiki/SECURITY.md#security)
  - [Privacy and external services](./wiki/SECURITY.md#privacy-and-external-services)
- [Troubleshooting](./wiki/DEBUG.md#troubleshooting)

## Features

- **Server control**: start the server on demand, check its status and who is online (with player head icons), shut it down with a confirmation step, and let it stop itself after 15 minutes with nobody online.
- **Two-way chat relay**: in-game chat shows up in a Discord channel under the player's name and head, and Discord messages show up in-game. Joins, leaves, advancements, deaths (with a skull) and other server messages are relayed too.
- **Player stats**: advancement progress and a leaderboard, plus playtime for devs.
- **Admin tools**: whitelist management, in-game announcements, and a Spark performance report.
- **Role-based access**: separate roles for players and devs, and `/help` adapts to who is asking.
- **Auto-deploy**: pushing to `main` updates the bot on the Pi and restarts it.

## About the author

Hi, I'm **Hein Huijskes**, the creator and maintainer of this project.

I built it to run a private Minecraft server for friends on a Raspberry Pi 4 at home, and to be able to manage that server from Discord instead of logging in to the Pi. It started as a handful of commands and grew feature by feature: chat relay, stats, automated deployment. It is a personal project written for my own setup, but I have tried to keep it configurable and documented so that others can adapt it to theirs.

This project was built with assistance of AI, ChatGPT initially and Claude later on. The creative vision is still my own, but usage of AI tools helped realize this much faster. Also big thanks to Jurre and his bot for being a ton of the original inspiration for this bot.

## How it works

```
 Discord <───> Bot ─── RCON (localhost) ───> Paper server
                └── (minecraft.service)
                       ├── systemctl: start the server / check if it is running
                       └── reads from the server folder:
                           logs/latest.log  → chat relay
                           whitelist.json, usercache.json → player names
                           world/.../advancements, stats  → /advanced, /time
```

- **Commands** are sent to Minecraft through [RCON](https://minecraft.wiki/w/RCON) on the same machine.
- **The server process** is a systemd service (`minecraft.service`). The bot starts it with `systemctl` and asks systemd whether it is running.
- **Chat relay (Minecraft → Discord)** works by following `logs/latest.log`, so it needs no Minecraft plugin. Discord → Minecraft uses RCON `tellraw`.
- **Stats** are read directly from the world's save files, so they need no extra tracking.

## Project structure

```
bot.py                    Entry point: all slash commands and background tasks
mcbot/
  __init__.py             Project root path + loads .env
  constants.py            Message strings
  misc.py                 Permission checks, config, helpers, webhooks, UI views
  minecraft.py            RCON and systemd helpers
  chat.py                 Log parser and log tailer for the chat relay
  advancements.py         Reads advancement save files and titles
  playtime.py             Reads playtime from stats files
info/
  server_info.txt.example   Template: joining instructions shown in /help
  server_rules.txt.example  Template: rules shown by /serverrules
.env.example              Template for the configuration
setup.sh                  Creates the virtual environment and installs dependencies
.github/workflows/deploy.yml   Auto-deploy to the Pi
```

`bot.py` stays in the project root so that `python bot.py` works from any directory and the service file never needs to change.

## Requirements

- A Linux machine with **systemd** (developed on a Raspberry Pi 4 with a 64-bit OS)
- **Python 3.10 or newer** (developed on 3.13) with `venv` (`sudo apt install python3-venv` on Debian-based systems)
- **discord.py 2.5 or newer** (needed for the player head emojis; `requirements.txt` is not pinned, so a fresh install gets the latest)
- A **Paper** server with RCON enabled, running as the systemd service `minecraft.service`
- A **Discord application** with a bot user



