from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Finding:
    level: str
    message: str


@dataclass
class Snapshot:
    generated_at: str
    hostname: str
    uptime_seconds: float
    load_average: tuple[float, float, float] | None
    cpu: dict[str, Any]
    memory: dict[str, Any]
    swap: dict[str, Any]
    disks: list[dict[str, Any]]
    processes: dict[str, list[dict[str, Any]]]
    docker: dict[str, Any]
    findings: list[Finding] = field(default_factory=list)
    snapshot_path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = {
            "generated_at": self.generated_at,
            "hostname": self.hostname,
            "uptime_seconds": self.uptime_seconds,
            "load_average": self.load_average,
            "cpu": self.cpu,
            "memory": self.memory,
            "swap": self.swap,
            "disks": self.disks,
            "processes": self.processes,
            "docker": self.docker,
            "findings": [finding.__dict__ for finding in self.findings],
        }
        if self.snapshot_path:
            data["snapshot_path"] = self.snapshot_path
        return data

