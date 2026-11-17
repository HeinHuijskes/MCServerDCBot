
## Network configuration
Assuming the following: Cloudflare is used as a DNS server to route traffic from a set IP (e.g. [map.example.com]()) into the Pi. Nginx is used to reroute traffic within the Pi and serve webpages.

### Create backup page

Add any small html page with a "map offline" message.
```
sudo mkdir -p /var/www/minecraft-status
sudo nano /var/www/minecraft-status/offline.html
sudo chown -R www-data:www-data /var/www/minecraft-status
```

### Configure nginx
```
nano /etc/nginx/sites-available/map.example.com
```
Add this configuration (or a different port from `8081` that is free). Replace `8080` if squaremap runs on a different port.
```
server {
    listen 127.0.0.1:8081;
    server_name map.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_intercept_errors on;
        error_page 502 503 504 = /offline.html;
    }

    location = /offline.html {
        root /var/www/minecraft-status;
        internal;
    }
}
```
Symlink into nginx sites-enabled. Also make sure `sites-enabled` is included in `nginx.conf` if it is a fresh install.
```
sudo ln -s /etc/nginx/sites-available/map.heinh.nl /etc/nginx/sites-enabled/
```
Check for errors, then reload.
```
sudo nginx -t
sudo systemctl reload nginx
```

### Configure cloudflare
Edit the cloudflare config: 
```
nano /etc/cloudflared/config.yml
``` 
Add the following to it:
```
  - hostname: map.example.com
    service: http://localhost:8081
```
or use any other port than `8081` that is free and that nginx can listen on.

```
sudo systemctl restart cloudflared
```