
## Auto-deploy with GitHub Actions

Every push to `main` (or a manual run via the "Run workflow" button) deploys to the Pi. The workflow in `.github/workflows/deploy.yml` does this:

1. **Joins your Tailscale network** as a temporary node tagged `tag:ci`, so the Pi never needs to be exposed to the internet.
2. **Sets up SSH** with a private key and a pinned host key from the repository secrets.
3. **Connects to the Pi** and runs `git pull --ff-only origin main`, then restarts `minecraft-discord-bot.service`.

The workflow only has read access to the repository (`permissions: contents: read`).

### Repository secrets

Add these under **Settings → Secrets and variables → Actions**:

| Secret | Contents |
|---|---|
| `TS_OAUTH_CLIENT_ID` | Tailscale OAuth client ID |
| `TS_OAUTH_SECRET` | Tailscale OAuth client secret |
| `PI_HOST` | The Pi's Tailscale name or IP address |
| `PI_SSH_PRIVATE_KEY` | The private half of a dedicated deploy key |
| `PI_SSH_KNOWN_HOSTS` | The Pi's host key line (see below) |

### One-time setup

1. **Tailscale.** In the admin console, define the tag in your ACL (`tagOwners` for `tag:ci`) and add a rule that lets `tag:ci` reach the Pi on port 2222. Then create an **OAuth client** with the *Auth Keys (write)* scope for that tag and put its ID and secret in the secrets above.
2. **Deploy key.** Create a key used only for deployment:
   ```bash
   ssh-keygen -t ed25519 -f mcbot_deploy -C "github-actions-deploy" -N ""
   ```
   Append `mcbot_deploy.pub` to `~/.ssh/authorized_keys` on the Pi (prefixing the line with `restrict` is a good idea), and paste the contents of the private file `mcbot_deploy` into `PI_SSH_PRIVATE_KEY`. Delete both files afterwards.
3. **Host key.** From a machine on your tailnet, run `ssh-keyscan -p 2222 -t ed25519 <PI_HOST>` and put the output line in `PI_SSH_KNOWN_HOSTS`. To be sure it is genuine, compare its fingerprint with `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` on the Pi.
4. **On the Pi.** The repository must be cloned at `/home/admin/Projects/MCServerDCBot`, SSH must listen on port 2222, and the `sudoers` rule from [Run the bot](#4-run-the-bot) must exist. If the repository is private, give the Pi a read-only deploy key on GitHub so `git pull` works.

The user, port and path are written out in the workflow file (`admin`, `2222`, `/home/admin/Projects/MCServerDCBot`). Edit them there if yours differ.

Because a push to `main` restarts the live bot, test risky changes on a branch first. The workflow does not run for other branches.
