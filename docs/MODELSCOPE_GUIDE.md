# ModelScope Integration Guide

This guide explains how to run ARIS with the free ModelScope API.

## Why ModelScope

ModelScope offers free API inference for many open models and supports both Anthropic-compatible and OpenAI-compatible endpoints. That makes it a low-friction way to run ARIS without Claude or OpenAI billing.

## Recommended model pairing

- Executor: `deepseek-ai/DeepSeek-V4-Pro`
- Reviewer: `deepseek-ai/DeepSeek-R1`

Other combinations are possible, but the key point is that the executor and reviewer should be different model families.

## Setup outline

1. Create a ModelScope account and generate an SDK token.
2. Install Claude Code and the ARIS skills.
3. Install the bundled `llm-chat` MCP server.
4. Configure `~/.claude/settings.json` with the ModelScope endpoints.
5. Rewrite any skills that still call Codex MCP.

## Validation

Verify the executor endpoint, the reviewer endpoint, the MCP server, and an end-to-end ARIS skill call.

## Notes

ModelScope is attractive because it is free and does not impose the same unattended-automation restrictions as some subscription plans.
