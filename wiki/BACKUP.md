
## Backups

```
sudo apt install rclone
rclone config
```
Copy the `RCLONE_REMOTE` variable into the `backup.sh` script.

Edit the placeholder paths/RCON password at the top of mc-backup.sh to match your actual install.

```
sudo cp ./backup/mc-backup.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/mc-backup.sh
sudo cp ./backup/mc-backup.service ./backup/mc-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mc-backup.timer
```
Test 
```
sudo systemctl start mc-backup.service
journalctl -u mc-backup.service
```