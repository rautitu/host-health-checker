from __future__ import annotations

import json
import urllib.request
from datetime import timedelta

from host_monitor.config import Config
from host_monitor.models import Snapshot


def render_discord_report(snapshot: Snapshot, config: Config) -> str:
    status = "OK" if not snapshot.findings else "WARN"
    lines = [
        f"**Host health: {snapshot.hostname}** `{status}`",
        f"Time: `{snapshot.generated_at}` | Uptime: `{_duration(snapshot.uptime_seconds)}`",
        f"CPU avg/max core: `{snapshot.cpu['average_percent']}% / {snapshot.cpu['max_core_percent']}%`",
        f"Memory: `{snapshot.memory['used_percent']}%` | Swap: `{snapshot.swap['used_percent']}%`",
    ]
    if snapshot.load_average:
        per_cpu = snapshot.load_average[0] / max(int(snapshot.cpu["core_count"]), 1)
        lines.append(f"Load 1/5/15: `{snapshot.load_average[0]:.2f} {snapshot.load_average[1]:.2f} {snapshot.load_average[2]:.2f}` | per CPU: `{per_cpu:.2f}`")
    lines.append("Disks: " + ", ".join(f"`{disk['mount']} {disk['used_percent']}%`" for disk in snapshot.disks) if snapshot.disks else "Disks: `unavailable`")

    if snapshot.docker.get("available"):
        containers = snapshot.docker.get("containers", [])
        unhealthy = [
            container
            for container in containers
            if container.get("state") == "running" and container.get("health") and container.get("health") != "healthy"
        ]
        lines.append(f"Docker: `{len(containers)} containers`, unhealthy: `{len(unhealthy)}`")
    else:
        lines.append(f"Docker: `{snapshot.docker.get('reason', 'unavailable')}`")

    lines.append("")
    lines.append("**Findings**")
    if snapshot.findings:
        lines.extend(f"- `{finding.level}` {finding.message}" for finding in snapshot.findings[:8])
    else:
        lines.append("- No warnings")

    lines.append("")
    lines.append("**Top CPU**")
    lines.extend(_render_process_rows(snapshot.processes.get("top_cpu", [])))
    lines.append("**Top memory**")
    lines.extend(_render_process_rows(snapshot.processes.get("top_memory", [])))

    if config.alerting.include_snapshot_path and snapshot.snapshot_path:
        lines.append("")
        lines.append(f"Snapshot: `{snapshot.snapshot_path}`")

    return "\n".join(lines)[:1900]


def post_discord_report(content: str, webhook_url: str) -> None:
    payload = json.dumps({"content": content}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status >= 300:
            raise RuntimeError(f"Discord webhook failed with HTTP {response.status}")


def _render_process_rows(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- unavailable"]
    rendered = []
    for row in rows[:5]:
        rendered.append(f"- `{row['pid']}` `{row['cpu_percent']}% CPU` `{row['memory_percent']}% MEM` {row['name']}")
    return rendered


def _duration(seconds: float) -> str:
    delta = timedelta(seconds=int(seconds))
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"
