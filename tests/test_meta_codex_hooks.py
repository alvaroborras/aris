from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.meta_opt import hook_adapter


ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "templates/claude-hooks/corpus_write_guard.py"


def test_normalizes_codex_skill_prompt_and_root(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    record = hook_adapter.normalize_payload(
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "s",
            "cwd": str(tmp_path),
            "prompt": "$meta-optimize all",
        }
    )
    assert record["event"] == "skill_invoke"
    assert record["skill"] == "meta-optimize"
    assert record["args"] == "all"
    assert record["project_root"] == str(tmp_path.resolve())


def test_normalizes_tool_failure_and_model_change(tmp_path: Path) -> None:
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "s",
        "cwd": str(tmp_path),
        "model": "m1",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "error": "failed",
    }
    record = hook_adapter.normalize_payload(payload)
    assert record["event"] == "tool_failure"
    assert record["input_summary"] == "pytest"
    hook_adapter.write_event(
        hook_adapter.normalize_payload(
            {**payload, "hook_event_name": "SessionStart", "source": "startup"}
        ),
        home=tmp_path / "home",
    )
    hook_adapter.write_event(
        hook_adapter.normalize_payload({**payload, "model": "m2"}),
        home=tmp_path / "home",
    )
    events = [
        json.loads(x)
        for x in (tmp_path / ".aris/meta/events.jsonl").read_text().splitlines()
    ]
    assert any(
        x["event"] == "model_change" and x["previous_model"] == "m1" for x in events
    )


def test_stop_readiness_is_valid_json_and_deduplicated(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    events = project / ".aris/meta/events.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text(
        "\n".join(
            json.dumps({"event": "skill_invoke", "ts": f"2026-01-01T00:00:0{i}Z"})
            for i in range(5)
        )
        + "\n"
    )
    record = {"project_root": str(project)}
    message = hook_adapter.readiness_message(record)
    assert json.loads(json.dumps({"systemMessage": message})) == {
        "systemMessage": message
    }
    assert hook_adapter.readiness_message(record) is None


def test_guard_supports_agents_and_fails_open_for_malformed() -> None:
    def run(command: str, tool: str = "Bash") -> int:
        p = subprocess.run(
            [sys.executable, str(GUARD)],
            input=json.dumps({"tool_name": tool, "tool_input": {"command": command}}),
            text=True,
            capture_output=True,
        )
        return p.returncode

    assert run("echo x > .agents/skills/foo/SKILL.md") == 2
    assert run("cat .agents/skills/foo/SKILL.md") == 0
    assert run("echo x > .aris/meta/events.jsonl") == 0
    assert run("echo x > skills/foo/SKILL.md", "apply_patch") == 0
    malformed = subprocess.run(
        [sys.executable, str(GUARD)], input="not json", text=True, capture_output=True
    )
    assert malformed.returncode == 0


def test_hook_configs_are_sync_command_handlers() -> None:
    for path in (ROOT / ".codex/hooks.json", ROOT / "templates/codex-hooks/hooks.json"):
        value = json.loads(path.read_text())
        assert set(value["hooks"]) <= {
            "SessionStart",
            "UserPromptSubmit",
            "PostToolUse",
            "Stop",
            "PreToolUse",
        }
        for groups in value["hooks"].values():
            for group in groups:
                for handler in group["hooks"]:
                    assert handler["type"] == "command"
                    assert "async" not in handler
