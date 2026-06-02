from __future__ import annotations

import os
import re
import time

import psutil

SENSITIVE_ARG_RE = re.compile(r"(token|secret|password|passwd|pwd|key|webhook)", re.IGNORECASE)
URL_RE = re.compile(r"https?://\S+")


def collect_processes(limit: int) -> dict[str, list[dict[str, object]]]:
    current_pid = os.getpid()
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
            if info["pid"] == current_pid:
                continue
            cpu_percent = proc.cpu_percent(interval=None)
            command = _format_command(info.get("cmdline") or [], info.get("name") or "")
            rows.append(
                {
                    "pid": info["pid"],
                    "name": info.get("name") or "",
                    "username": info.get("username") or "",
                    "cpu_percent": round(float(cpu_percent or 0.0), 1),
                    "memory_percent": round(float(info.get("memory_percent") or 0.0), 1),
                    "cmdline": command,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    cpu_rows = [row for row in rows if row["cpu_percent"] > 0]

    return {
        "top_cpu": sorted(cpu_rows, key=lambda row: row["cpu_percent"], reverse=True)[:limit],
        "top_memory": sorted(rows, key=lambda row: row["memory_percent"], reverse=True)[:limit],
    }


def _format_command(cmdline: list[str], fallback: str) -> str:
    if not cmdline:
        return fallback
    redacted = []
    redact_next = False
    for arg in cmdline:
        if redact_next:
            redacted.append("[redacted]")
            redact_next = False
            continue
        if SENSITIVE_ARG_RE.search(arg):
            if "=" in arg:
                key, _value = arg.split("=", 1)
                redacted.append(f"{key}=[redacted]")
            else:
                redacted.append(arg)
                redact_next = arg.startswith("-")
            continue
        redacted.append(URL_RE.sub("[url]", arg))
    command = " ".join(redacted).replace("`", "'").strip()
    if len(command) > 90:
        return f"{command[:87]}..."
    return command
