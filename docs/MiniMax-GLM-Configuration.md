# MiniMax-M3 + GLM Configuration Guide

This guide describes the provider pair where MiniMax-M3 runs the executor and GLM-5 runs the reviewer.

## Overview

This is the inverse of the common GLM + MiniMax setup:

- Executor: MiniMax-M3
- Reviewer: GLM-5 through `llm-chat`

## When to use it

Use this configuration if you want MiniMax to handle the main execution workload and GLM to handle review / critique.

## Setup outline

1. Install Claude Code.
2. Clone the repo and install the bundled `llm-chat` MCP server.
3. Configure `~/.claude/settings.json` with the MiniMax Anthropic-compatible endpoint for the executor.
4. Configure `llm-chat` with the GLM OpenAI-compatible endpoint for the reviewer.
5. Verify both endpoints inside Claude Code.

## Suggested pairing

- Executor: MiniMax-M3
- Reviewer: GLM-5

## Notes

The core requirement is the same as every other ARIS provider pair: the executor and reviewer should be separate model families.
