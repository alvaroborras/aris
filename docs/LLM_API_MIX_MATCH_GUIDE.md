# LLM API Mixing Guide

This guide explains how to mix and match executor and reviewer APIs in Claude Code.

## Idea

Use one provider for the executor and any OpenAI-compatible provider for the reviewer.

- `ANTHROPIC_*` environment variables configure the executor
- `LLM_*` environment variables configure the reviewer through `llm-chat`

This lets you combine providers such as Claude, GLM, Kimi, LongCat, DeepSeek, MiniMax, or a custom compatible endpoint.

## Recommended flow

1. Configure the executor endpoint in `~/.claude/settings.json`.
2. Configure the reviewer MCP server with `llm-chat`.
3. Pick the skill variant that matches your provider pair.
4. If needed, rewrite skills that still call Codex MCP.

## Common combinations

- GLM + DeepSeek
- GLM + Kimi
- Claude + MiniMax
- Any Anthropic-compatible executor plus any OpenAI-compatible reviewer

## Reference

Use this guide together with `MODELSCOPE_GUIDE.md`, `ALI_CODING_PLAN_GUIDE.md`, and `MINIMAX_MCP_GUIDE.md`.
