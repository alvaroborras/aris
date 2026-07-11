# Ali Bailian Coding Plan Integration Guide

This guide explains how to run the ARIS workflow with a single Ali Bailian Coding Plan API key, without Claude or OpenAI billing.

## Overview

Coding Plan exposes Anthropic-compatible and OpenAI-compatible endpoints behind one subscription key. In ARIS, that means:

- the executor can use the Anthropic-compatible endpoint
- the reviewer can use the OpenAI-compatible endpoint through the bundled `llm-chat` MCP server

### Supported models

The practical choices are:

- `qwen3.5-plus` for lightweight execution and image reading
- `kimi-k2.5` for the main executor
- `glm-5` for the main reviewer
- `MiniMax-M3` as a fast reviewer alternative

## Why `llm-chat` instead of Codex MCP

Codex MCP is tied to OpenAI's Responses API, which third-party providers such as Coding Plan do not expose. The bundled `llm-chat` MCP server uses the standard Chat Completions API, so it works with any OpenAI-compatible endpoint.

## Usage restrictions

Coding Plan's terms are restrictive. The safe interpretation is interactive, human-in-the-loop use inside a coding tool. Fully unattended overnight automation may violate the plan terms.

If you need unattended runs, consider a metered API key or another provider without that restriction.

## Recommended layout

- Executor endpoint: Anthropic-compatible
- Reviewer endpoint: OpenAI-compatible
- Same Coding Plan key for both

## Setup outline

1. Clone the repo.
2. Install Python dependencies.
3. Start the `llm-chat` MCP server.
4. Install the ARIS skills.
5. Configure `~/.claude/settings.json`.
6. Rewrite any skills that still call Codex MCP so they use `mcp__llm-chat__chat`.

## Validation

Verify the executor endpoint, the reviewer endpoint, the MCP server, and an end-to-end skill call in Claude Code.

## Model recommendations

- Balanced: `kimi-k2.5` executor + `glm-5` reviewer
- Speed-first: `qwen3.5-plus` + `MiniMax-M3`
- Test-stage: `qwen3.5-plus` + `glm-5`

## References

- Ali Bailian Coding Plan docs
- OpenAI Codex discussion #7782
- `LLM_API_MIX_MATCH_GUIDE.md`
- `MINIMAX_MCP_GUIDE.md`
- Claude Code docs
