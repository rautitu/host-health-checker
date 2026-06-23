from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HostConfig:
    cpu_sample_seconds: float = 2.0
    core_cpu_percent_warn: float = 95.0
    core_cpu_percent_critical: float = 99.0
    mem_used_percent_warn: float = 90.0
    swap_used_percent_warn: float = 25.0
    disk_used_percent_warn: float = 85.0
    inode_used_percent_warn: float = 85.0
    load_per_cpu_warn: float = 1.5
    process_limit: int = 5
    disk_mounts: list[str] = field(default_factory=lambda: ["/"])


@dataclass(frozen=True)
class DockerConfig:
    enabled: bool = True
    container_cpu_percent_warn: float = 150.0
    container_mem_percent_warn: float = 80.0
    restart_count_increase_warn: int = 1
    require_healthy: bool = True


@dataclass(frozen=True)
class AlertingConfig:
    discord_webhook_url_env: str = "HOST_MONITOR_DISCORD_WEBHOOK"
    include_snapshot_path: bool = True
    subagent_prompt_enabled: bool = False
    subagent_prompt_timeout_hours: int = 6
    subagent_prompt_default_model: str = "default"
    subagent_prompt_models: list[str] = field(default_factory=lambda: ["default"])
    subagent_prompt_min_level: str = "warning"
    subagent_prompt_interactive_components: bool = False

    @property
    def discord_webhook_url(self) -> str | None:
        return os.environ.get(self.discord_webhook_url_env)


@dataclass(frozen=True)
class StorageConfig:
    state_path: Path = Path("/var/lib/host-monitor/state.json")
    snapshot_dir: Path = Path("/var/log/host-monitor/snapshots")


@dataclass(frozen=True)
class Config:
    host: HostConfig = field(default_factory=HostConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    alerting: AlertingConfig = field(default_factory=AlertingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


def load_config(path: Path | None) -> Config:
    if path is None:
        return Config()
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    return Config(
        host=_dataclass_from_dict(HostConfig, raw.get("host", {})),
        docker=_dataclass_from_dict(DockerConfig, raw.get("docker", {})),
        alerting=_dataclass_from_dict(AlertingConfig, raw.get("alerting", {})),
        storage=_storage_from_dict(raw.get("storage", {})),
    )


def _dataclass_from_dict(cls: type[Any], data: dict[str, Any]) -> Any:
    allowed = cls.__dataclass_fields__.keys()
    return cls(**{key: value for key, value in data.items() if key in allowed})


def _storage_from_dict(data: dict[str, Any]) -> StorageConfig:
    return StorageConfig(
        state_path=Path(data.get("state_path", StorageConfig.state_path)),
        snapshot_dir=Path(data.get("snapshot_dir", StorageConfig.snapshot_dir)),
    )
