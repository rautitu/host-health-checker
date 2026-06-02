from __future__ import annotations

import os
import socket
from datetime import datetime, timezone

import psutil

from host_monitor.config import HostConfig
from host_monitor.models import Finding


def collect_host(config: HostConfig) -> tuple[dict[str, object], list[Finding]]:
    psutil.cpu_percent(interval=None, percpu=True)
    per_core = psutil.cpu_percent(interval=config.cpu_sample_seconds, percpu=True)
    avg_cpu = sum(per_core) / len(per_core) if per_core else 0.0
    max_core = max(per_core) if per_core else 0.0
    core_count = psutil.cpu_count() or len(per_core) or 1
    load_average = os.getloadavg() if hasattr(os, "getloadavg") else None
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    findings: list[Finding] = []
    if max_core >= config.core_cpu_percent_critical:
        findings.append(Finding("critical", f"Single CPU core is saturated at {max_core:.1f}%"))
    elif max_core >= config.core_cpu_percent_warn:
        findings.append(Finding("warning", f"Single CPU core is high at {max_core:.1f}%"))
    if memory.percent >= config.mem_used_percent_warn:
        findings.append(Finding("warning", f"Memory usage is high at {memory.percent:.1f}%"))
    if swap.percent >= config.swap_used_percent_warn:
        findings.append(Finding("warning", f"Swap usage is high at {swap.percent:.1f}%"))
    if load_average and load_average[0] / core_count >= config.load_per_cpu_warn:
        findings.append(Finding("warning", f"1-minute load per CPU is {load_average[0] / core_count:.2f}"))

    return (
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "uptime_seconds": datetime.now(timezone.utc).timestamp() - psutil.boot_time(),
            "load_average": load_average,
            "cpu": {
                "average_percent": round(avg_cpu, 1),
                "max_core_percent": round(max_core, 1),
                "per_core_percent": [round(value, 1) for value in per_core],
                "core_count": core_count,
                "busy_core_indexes": _busy_core_indexes(per_core, limit=4),
            },
            "memory": _memory_dict(memory),
            "swap": _memory_dict(swap),
        },
        findings,
    )


def collect_disks(config: HostConfig) -> tuple[list[dict[str, object]], list[Finding]]:
    findings: list[Finding] = []
    disks: list[dict[str, object]] = []

    for mount in config.disk_mounts:
        try:
            usage = psutil.disk_usage(mount)
            inode = _inode_usage(mount)
        except OSError as exc:
            findings.append(Finding("warning", f"Could not read disk usage for {mount}: {exc}"))
            continue

        disk = {
            "mount": mount,
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": round(usage.percent, 1),
            "inode_used_percent": inode,
        }
        disks.append(disk)
        if usage.percent >= config.disk_used_percent_warn:
            findings.append(Finding("warning", f"Disk {mount} usage is high at {usage.percent:.1f}%"))
        if inode is not None and inode >= config.inode_used_percent_warn:
            findings.append(Finding("warning", f"Disk {mount} inode usage is high at {inode:.1f}%"))

    return disks, findings


def _memory_dict(memory: psutil._common.svmem | psutil._common.sswap) -> dict[str, object]:
    return {
        "total_bytes": memory.total,
        "used_bytes": memory.used,
        "available_bytes": getattr(memory, "available", None),
        "free_bytes": memory.free,
        "used_percent": round(memory.percent, 1),
    }


def _busy_core_indexes(per_core: list[float], limit: int) -> list[int]:
    return [index for index, _ in sorted(enumerate(per_core), key=lambda item: item[1], reverse=True)[:limit]]


def _inode_usage(mount: str) -> float | None:
    stats = os.statvfs(mount)
    total = stats.f_files
    if not total:
        return None
    used = total - stats.f_ffree
    return round((used / total) * 100, 1)

