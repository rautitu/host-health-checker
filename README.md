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

These commands assume a Debian/Ubuntu-style host. Other Linux distributions work too, but package names may differ.

1. Install Python venv support:

```bash
sudo apt update
sudo apt install python3 python3-venv
```

2. Put the project under `/opt/host-monitor`:

```bash
sudo mkdir -p /opt/host-monitor
sudo chown "$USER":"$USER" /opt/host-monitor
git clone https://github.com/tonnomolt/host-health-checker.git /opt/host-monitor
cd /opt/host-monitor
```

If you are deploying from an already cloned checkout, copy or pull the code into `/opt/host-monitor` instead.

3. Create the virtual environment and install the package:

```bash
python3 -m venv /opt/host-monitor/.venv
/opt/host-monitor/.venv/bin/python -m pip install --upgrade pip
/opt/host-monitor/.venv/bin/python -m pip install /opt/host-monitor
```

4. Create config, state, and log directories:

```bash
sudo mkdir -p /etc/host-monitor /var/lib/host-monitor /var/log/host-monitor/snapshots
sudo cp /opt/host-monitor/config.example.toml /etc/host-monitor/config.toml
sudo chown -R "$USER":"$USER" /var/lib/host-monitor /var/log/host-monitor
```

5. Edit `/etc/host-monitor/config.toml`.

For production paths, set:

```toml
[storage]
state_path = "/var/lib/host-monitor/state.json"
snapshot_dir = "/var/log/host-monitor/snapshots"
```

6. Configure the Discord webhook environment variable:

```bash
export HOST_MONITOR_DISCORD_WEBHOOK='https://discord.com/api/webhooks/...'
```

For cron, put that export in the cron command or in a small wrapper script. For systemd, set it in `deploy/host-monitor.service` or an EnvironmentFile.

7. Test before scheduling:

```bash
/opt/host-monitor/.venv/bin/python -m host_monitor config-test --config /etc/host-monitor/config.toml
/opt/host-monitor/.venv/bin/python -m host_monitor snapshot --config /etc/host-monitor/config.toml --json
/opt/host-monitor/.venv/bin/python -m host_monitor daily --config /etc/host-monitor/config.toml
```

If `HOST_MONITOR_DISCORD_WEBHOOK` is not set, `daily` prints the Discord report to stdout instead of sending it.

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

Install with `crontab -e`:

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
