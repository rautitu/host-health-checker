from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from host_monitor.config import Config
from host_monitor.models import Finding, Snapshot


LEVEL_ORDER = {
    "info": 0,
    "warning": 1,
    "critical": 2,
}


def should_prompt_for_subagent(snapshot: Snapshot, config: Config) -> bool:
    if not config.alerting.subagent_prompt_enabled:
        return False
    if not snapshot.findings:
        return False

    minimum = LEVEL_ORDER.get(config.alerting.subagent_prompt_min_level.lower(), LEVEL_ORDER["warning"])
    return any(LEVEL_ORDER.get(finding.level.lower(), 0) >= minimum for finding in snapshot.findings)


def render_subagent_prompt(snapshot: Snapshot, config: Config) -> dict[str, object]:
    request_id = _request_id(snapshot)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=config.alerting.subagent_prompt_timeout_hours)
    models = _model_options(config.alerting.subagent_prompt_models, config.alerting.subagent_prompt_default_model)

    content = "\n".join(
        [
            f"**Subagent analysis requested?** `{snapshot.hostname}`",
            f"Findings: `{len(snapshot.findings)}` | expires: `{expires_at.isoformat(timespec='minutes')}`",
            _prompt_instruction(config),
            "",
            "**Findings**",
            *[f"- `{finding.level}` {finding.message}" for finding in snapshot.findings[:8]],
            "",
            f"Snapshot: `{snapshot.snapshot_path or 'not saved'}`",
            f"Request id: `{request_id}`",
        ]
    )[:1900]

    payload: dict[str, object] = {
        "content": content,
        "allowed_mentions": {"parse": []},
    }

    if config.alerting.subagent_prompt_interactive_components:
        payload["components"] = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 3,
                        "custom_id": f"host-monitor:subagent:model:{request_id}",
                        "placeholder": "Model",
                        "min_values": 1,
                        "max_values": 1,
                        "options": models,
                    }
                ],
            },
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 3,
                        "label": "Kyllä",
                        "custom_id": f"host-monitor:subagent:approve:{request_id}",
                    },
                    {
                        "type": 2,
                        "style": 4,
                        "label": "Ei",
                        "custom_id": f"host-monitor:subagent:decline:{request_id}",
                    },
                ],
            },
        ]

    return payload


def post_subagent_prompt(snapshot: Snapshot, config: Config, webhook_url: str) -> None:
    payload = json.dumps(render_subagent_prompt(snapshot, config)).encode("utf-8")
    url = _with_components(webhook_url) if config.alerting.subagent_prompt_interactive_components else webhook_url
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "host-health-checker/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status >= 300:
                raise RuntimeError(f"Discord subagent prompt failed with HTTP {response.status}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        detail = f": {body}" if body else ""
        raise RuntimeError(f"Discord subagent prompt failed with HTTP {exc.code}{detail}") from exc


def _prompt_instruction(config: Config) -> str:
    if config.alerting.subagent_prompt_interactive_components:
        return "Choose a model and approve within the timeout if you want OpenClaw to investigate this snapshot."
    return (
        "OpenClaw receiver is not wired yet, so this is a notification only. "
        "Use the request id and snapshot path if you want to trigger analysis manually."
    )


def _model_options(models: list[str], default_model: str) -> list[dict[str, object]]:
    seen = set()
    ordered = [default_model, *models]
    options = []
    for model in ordered:
        if model in seen:
            continue
        seen.add(model)
        options.append(
            {
                "label": model,
                "value": model,
                "default": model == default_model,
            }
        )
    return options[:25]


def _request_id(snapshot: Snapshot) -> str:
    source = f"{snapshot.hostname}:{snapshot.generated_at}:{snapshot.snapshot_path or ''}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _with_components(webhook_url: str) -> str:
    parsed = urllib.parse.urlsplit(webhook_url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query["with_components"] = ["true"]
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(query, doseq=True),
            parsed.fragment,
        )
    )
