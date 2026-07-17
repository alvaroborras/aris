---
name: paper-writing
description: 'Workflow 3: Full paper writing pipeline that goes from a narrative report to a polished, submission-ready PDF. Use when user says "写论文全流程", "write paper pipeline", "从报告到PDF", "paper writing", or wants the complete paper generation workflow.'
---

# Workflow 3: Paper Writing Pipeline

> **Codex assurance:** every base semantic audit is same-family provisional.
> The pipeline still completes when all mandatory audits are green, but the
> Final Report must say `Submission-ready: provisional`; only cross-family or
> deterministic accepted audit coverage may say `yes`.

Orchestrate a complete paper writing workflow for: **the user's request**

## Overview

This skill chains five sub-skills into a single automated pipeline:

```
$paper-plan → $paper-figure → $paper-write → $paper-compile → $auto-paper-improvement-loop
  (outline)     (plots)        (LaTeX)        (build PDF)       (review & polish ×2)
```

Each phase builds on the previous one's output. The final deliverable is a polished, reviewed `paper/` directory with LaTeX source and compiled PDF.

In this hybrid pack, the pipeline itself is unchanged, but `paper-plan` and `paper-write` use Orchestra-adapted shared references for stronger story framing and prose guidance.

## Constants

- **VENUE = `ICLR`** — Target venue. Options: `ICLR`, `NeurIPS`, `ICML`, `CVPR`, `ACL`, `AAAI`, `ACM`, `IEEE_JOURNAL` (IEEE Transactions / Letters), `IEEE_CONF` (IEEE conferences). Affects style file, page limit, citation format.
- **MAX_IMPROVEMENT_ROUNDS = 2** — Number of review→fix→recompile rounds in the improvement loop.
- **REVIEWER_MODEL = `gpt-5.6-sol`** — Model used via Codex subagent capability for plan review, figure review, writing review, and improvement loop.
- **AUTO_PROCEED = true** — Auto-continue between phases. Set `false` to pause and wait for user approval after each phase.
- **HUMAN_CHECKPOINT = false** — When `true`, the improvement loop (Phase 5) pauses after each round's review to let you see the score and provide custom modification instructions. When `false` (default), the loop runs fully autonomously. Passed through to `$auto-paper-improvement-loop`.
- **ILLUSTRATION = `figurespec`** — Architecture/illustration generator for Phase 2b: `figurespec` (default, deterministic JSON→SVG via `$figure-spec`, best for architecture/workflow/topology), `gemini` (AI-generated via `$paper-illustration`, best for qualitative method illustrations; needs `GEMINI_API_KEY`), `mermaid` (Mermaid syntax via `$mermaid-diagram`, free, best for flowcharts), or `false` (skip Phase 2b, manual only).

> Override inline: `$paper-writing "NARRATIVE_REPORT.md" — venue: NeurIPS, illustration: gemini, human checkpoint: true`
> IEEE example: `$paper-writing "NARRATIVE_REPORT.md" — venue: IEEE_JOURNAL`

## Inputs

This pipeline accepts one of:

1. **`NARRATIVE_REPORT.md`** (best) — structured research narrative with claims, experiments, results, figures
2. **Research direction + experiment results** — the skill will help draft the narrative first
3. **Existing `PAPER_PLAN.md`** — skip Phase 1, start from **Phase 1.5** (the contract negotiation still runs; only resuming a genuine pre-1.5 legacy run may skip it, and then Phase 6.0's row 0 records "no contract")

The more detailed the input (especially figure descriptions and quantitative results), the better the output.

## Detailed Protocol

Before executing the workflow, read [references/detailed-protocol.md](references/detailed-protocol.md) completely. Treat its workflow, output templates, and completion rules as normative.
