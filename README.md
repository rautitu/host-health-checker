# host-health-checker

Small cron-friendly Linux host health monitor that writes a JSON snapshot and sends a compact daily Discord report.

The first version is intentionally report-only: it does not kill, restart, or repair anything automatically.

## What It Checks

- hostname, timestamp, uptime, and load average
- average CPU and max single-core CPU
- per-core CPU usage, so one saturated core is not hidden by a low average
- memory and swap usage
- top CPU and memory processes
- disk and inode usage for configured mount points
- Docker container stats, health, status, and restart count changes when Docker is available

## Install For Local Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

## Deploy On A Host

The easiest path is the install script:

```bash
git clone https://github.com/tonnomolt/host-health-checker.git
cd host-health-checker
sudo deploy/install.sh --install-apt-deps --install-cron --discord-webhook-url 'https://discord.com/api/webhooks/...'
```

The script:

- copies the app to `/opt/host-monitor`
- creates `/opt/host-monitor/.venv`
- installs the Python package into that venv
- creates `/etc/host-monitor/config.toml` if it does not already exist
- writes `/etc/host-monitor/env` for the Discord webhook
- creates `/var/lib/host-monitor` and `/var/log/host-monitor/snapshots`
- optionally installs `/etc/cron.d/host-monitor`

It does not overwrite an existing `config.toml`.

After install, test manually:

```bash
sudo /opt/host-monitor/run-daily.sh
```

Edit config here:

```bash
sudoedit /etc/host-monitor/config.toml
```

Edit the webhook env here:

```bash
sudoedit /etc/host-monitor/env
```

For all options:

```bash
deploy/install.sh --help
```

### Webhook Env File

`deploy/install.sh` creates `/etc/host-monitor/env` automatically if it does not exist. It contains:

```bash
HOST_MONITOR_DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

If `--discord-webhook-url` is omitted on first install, the file is still created with an empty value. Add the URL later with `sudoedit /etc/host-monitor/env`, or rerun the installer with `--discord-webhook-url`.

`/opt/host-monitor/run-daily.sh` loads this env file before running the health check.

## Commands

```bash
python -m host_monitor config-test --config config.example.toml
python -m host_monitor snapshot --config config.example.toml --json
python -m host_monitor daily --config config.example.toml
```

`daily` sends to Discord when the environment variable configured by `discord_webhook_url_env` is set. Without a webhook, it prints the report to stdout.

```bash
export HOST_MONITOR_DISCORD_WEBHOOK='https://discord.com/api/webhooks/...'
python -m host_monitor daily --config /etc/host-monitor/config.toml
```

## Cron

The install script can create `/etc/cron.d/host-monitor`:

```bash
sudo deploy/install.sh --install-cron
```

For a manual user crontab, run `crontab -e`:

```cron
HOST_MONITOR_DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
0 9 * * * /opt/host-monitor/.venv/bin/python -m host_monitor daily --config /etc/host-monitor/config.toml >> /var/log/host-monitor/cron.log 2>&1
```

See `deploy/` for cron and optional systemd timer examples.

## Optional Systemd Timer

Copy the example units, edit the webhook environment value, then enable the timer:

```bash
sudo cp deploy/host-monitor.service deploy/host-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now host-monitor.timer
sudo systemctl list-timers host-monitor.timer
```

Run once manually:

```bash
sudo systemctl start host-monitor.service
sudo journalctl -u host-monitor.service -n 100 --no-pager
```

## Config

Copy `config.example.toml` and adjust paths and thresholds. Production-ish default paths are:

- config: `/etc/host-monitor/config.toml`
- state: `/var/lib/host-monitor/state.json`
- snapshots: `/var/log/host-monitor/snapshots/`
- cron log: `/var/log/host-monitor/cron.log`

For local development, `config.example.toml` stores state and snapshots under `./var/`.

Real local config files named `config.toml` are ignored by git. Keep secrets such as Discord webhook URLs in environment variables or `/etc/host-monitor/env`, not in `config.example.toml`.
