# MiniMax MCP Integration Guide

This guide explains how to replace Codex MCP with MiniMax for review workflows.

## Background

Codex CLI is built around OpenAI's Responses API. MiniMax and other third-party providers usually expose only the Chat Completions API, so Codex MCP cannot talk to them directly.

The fix is to run a custom MCP server that calls the MiniMax chat API.

## Two review-loop variants

| Version | Skill name | Trigger | External reviewer |
|---|---|---|---|
| Original | `auto-review-loop` | `auto review loop` | Codex MCP (OpenAI) |
| MiniMax | `auto-review-loop-minimax` | `auto review loop minimax` | MiniMax API |

## Which one to use

- Use the original version if you already have an OpenAI API key and the budget to match.
- Use the MiniMax version if you want lower-cost review calls or already have a MiniMax account.

## Setup outline

1. Create the MCP server directory.
2. Copy the MiniMax MCP server code.
3. Install the Python dependencies.
4. Configure the MiniMax environment variables.
5. Install the matching ARIS skill.
6. Point Claude Code at the new MCP server.

## Validation

Check that the MCP server starts, the chosen model responds, and the review loop skill can call it end to end.
