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

Example:

```cron
0 9 * * * /opt/host-monitor/.venv/bin/python -m host_monitor daily --config /etc/host-monitor/config.toml >> /var/log/host-monitor/cron.log 2>&1
```

See `deploy/` for cron and optional systemd timer examples.

## Config

Copy `config.example.toml` and adjust paths and thresholds. Production-ish default paths are:

- config: `/etc/host-monitor/config.toml`
- state: `/var/lib/host-monitor/state.json`
- snapshots: `/var/log/host-monitor/snapshots/`
- cron log: `/var/log/host-monitor/cron.log`

For local development, `config.example.toml` stores state and snapshots under `./var/`.
