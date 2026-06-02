from __future__ import annotations

import json
import re
from pathlib import Path

from host_monitor.checks.docker import collect_docker
from host_monitor.checks.host import collect_disks, collect_host
from host_monitor.checks.processes import collect_processes
from host_monitor.config import Config
from host_monitor.models import Snapshot
from host_monitor.state import load_state, save_state


def build_snapshot(config: Config) -> Snapshot:
    state = load_state(config.storage.state_path)
    host_data, host_findings = collect_host(config.host)
    disks, disk_findings = collect_disks(config.host)
    docker, docker_findings, state_update = collect_docker(config.docker, state)
    processes = collect_processes(config.host.process_limit)

    snapshot = Snapshot(
        generated_at=str(host_data["generated_at"]),
        hostname=str(host_data["hostname"]),
        uptime_seconds=float(host_data["uptime_seconds"]),
        load_average=host_data["load_average"],  # type: ignore[arg-type]
        cpu=host_data["cpu"],  # type: ignore[arg-type]
        memory=host_data["memory"],  # type: ignore[arg-type]
        swap=host_data["swap"],  # type: ignore[arg-type]
        disks=disks,
        processes=processes,
        docker=docker,
        findings=host_findings + disk_findings + docker_findings,
    )

    state.update(state_update)
    state["last_snapshot_at"] = snapshot.generated_at
    save_state(config.storage.state_path, state)
    return snapshot


def save_snapshot(snapshot: Snapshot, snapshot_dir: Path) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = re.sub(r"[^0-9A-Za-z_.-]", "-", snapshot.generated_at)
    filename = f"{timestamp}-{snapshot.hostname}.json"
    path = snapshot_dir / filename
    snapshot.snapshot_path = str(path)
    path.write_text(json.dumps(snapshot.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
