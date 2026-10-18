# ExPyRi — Statement of Intent

*Confirmed via interview on 2026-10-18. This document is the upstream source of truth for specs, plans, and task breakdowns.*

## Outcome

Take real-world experiment data (typically grouped conditions, e.g. A, B, C…) through a guided wizard to trustworthy statistical results — with guardrails that prevent a knowledgeable-but-not-expert user from statistical misuse.

## User

Educated professionals (scientists, engineers, researchers) with a **basic** understanding of statistics — not novices, not full-time statisticians. They know what a t-test is; they don't know when it's wrong. They work on real experiments and need trustworthy information about them.

## Why this exists

The author supports these users professionally (consulting, IT, methods support) and sees the same statistical misuse firsthand. The wizard encodes the expert judgment these users lack access to, so they can self-serve safely on real experiments.

## Success

A **1.0 that can be confidently put in front of real users/clients**. Two things in focus, in order:

1. **Guardrails** — the applicability guidance that makes the result trustworthy for a non-expert.
2. **A fine report** — supporting further discussion of the experiment (e.g. with a statistician or supervisor).

The gap from 0.9.x to 1.0 is about correctness assurance, not feature count.

## Binding Constraint

**Correctness.** The guidance must never produce a statistically wrong result. A wrong answer is worse than no tool, because professional credibility backs this tool.

## Out of Scope

- Full statistical suite (SPSS/JASP/R replacement)
- Modeling / regression beyond basics
- Bayesian methods
- Power analysis / sample-size planning
