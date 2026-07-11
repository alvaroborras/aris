#!/usr/bin/env python3
"""Normalize Claude and Codex lifecycle hook payloads for ARIS meta-optimization.

Logging hooks are deliberately silent on stdout.  ``--mode readiness`` is the
only mode that emits Codex hook JSON, and it emits nothing when no reminder is
due.  The module is also importable for payload-normalization tests.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ("" if value is None else str(value))


def project_root(
    payload: dict[str, Any], *, environ: dict[str, str] | None = None
) -> Path:
    env = os.environ if environ is None else environ
    cwd = Path(
        _text(payload.get("cwd"))
        or env.get("CLAUDE_PROJECT_DIR")
        or env.get("PWD")
        or os.getcwd()
    ).expanduser()
    if not cwd.is_dir():
        cwd = cwd.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        return cwd.resolve()


def _event_name(payload: dict[str, Any]) -> str:
    return _text(payload.get("hook_event_name") or payload.get("event") or "unknown")


def normalize_payload(
    payload: dict[str, Any], *, environ: dict[str, str] | None = None
) -> dict[str, Any]:
    """Return the stable ARIS event schema for either hook dialect."""
    event_name = _event_name(payload)
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    session = _text(payload.get("session_id") or payload.get("session"))
    record: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session,
        "event": event_name,
    }
    if payload.get("turn_id"):
        record["turn"] = _text(payload["turn_id"])

    if event_name in {
        "PostToolUse",
        "PostToolUseFailure",
        "PreToolUse",
        "PermissionRequest",
    }:
        tool = _text(payload.get("tool_name") or payload.get("tool"))
        record["tool"] = tool
        if (
            event_name == "PostToolUseFailure"
            or payload.get("error")
            or payload.get("is_error")
        ):
            record["event"] = "tool_failure"
            if payload.get("error"):
                record["error"] = _text(payload["error"])[:500]
        if tool == "Skill":
            record["event"] = "skill_invoke"
            record["skill"] = _text(tool_input.get("skill") or tool_input.get("name"))
            record["args"] = _text(tool_input.get("args"))
        elif tool in {"Bash", "apply_patch"}:
            record["input_summary"] = _text(tool_input.get("command"))[:200]
        elif tool:
            record["input_summary"] = json.dumps(tool_input, ensure_ascii=False)[:200]
        output = payload.get("tool_output") or payload.get("tool_response")
        if output is not None:
            record["output_summary"] = _text(output)[:200]
    elif event_name == "UserPromptSubmit":
        prompt = _text(payload.get("prompt") or payload.get("user_prompt"))
        record["prompt_preview"] = prompt[:200]
        stripped = prompt.lstrip()
        if stripped.startswith(("/", "$")):
            parts = stripped.split(None, 1)
            command = parts[0]
            record["event"] = (
                "slash_command" if command.startswith("/") else "skill_invoke"
            )
            record["command"] = command
            record["skill"] = command[1:]
            record["args"] = parts[1] if len(parts) > 1 else ""
    elif event_name == "SessionStart":
        record.update(
            event="session_start",
            source=_text(payload.get("source")),
            model=_text(payload.get("model")),
        )
    elif event_name == "Stop":
        record["event"] = "turn_stop"
        if payload.get("stop_reason"):
            record["stop_reason"] = _text(payload["stop_reason"])
    elif event_name == "SessionEnd":
        record["event"] = "session_end"

    if payload.get("model"):
        record["model"] = _text(payload["model"])
    record["project_root"] = str(project_root(payload, environ=environ))
    return record


def _append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_event(record: dict[str, Any], *, home: Path | None = None) -> None:
    root = Path(record["project_root"])
    project_log = root / ".aris/meta/events.jsonl"
    global_log = (home or Path.home()) / ".aris/meta/events.jsonl"
    # Keep model changes explicit without requiring Codex to expose a separate
    # lifecycle event. The sidecar is project-local and does not affect the
    # stable event schema.
    model = record.get("model")
    model_state = root / ".aris/meta/.last_hook_model"
    extra: list[dict[str, Any]] = []
    if model:
        previous = (
            model_state.read_text(encoding="utf-8").strip()
            if model_state.exists()
            else ""
        )
        if previous and previous != model:
            change = dict(record)
            change.update(event="model_change", previous_model=previous, model=model)
            extra.append(change)
        model_state.parent.mkdir(parents=True, exist_ok=True)
        model_state.write_text(str(model), encoding="utf-8")
    for item in (*extra, record):
        _append(project_log, item)
    for item in (*extra, record):
        global_item = dict(item)
        global_item["project"] = root.name
        _append(global_log, global_item)


def readiness_message(record: dict[str, Any]) -> str | None:
    root = Path(record["project_root"])
    events = root / ".aris/meta/events.jsonl"
    if not events.exists():
        return None
    try:
        rows = [
            json.loads(line)
            for line in events.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError):
        return None
    last = root / ".aris/meta/.last_optimize"
    marker = last.read_text(encoding="utf-8").strip() if last.exists() else ""
    count = sum(
        1
        for row in rows
        if row.get("event") == "skill_invoke"
        and (not marker or row.get("ts", "") > marker)
    )
    if count < 5:
        return None
    emitted = root / ".aris/meta/.last_readiness_reminder"
    if emitted.exists() and emitted.read_text(encoding="utf-8").strip() == str(count):
        return None
    emitted.parent.mkdir(parents=True, exist_ok=True)
    emitted.write_text(str(count), encoding="utf-8")
    return f"📊 ARIS has logged {count} skill runs since last optimization. Run $meta-optimize to check for improvement opportunities."


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("logger", "readiness", "guard"), default="logger"
    )
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    if not isinstance(payload, dict):
        return 0
    if args.mode == "guard":
        from importlib.util import module_from_spec, spec_from_file_location

        guard_path = (
            Path(__file__).parents[2] / "templates/claude-hooks/corpus_write_guard.py"
        )
        spec = spec_from_file_location("aris_corpus_write_guard", guard_path)
        assert spec and spec.loader
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        guard_main = getattr(module, "main")
        return guard_main(payload)
    record = normalize_payload(payload)
    write_event(record)
    if args.mode == "readiness":
        message = readiness_message(record)
        if message:
            sys.stdout.write(
                json.dumps({"systemMessage": message}, ensure_ascii=False) + "\n"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
