#!/usr/bin/env python3
"""Focused tests for the native Codex trigger evaluator."""
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "trigger_eval", REPO / "tools" / "meta_opt" / "trigger_eval.py")
TE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TE)


def _command_event(command, event_type="item.started"):
    return json.dumps({"type": event_type, "item": {
        "id": "item_1", "type": "command_execution", "command": command}})


class ParseStreamTest(unittest.TestCase):
    def test_extracts_and_deduplicates_command_executions(self):
        command = "/bin/zsh -lc \"sed -n '1,240p' /x/skills/check-gpu/SKILL.md\""
        stream = "\n".join([
            json.dumps({"type": "thread.started"}),
            _command_event(command),
            "not json noise",
            _command_event(command, "item.completed"),
        ])
        self.assertEqual(TE.parse_stream_tool_uses(stream), [
            ("command_execution", {"command": command})])

    def test_skips_malformed_and_non_command_items(self):
        stream = "\n".join(["{bad", json.dumps({"type": "turn.started"}),
                            json.dumps({"type": "item.completed", "item": {
                                "type": "agent_message", "text": "done"}})])
        self.assertEqual(TE.parse_stream_tool_uses(stream), [])


class ClassifyTest(unittest.TestCase):
    def test_reading_target_skill_is_trigger(self):
        uses = [("command_execution", {"command":
                 "sed -n '1,240p' /home/u/.agents/skills/research-lit/SKILL.md"})]
        self.assertEqual(TE.classify(uses, "research-lit"),
                         ("trigger", "research-lit"))

    def test_namespaced_target_matches_directory_basename(self):
        uses = [("command_execution", {"command":
                 "sed -n '1,240p' /cache/plugin/skills/openai-docs/SKILL.md"})]
        outcome, detail = TE.classify(uses, "plugin:openai-docs")
        self.assertEqual(outcome, "trigger")
        self.assertIn("plugin:openai-docs", detail)

    def test_different_skill_is_confusion(self):
        uses = [("command_execution", {"command":
                 "sed -n '1,240p' /home/u/.agents/skills/vast-gpu/SKILL.md"})]
        self.assertEqual(TE.classify(uses, "check-gpu"),
                         ("confusion", "vast-gpu"))

    def test_first_skill_read_decides(self):
        uses = [
            ("command_execution", {"command": "sed /x/skills/vast-gpu/SKILL.md"}),
            ("command_execution", {"command": "sed /x/skills/check-gpu/SKILL.md"}),
        ]
        self.assertEqual(TE.classify(uses, "check-gpu"),
                         ("confusion", "vast-gpu"))

    def test_unrelated_commands_are_miss(self):
        self.assertEqual(TE.classify([
            ("command_execution", {"command": "rg --files"})], "check-gpu")[0],
            "miss")


class AggregateTest(unittest.TestCase):
    def test_rate_excludes_errors(self):
        records = [
            {"skill": "s", "query": "q", "outcome": "trigger", "detail": "s"},
            {"skill": "s", "query": "q", "outcome": "miss", "detail": ""},
            {"skill": "s", "query": "q", "outcome": "error", "detail": "x"},
        ]
        self.assertEqual(TE.aggregate(records)["s"]["trigger_rate"], 0.5)

    def test_all_errors_has_no_rate(self):
        records = [{"skill": "s", "query": "q", "outcome": "error", "detail": "x"}]
        self.assertIsNone(TE.aggregate(records)["s"]["trigger_rate"])


class StreamStateTest(unittest.TestCase):
    def test_turn_failed_is_error(self):
        self.assertTrue(TE._stream_real_error(json.dumps({
            "type": "turn.failed", "error": {"message": "auth"}})))

    def test_completed_turn_is_gradeable(self):
        self.assertTrue(TE._stream_has_assistant(json.dumps({"type": "turn.completed"})))
        self.assertFalse(TE._stream_real_error(json.dumps({"type": "turn.completed"})))

    def test_agent_message_is_gradeable(self):
        stream = json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": "done"}})
        self.assertTrue(TE._stream_has_assistant(stream))


class ProbeCommandTest(unittest.TestCase):
    @mock.patch.object(TE.subprocess, "run")
    def test_uses_required_safe_codex_flags_and_stdin(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"type": "turn.completed"}), stderr="")
        TE.run_probe("query", "gpt-test", 10, "/tmp/neutral")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:2], ["codex", "exec"])
        for flag in ("--json", "--ephemeral", "--skip-git-repo-check"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")
        self.assertEqual(run.call_args.kwargs["input"], "query")
        self.assertEqual(run.call_args.kwargs["cwd"], "/tmp/neutral")


class SampleEvalFileTest(unittest.TestCase):
    def test_sample_file_is_valid(self):
        data = json.loads((REPO / "tools" / "meta_opt" /
                           "trigger_evals.sample.json").read_text())
        skills = {k: v for k, v in data.items() if not k.startswith("_")}
        self.assertTrue(skills)
        self.assertTrue(all(isinstance(q, str) and q.strip()
                            for queries in skills.values() for q in queries))


if __name__ == "__main__":
    unittest.main()
