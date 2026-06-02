from __future__ import annotations

import time

import psutil


def collect_processes(limit: int) -> dict[str, list[dict[str, object]]]:
    procs = list(psutil.process_iter())
    for proc in procs:
        try:
            proc.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.1)

    rows = []
    for proc in procs:
        try:
            info = proc.as_dict(attrs=["pid", "name", "username", "memory_percent", "cmdline"])
            cpu_percent = proc.cpu_percent(interval=None)
            rows.append(
                {
                    "pid": info["pid"],
                    "name": info.get("name") or "",
                    "username": info.get("username") or "",
                    "cpu_percent": round(float(cpu_percent or 0.0), 1),
                    "memory_percent": round(float(info.get("memory_percent") or 0.0), 1),
                    "cmdline": " ".join(info.get("cmdline") or [])[:240],
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return {
        "top_cpu": sorted(rows, key=lambda row: row["cpu_percent"], reverse=True)[:limit],
        "top_memory": sorted(rows, key=lambda row: row["memory_percent"], reverse=True)[:limit],
    }
