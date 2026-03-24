# Codex CLI Workflow Example

This document shows how Portable Memory MVP can fit into a Codex CLI style workflow.

## Goal

Preserve durable project state across multiple coding sessions instead of depending only on transcript continuity.

## Workflow idea

1. Start with existing working context
2. Read durable memory files before work
3. Perform implementation work
4. Write durable updates back into memory notes
5. Re-ingest those updates into the memory system
6. Retrieve refreshed context for the next session

## Example local memory files

- .ai-memory/context/working_context.md
- .ai-memory/current_package.json
- .ai-memory/UPDATE_NOTES.md
- AGENTS.md

## Suggested Codex session pattern

Before starting:
- read .ai-memory/context/working_context.md
- read AGENTS.md
- inspect current repo state

During work:
- make changes normally
- keep track of durable facts, constraints, decisions, and tasks

After work:
- append important durable updates to .ai-memory/UPDATE_NOTES.md
- ingest that note back into Portable Memory MVP as a new session
- retrieve refreshed project context

## Example durable update note

New durable update:
- Added benchmark scaffolding to the repo
- Added proof-of-work documentation
- Next step is to create Codex CLI and Claude Code workflow examples

## Why this helps

Instead of forcing the next coding session to reconstruct state from raw history, the workflow turns important updates into durable memory inputs.

## Current status

This is a workflow example, not yet a live Codex CLI integration harness.
