# Portable Memory MVP

Portable Memory MVP is an early open-source prototype for a portable, persistent, mergeable AI memory layer.

It is built to test a simple but important idea:

Can an AI system carry forward durable working state across sessions instead of repeatedly starting over from raw transcript history alone?

This prototype demonstrates an early yes.

It shows that session knowledge can be:
- ingested from transcripts
- turned into structured package state
- accumulated across sessions
- retrieved later as usable working context
- extended with durable update notes that re-enter the memory stream

## What this prototype currently proves

This version has already demonstrated:
- transcript ingest works
- package creation works
- multi-session accumulation works
- retrieval works
- durable update note ingestion works
- working context regeneration works

## Why this matters

Most AI workflows still rely heavily on fragile session history and repeated re-explanation.

This project explores a different direction:

a structured memory package that survives across sessions and can be merged forward

That makes it possible to preserve:
- project state
- constraints
- durable updates
- prior decisions
- accumulated working context

## Current status

This is an early working prototype, not a production-ready system.

It is best understood as:
- a proof of concept
- an open prototype
- a foundation for future benchmarks, integrations, and workflow tooling

## Repository contents

- app.py - FastAPI MVP
- sample_payloads/ - sample transcripts for testing
- .ai-memory/ - working memory files
- artifacts/ - proof outputs from successful runs
- docs/ - status, runbook, and packaging notes

## Quick start

Run locally with:

.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8011

Then open the docs endpoint shown in the terminal.

## What comes next

Planned next steps include:
- benchmark module
- cleaner startup automation
- Codex CLI workflow example
- Claude Code workflow example
- MCP-compatible interface layer
- stronger conflict handling and evaluation
