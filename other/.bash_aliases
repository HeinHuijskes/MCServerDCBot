# Add password after: `rcon 'YOURPASSWORD'`
alias rcon='mcrcon -H 127.0.0.1 -P 25575 -p'

alias bot='sudo systemctl restart minecraft-discord-bot.service && "Done starting bot."'
alias mc='sudo systemctl restart minecraft && echo "Done starting minecraft."'
alias mcbackup='sudo systemctl start mc-backup.service && "Done making server backup."'

alias logbot='sudo systemctl status minecraft-discord-bot.service | head -7 && sudo journalctl -u minecraft-discord-bot.service -f'
alias logmc='sudo systemctl status minecraft | head -7 && sudo journalctl -u minecraft -f'
alias logbu='sudo systemctl status mc-backup.service | head -7 && sudo journalctl -u mc-backup.service -f'

alias cdbot='cd $HOME/Projects/MCServerDCBot'
alias cdmc='cd /opt/minecraft/server'

alias mcsize='sudo du -sh /opt/minecraft/server && echo "Details:" && sudo du -sh /opt/minecraft/server/world* \
    /opt/minecraft/server/libraries /opt/minecraft/server/cache /opt/minecraft/server/paper.jar \
    /opt/minecraft/server/versions /opt/minecraft/server/plugins /opt/minecraft/server/logs \
    && df -h /'

alias health='vcgencmd measure_temp && vcgencmd get_throttled'

alias report='echo "UFW" && sudo ufw status verbose && echo "Fail2Ban" && sudo fail2ban-client status sshd \
    && echo "" && echo "Cloudeflare" && sudo systemctl status cloudflared | head -7'

alias pioff='shutdown -h now'