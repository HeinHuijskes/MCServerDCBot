#!/usr/bin/env bash
#
# mc-backup.sh — back up the Minecraft server + Discord bot + related configs
# to a cloud remote via rclone, then prune old backups.
#
# WHAT THIS DOES
#   1. Checks whether the Minecraft service is running. If it IS running,
#      this run is skipped (logged as a warning) rather than copying files
#      that the server might be writing to mid-backup — the daily timer will
#      just catch up on a later run when the server happens to be offline.
#      If you'd rather back up anyway even while the server is online
#      (small risk of an inconsistent world copy), see SKIP_IF_RUNNING below.
#   2. Tars up the folders/files listed in BACKUP_PATHS (minus EXCLUDES).
#   3. Uploads the tarball to the rclone remote in RCLONE_REMOTE.
#   4. Deletes the local tarball immediately (keeps the Pi's own disk usage flat).
#   5. Deletes remote backups older than the newest RETAIN copies.
#
# ---------------------------------------------------------------------------
# >>> EDIT EVERYTHING IN THIS CONFIG SECTION FOR YOUR ACTUAL PATHS/SETUP <<<
# I don't have access to your Pi, so these are placeholders based on your
# README (SERVER_DIR = the Paper server folder, plus the bot's own project
# directory and the nginx/cloudflared configs you mentioned).
# ---------------------------------------------------------------------------

# Where backups go. Run `rclone config` once first to set this remote up
# (Backblaze B2, S3, Google Drive, etc. all work the same way after that).
RCLONE_REMOTE="myremote:minecraft-backups"

# Full path to the rclone.conf that actually has that remote in it. Find it
# with `rclone config file` while logged in as the user who ran `rclone config`
# (commonly ~/.config/rclone/rclone.conf). This is set explicitly because the
# backup service may run as root, which otherwise looks in /root/ instead.
RCLONE_CONFIG_PATH="/home/admin/.config/rclone/rclone.conf"

# How many of the most recent backups to keep on the remote.
RETAIN=5

# The Minecraft systemd service name (from your README: minecraft.service)
MC_SERVICE="minecraft.service"

# true  = skip this run (and warn) if the server happens to be online —
#         safest, just copies files straight off disk when it's offline.
# false = back up anyway even if the server is online. Paper writes region
#         files in whole chunks, so the risk is low, but not zero.
SKIP_IF_RUNNING=true

# Absolute paths to back up. Adjust to match your actual install.
BACKUP_PATHS=(
  "/opt/minecraft/server/world"
  "/opt/minecraft/server/world_nether"
  "/opt/minecraft/server/world_the_end"
  "/opt/minecraft/server/whitelist.json"
  "/opt/minecraft/server/usercache.json"
  "/opt/minecraft/server/ops.json"
  "/opt/minecraft/server/server.properties"
  "/opt/minecraft/server/plugins"
  "/home/admin/Projects/MCServerDCBot/.env"
  "/home/admin/Projects/MCServerDCBot/info"
  "/etc/nginx/sites-available"
  "/etc/cloudflared"
)

# tar --exclude patterns, mainly to skip large/regenerable cache data
# (map tile caches especially can be huge — squaremap/chunky both cache tiles).
EXCLUDES=(
  "--exclude=plugins/squaremap/web"
  "--exclude=plugins/squaremap/tiles"
  "--exclude=plugins/Chunky/cache"
  "--exclude=logs"
  "--exclude=crash-reports"
  "--exclude=*/cache/*"
)

# ---------------------------------------------------------------------------
# No need to edit below this line.
# ---------------------------------------------------------------------------

set -euo pipefail

TIMESTAMP="$(date +%Y-%m-%d_%H-%M-%S)"
ARCHIVE_NAME="mc-backup-${TIMESTAMP}.tar.gz"
STAGING_DIR="$(mktemp -d)"
ARCHIVE_PATH="${STAGING_DIR}/${ARCHIVE_NAME}"

log() { echo "[mc-backup] $*"; }

cleanup() {
    rm -rf "${STAGING_DIR}"
}
trap cleanup EXIT

SERVER_RUNNING=false
if systemctl is-active --quiet "${MC_SERVICE}"; then
    SERVER_RUNNING=true
fi

if [ "${SERVER_RUNNING}" = true ] && [ "${SKIP_IF_RUNNING}" = true ]; then
    log "WARNING: ${MC_SERVICE} is running — skipping this backup to avoid copying files mid-write."
    log "It will run normally next time it finds the server offline."
    exit 0
fi

if [ "${SERVER_RUNNING}" = true ]; then
    log "WARNING: ${MC_SERVICE} is running and SKIP_IF_RUNNING=false — backing up anyway."
fi

export RCLONE_CONFIG="${RCLONE_CONFIG_PATH}"

log "Creating archive ${ARCHIVE_NAME}"
# --ignore-failed-read: don't abort the whole backup just because one listed
# path doesn't exist right now (e.g. world_nether/world_the_end before anyone
# has visited them yet). Real permission errors will still show up in the log.
tar czf "${ARCHIVE_PATH}" --ignore-failed-read "${EXCLUDES[@]}" "${BACKUP_PATHS[@]}" 2>&1 \
    | grep -v "Removing leading" || true

log "Uploading to ${RCLONE_REMOTE}"
rclone copy "${ARCHIVE_PATH}" "${RCLONE_REMOTE}" --progress

log "Pruning remote backups, keeping the newest ${RETAIN}"
mapfile -t REMOTE_BACKUPS < <(rclone lsf "${RCLONE_REMOTE}" --files-only | grep '^mc-backup-' | sort)
COUNT="${#REMOTE_BACKUPS[@]}"
if [ "${COUNT}" -gt "${RETAIN}" ]; then
    TO_DELETE=$((COUNT - RETAIN))
    for i in $(seq 0 $((TO_DELETE - 1))); do
        OLD_FILE="${REMOTE_BACKUPS[$i]}"
        log "Deleting old remote backup: ${OLD_FILE}"
        rclone deletefile "${RCLONE_REMOTE}/${OLD_FILE}"
    done
fi

log "Done."