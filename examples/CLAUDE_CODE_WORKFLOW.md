# Claude Code Workflow Example

This document shows how Portable Memory MVP can fit into a Claude Code style workflow.

## Goal

Make project continuity depend on structured durable memory, not only on long conversation context.

## Workflow idea

1. Read working context before starting
2. Use durable memory as the project state anchor
3. Perform implementation work
4. Write durable updates after important changes
5. Re-ingest those updates into the memory layer
6. Retrieve updated context for the next session

## Example local memory files

- .ai-memory/context/working_context.md
- .ai-memory/current_package.json
- .ai-memory/UPDATE_NOTES.md
- CLAUDE.md

## Suggested Claude Code session pattern

Before starting:
- read .ai-memory/context/working_context.md
- read CLAUDE.md
- inspect current repo state

During work:
- make changes normally
- keep note of durable constraints, decisions, and newly proven outcomes

After work:
- write durable updates into .ai-memory/UPDATE_NOTES.md
- ingest that note back into Portable Memory MVP
- regenerate working context for the next session

## Example durable update note

New durable update:
- Claude Code workflow example added
- Benchmark scaffolding is now present in the repo
- Next step is a runnable benchmark module

## Why this helps

The next session can recover important state from structured memory artifacts instead of depending only on long transcript recall.

## Current status

This is a workflow example, not yet a live Claude Code integration harness.
