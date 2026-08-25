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
class SensorsConfig:
    enabled: bool = True
    cpu_temperature_warn_c: float = 85.0
    cpu_temperature_critical_c: float = 95.0
    gpu_temperature_warn_c: float = 85.0
    gpu_temperature_critical_c: float = 95.0


@dataclass(frozen=True)
class AlertingConfig:
    discord_webhook_url_env: str = "HOST_MONITOR_DISCORD_WEBHOOK"
    include_snapshot_path: bool = True
    openclaw_analysis_hook_enabled: bool = False
    openclaw_hook_url_env: str = "HOST_MONITOR_OPENCLAW_HOOK_URL"
    openclaw_hook_token_env: str = "HOST_MONITOR_OPENCLAW_HOOK_TOKEN"
    openclaw_discord_channel_env: str = "HOST_MONITOR_OPENCLAW_DISCORD_CHANNEL"

    @property
    def discord_webhook_url(self) -> str | None:
        return os.environ.get(self.discord_webhook_url_env)

    @property
    def openclaw_hook_url(self) -> str | None:
        return os.environ.get(self.openclaw_hook_url_env)

    @property
    def openclaw_hook_token(self) -> str | None:
        return os.environ.get(self.openclaw_hook_token_env)

    @property
    def openclaw_discord_channel(self) -> str | None:
        return os.environ.get(self.openclaw_discord_channel_env)


@dataclass(frozen=True)
class StorageConfig:
    state_path: Path = Path("/var/lib/host-monitor/state.json")
    snapshot_dir: Path = Path("/var/log/host-monitor/snapshots")


@dataclass(frozen=True)
class Config:
    host: HostConfig = field(default_factory=HostConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    sensors: SensorsConfig = field(default_factory=SensorsConfig)
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
        sensors=_dataclass_from_dict(SensorsConfig, raw.get("sensors", {})),
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
