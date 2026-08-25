from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from host_monitor.config import load_config
from host_monitor.openclaw_hook import post_openclaw_analysis_hook, should_request_analysis_approval
from host_monitor.report import post_discord_report, render_discord_report
from host_monitor.snapshot import build_snapshot, save_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="host-monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_config_arg(subparsers.add_parser("daily", help="Collect, save, and send the daily health report"))
    snapshot_parser = subparsers.add_parser("snapshot", help="Collect and save a snapshot")
    _add_config_arg(snapshot_parser)
    snapshot_parser.add_argument("--json", action="store_true", help="Print snapshot JSON to stdout")
    _add_config_arg(subparsers.add_parser("config-test", help="Show configured paths and available checks"))

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "config-test":
        print(json.dumps(config_test(config), indent=2, sort_keys=True))
        return 0

    snapshot = build_snapshot(config)
    save_snapshot(snapshot, config.storage.snapshot_dir)

    if args.command == "snapshot":
        if args.json:
            print(json.dumps(snapshot.as_dict(), indent=2, sort_keys=True))
        else:
            print(snapshot.snapshot_path)
        return 0

    report = render_discord_report(snapshot, config)
    webhook_url = config.alerting.discord_webhook_url
    if webhook_url:
        post_discord_report(report, webhook_url)
    else:
        print(report)
    if should_request_analysis_approval(snapshot, config):
        try:
            post_openclaw_analysis_hook(snapshot, config)
        except Exception as exc:
            print(f"Warning: could not call OpenClaw analysis hook: {exc}", file=sys.stderr)
    return 0


def config_test(config) -> dict[str, object]:
    import shutil

    return {
        "state_path": str(config.storage.state_path),
        "snapshot_dir": str(config.storage.snapshot_dir),
        "docker_enabled": config.docker.enabled,
        "docker_cli_found": shutil.which("docker") is not None,
        "sensors_enabled": config.sensors.enabled,
        "temperature_sensors_supported": hasattr(__import__("psutil"), "sensors_temperatures"),
        "fan_sensors_supported": hasattr(__import__("psutil"), "sensors_fans"),
        "nvidia_smi_found": shutil.which("nvidia-smi") is not None,
        "discord_webhook_env": config.alerting.discord_webhook_url_env,
        "discord_webhook_configured": bool(config.alerting.discord_webhook_url),
        "openclaw_analysis_hook_enabled": config.alerting.openclaw_analysis_hook_enabled,
        "openclaw_hook_url_env": config.alerting.openclaw_hook_url_env,
        "openclaw_hook_url_configured": bool(config.alerting.openclaw_hook_url),
        "openclaw_hook_token_env": config.alerting.openclaw_hook_token_env,
        "openclaw_hook_token_configured": bool(config.alerting.openclaw_hook_token),
        "openclaw_discord_channel_env": config.alerting.openclaw_discord_channel_env,
        "openclaw_discord_channel_configured": bool(config.alerting.openclaw_discord_channel),
        "disk_mounts": config.host.disk_mounts,
    }


def _add_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None, help="Path to config TOML")


if __name__ == "__main__":
    raise SystemExit(main())
