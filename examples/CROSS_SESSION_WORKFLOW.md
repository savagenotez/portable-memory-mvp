# Cross-Session Workflow Example

This document shows the intended continuity loop across multiple sessions and agents.

## Core loop

Session 1:
- ingest project planning transcript
- create package state

Session 2:
- ingest follow-up transcript
- accumulate more state

Session 3:
- retrieve current context
- write working context into .ai-memory/context/working_context.md

Session 4:
- write durable update note
- ingest durable update note as new session
- retrieve updated context again

## General agent pattern

Any agent or CLI can follow this pattern:

1. Read durable working context
2. Perform work
3. Write durable updates
4. Re-ingest durable updates
5. Retrieve updated state for the next run

## Why this matters

The memory layer becomes the continuity backbone across:
- multiple sessions
- multiple agents
- multiple coding tools

## What is already proven

The prototype has already demonstrated:
- session ingest
- multi-session accumulation
- retrieval
- durable update note ingestion
- working context regeneration

## What is not yet proven

Not yet proven:
- live multi-tool orchestration
- automated Codex CLI handoff
- automated Claude Code handoff
- benchmarked workflow superiority

## Next step

Build runnable workflow helpers and benchmark those workflows against transcript-only continuation.
