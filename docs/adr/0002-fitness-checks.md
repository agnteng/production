# 0002. Every past failure becomes a fitness check

- Status: Accepted
- Date: 2026-11-13

## Context
The same classes of failure kept costing time: internal names leaking into
public text, media and scratch files handled as if they were source, and
hand-copied text drifting between a talk's descriptions.

## Decision
`scripts/fitness.py` describes a healthy repository as checks, run locally
with `mise run fitness` and in CI on every push and pull request. When
something breaks in a way no check caught, add a check before closing the
fix.

## Consequences
CI needs the `PUBLIC_DENYLIST` secret.
