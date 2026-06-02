from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from host_monitor.config import DockerConfig
from host_monitor.models import Finding


def collect_docker(config: DockerConfig, previous_state: dict[str, Any]) -> tuple[dict[str, Any], list[Finding], dict[str, Any]]:
    if not config.enabled:
        return {"available": False, "reason": "disabled"}, [], {}
    if not shutil.which("docker"):
        return {"available": False, "reason": "docker CLI not found"}, [], {}

    ps_result = _run(["docker", "ps", "-a", "--format", "{{json .}}"])
    if ps_result.returncode != 0:
        reason = ps_result.stderr.strip() or ps_result.stdout.strip() or "docker command failed"
        return {"available": False, "reason": reason}, [Finding("warning", f"Docker unavailable: {reason}")], {}

    stats_result = _run(["docker", "stats", "--no-stream", "--format", "{{json .}}"])
    stats_by_id = _parse_json_lines(stats_result.stdout) if stats_result.returncode == 0 else {}
    containers = []
    findings: list[Finding] = []
    next_restart_counts: dict[str, int] = {}
    previous_restart_counts = previous_state.get("docker_restart_counts", {})

    for row in _parse_json_lines(ps_result.stdout).values():
        container_id = row.get("ID", "")
        inspect = _inspect(container_id)
        name = row.get("Names", "")
        restart_count = int(inspect.get("RestartCount") or 0)
        next_restart_counts[name or container_id] = restart_count
        prior_restart_count = int(previous_restart_counts.get(name or container_id, restart_count))
        restart_delta = restart_count - prior_restart_count
        health = inspect.get("State", {}).get("Health", {}).get("Status")
        stat = stats_by_id.get(container_id) or stats_by_id.get(name) or {}
        cpu_percent = _percent(stat.get("CPUPerc"))
        mem_percent = _percent(stat.get("MemPerc"))

        if restart_delta >= config.restart_count_increase_warn:
            findings.append(Finding("warning", f"Container {name} restart count increased by {restart_delta}"))
        if config.require_healthy and row.get("State") == "running" and health and health != "healthy":
            findings.append(Finding("warning", f"Container {name} health is {health}"))
        if cpu_percent is not None and cpu_percent >= config.container_cpu_percent_warn:
            findings.append(Finding("warning", f"Container {name} CPU is {cpu_percent:.1f}%"))
        if mem_percent is not None and mem_percent >= config.container_mem_percent_warn:
            findings.append(Finding("warning", f"Container {name} memory is {mem_percent:.1f}%"))

        containers.append(
            {
                "id": container_id,
                "name": name,
                "status": row.get("Status"),
                "state": row.get("State"),
                "health": health,
                "restart_count": restart_count,
                "restart_delta": restart_delta,
                "cpu_percent": cpu_percent,
                "memory_percent": mem_percent,
                "memory_usage": stat.get("MemUsage"),
            }
        )

    return {"available": True, "containers": containers}, findings, {"docker_restart_counts": next_restart_counts}


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=20)


def _parse_json_lines(output: str) -> dict[str, dict[str, Any]]:
    parsed = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = row.get("ID") or row.get("Name") or row.get("Name")
        if key:
            parsed[key] = row
    return parsed


def _inspect(container_id: str) -> dict[str, Any]:
    result = _run(["docker", "inspect", container_id])
    if result.returncode != 0:
        return {}
    payload = json.loads(result.stdout)
    return payload[0] if payload else {}


def _percent(value: str | None) -> float | None:
    if not value:
        return None
    return float(value.strip().rstrip("%"))
