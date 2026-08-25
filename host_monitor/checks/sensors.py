from __future__ import annotations

import csv
import shutil
import subprocess
from io import StringIO

import psutil

from host_monitor.config import SensorsConfig
from host_monitor.models import Finding


def collect_sensors(config: SensorsConfig) -> tuple[dict[str, object], list[Finding]]:
    if not config.enabled:
        return {"enabled": False, "cpu": {}, "gpus": []}, []

    cpu = _collect_cpu_sensors()
    gpus, nvidia_reason = _collect_nvidia_gpus()
    findings = _temperature_findings(cpu, gpus, config)

    return (
        {
            "enabled": True,
            "cpu": cpu,
            "gpus": gpus,
            "nvidia_smi_available": shutil.which("nvidia-smi") is not None,
            "nvidia_smi_reason": nvidia_reason,
        },
        findings,
    )


def _collect_cpu_sensors() -> dict[str, object]:
    result: dict[str, object] = {}
    try:
        temperatures = psutil.sensors_temperatures(fahrenheit=False)
    except (AttributeError, OSError, RuntimeError):
        temperatures = {}

    for group_name in ("coretemp", "k10temp", "zenpower"):
        entries = temperatures.get(group_name, [])
        if not entries:
            continue

        package = next(
            (
                entry
                for entry in entries
                if any(name in (entry.label or "").lower() for name in ("package", "tctl", "tdie"))
            ),
            entries[0],
        )
        result["temperature_c"] = round(float(package.current), 1)
        result["temperature_label"] = package.label or group_name
        result["temperature_source"] = f"psutil:{group_name}"

        core_temperatures = [float(entry.current) for entry in entries if "core" in (entry.label or "").lower()]
        if core_temperatures:
            result["max_core_temperature_c"] = round(max(core_temperatures), 1)
        break

    try:
        fans = psutil.sensors_fans()
    except (AttributeError, OSError, RuntimeError):
        fans = {}

    for group_name, entries in fans.items():
        cpu_fan = next((entry for entry in entries if "cpu" in (entry.label or "").lower()), None)
        if cpu_fan is None:
            continue
        result["fan_rpm"] = int(cpu_fan.current)
        result["fan_label"] = cpu_fan.label
        result["fan_source"] = f"psutil:{group_name}"
        break

    return result


def _collect_nvidia_gpus() -> tuple[list[dict[str, object]], str | None]:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return [], "nvidia-smi not found"

    command = [
        executable,
        "--query-gpu=index,name,temperature.gpu,fan.speed",
        "--format=csv,noheader,nounits",
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [], f"nvidia-smi failed: {exc}"

    if completed.returncode != 0:
        reason = completed.stderr.strip() or f"nvidia-smi exited with status {completed.returncode}"
        return [], reason

    gpus: list[dict[str, object]] = []
    for row in csv.reader(StringIO(completed.stdout), skipinitialspace=True):
        if len(row) != 4:
            continue
        index, name, temperature, fan_percent = (value.strip() for value in row)
        gpu: dict[str, object] = {
            "index": _int_or_value(index),
            "name": name,
            "source": "nvidia-smi",
        }
        parsed_temperature = _optional_number(temperature)
        parsed_fan = _optional_number(fan_percent)
        if parsed_temperature is not None:
            gpu["temperature_c"] = parsed_temperature
        if parsed_fan is not None:
            gpu["fan_percent"] = parsed_fan
        gpus.append(gpu)
    return gpus, None


def _temperature_findings(
    cpu: dict[str, object], gpus: list[dict[str, object]], config: SensorsConfig
) -> list[Finding]:
    findings: list[Finding] = []
    cpu_temperature = cpu.get("temperature_c")
    if isinstance(cpu_temperature, (int, float)):
        if cpu_temperature >= config.cpu_temperature_critical_c:
            findings.append(Finding("critical", f"CPU temperature is critical at {cpu_temperature:.1f}°C"))
        elif cpu_temperature >= config.cpu_temperature_warn_c:
            findings.append(Finding("warning", f"CPU temperature is high at {cpu_temperature:.1f}°C"))

    for gpu in gpus:
        temperature = gpu.get("temperature_c")
        if not isinstance(temperature, (int, float)):
            continue
        label = f"GPU {gpu.get('index', '?')}"
        if temperature >= config.gpu_temperature_critical_c:
            findings.append(Finding("critical", f"{label} temperature is critical at {temperature:.1f}°C"))
        elif temperature >= config.gpu_temperature_warn_c:
            findings.append(Finding("warning", f"{label} temperature is high at {temperature:.1f}°C"))
    return findings


def _optional_number(value: str) -> int | float | None:
    if value.lower() in {"", "n/a", "na", "[not supported]", "not supported"}:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return int(number) if number.is_integer() else round(number, 1)


def _int_or_value(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value
