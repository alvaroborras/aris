# OpenClaw Adaptation Guide

> Goal: run the core ARIS workflows in OpenClaw when Claude Code slash skills are not available.

## 1. Adaptation model

ARIS is fundamentally a research workflow orchestrator:

- Workflow 1: literature → ideas → novelty / feasibility assessment
- Workflow 2: experiment execution → auto-review loop → iterative fixes

In OpenClaw, replace slash skills with staged tasks and explicit file outputs.

## 2. Mapping from ARIS to OpenClaw

| ARIS skill | OpenClaw equivalent | Output file |
|---|---|---|
| `/research-lit` | Run literature scanning and structured review | `outputs/lit_scan.md` |
| `/idea-creator` | Generate candidate ideas, MVPs, and failure signals | `outputs/idea_report.md` |
| `/run-experiment` | Generate an experiment matrix, run commands, and log conventions | `outputs/experiment_plan.md` / `outputs/runbook.md` |
| `/auto-review-loop` | Iterative review with score and minimal fix actions | `outputs/review_loop.md` |
| Full pipeline | Chain the stages end to end | `outputs/final_summary.md` |

## 3. Minimal runnable flow

### Stage 1: Literature scan

Run a literature scan for the topic, write `outputs/lit_scan.md`, and list five research gaps.

### Stage 2: Idea generation

Use `outputs/lit_scan.md` to generate three candidate ideas, write `outputs/idea_report.md`, and rank the top two.

### Stage 3: Experiment script

Use the top idea to generate an experiment matrix and one-week plan, writing `outputs/experiment_plan.md` and `outputs/runbook.md`.

### Stage 4: Review loop

Start a review loop with at most four rounds. Each round should output a score, weaknesses, and the minimal fix actions, then update `outputs/review_loop.md`.

## 4. Implementation notes

1. Prefer files over chat history so context drift stays low.
2. Cap the review loop at four rounds to avoid endless iteration.
3. Record sources and location fields for any evidence-heavy claims.
4. Sync local files to Feishu if you want cross-device review.
5. Back up before editing production artifacts.
