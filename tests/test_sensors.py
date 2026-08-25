from collections import namedtuple
from subprocess import CompletedProcess

from host_monitor.checks.sensors import collect_sensors
from host_monitor.config import SensorsConfig


Temperature = namedtuple("Temperature", "label current high critical")
Fan = namedtuple("Fan", "label current")


def test_collects_cpu_temperature_and_fan(monkeypatch):
    monkeypatch.setattr(
        "host_monitor.checks.sensors.psutil.sensors_temperatures",
        lambda fahrenheit=False: {
            "coretemp": [
                Temperature("Package id 0", 61.0, 100.0, 100.0),
                Temperature("Core 0", 58.0, 100.0, 100.0),
                Temperature("Core 1", 63.0, 100.0, 100.0),
            ]
        },
    )
    monkeypatch.setattr(
        "host_monitor.checks.sensors.psutil.sensors_fans",
        lambda: {"asus": [Fan("cpu_fan", 1700)]},
    )
    monkeypatch.setattr("host_monitor.checks.sensors.shutil.which", lambda command: None)

    sensors, findings = collect_sensors(SensorsConfig())

    assert sensors["cpu"] == {
        "temperature_c": 61.0,
        "temperature_label": "Package id 0",
        "temperature_source": "psutil:coretemp",
        "max_core_temperature_c": 63.0,
        "fan_rpm": 1700,
        "fan_label": "cpu_fan",
        "fan_source": "psutil:asus",
    }
    assert findings == []


def test_collects_nvidia_gpu_and_creates_temperature_finding(monkeypatch):
    monkeypatch.setattr("host_monitor.checks.sensors.psutil.sensors_temperatures", lambda fahrenheit=False: {})
    monkeypatch.setattr("host_monitor.checks.sensors.psutil.sensors_fans", lambda: {})
    monkeypatch.setattr("host_monitor.checks.sensors.shutil.which", lambda command: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(
        "host_monitor.checks.sensors.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, '0, "NVIDIA RTX 4090", 88, 42\n', ""),
    )

    sensors, findings = collect_sensors(SensorsConfig())

    assert sensors["gpus"] == [
        {
            "index": 0,
            "name": "NVIDIA RTX 4090",
            "temperature_c": 88,
            "fan_percent": 42,
            "source": "nvidia-smi",
        }
    ]
    assert [finding.message for finding in findings] == ["GPU 0 temperature is high at 88.0°C"]


def test_missing_sensors_are_best_effort(monkeypatch):
    monkeypatch.setattr(
        "host_monitor.checks.sensors.psutil.sensors_temperatures", lambda fahrenheit=False: (_ for _ in ()).throw(OSError())
    )
    monkeypatch.setattr("host_monitor.checks.sensors.psutil.sensors_fans", lambda: (_ for _ in ()).throw(OSError()))
    monkeypatch.setattr("host_monitor.checks.sensors.shutil.which", lambda command: None)

    sensors, findings = collect_sensors(SensorsConfig())

    assert sensors["cpu"] == {}
    assert sensors["gpus"] == []
    assert findings == []
