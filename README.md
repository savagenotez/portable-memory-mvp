# Portable Memory MVP

Portable Memory MVP is an early prototype for a portable, persistent, mergeable AI memory layer.

It is designed to prove that knowledge from one session can be:
- extracted
- stored
- merged
- retrieved
- carried into later sessions without starting from scratch

## What this prototype currently proves

This version has already demonstrated:
- transcript ingest works
- package creation works
- multi-session accumulation works
- retrieval works
- durable update note ingestion works
- working context regeneration works

## Core idea

The core idea is not transcript replay.

The core idea is:

a structured memory package that survives across sessions and can be merged forward

This allows an AI workflow to preserve:
- project state
- constraints
- durable updates
- prior decisions
- accumulated context

## Current architecture

- app.py - FastAPI MVP
- sample_payloads/ - sample transcripts for testing
- .ai-memory/ - working memory files
- artifacts/ - successful proof outputs
- docs/ - status, runbook, packaging notes

## Quick start

Open PowerShell in this folder and run:

powershell -ExecutionPolicy Bypass -File .\dist\portable_memory_automation_clean\start-clean.ps1

Or run the app manually:

.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8011

Then open the docs URL shown in the terminal.

## What success looks like

A successful run should allow you to:
- ingest multiple sessions
- retrieve accumulated project context
- ingest durable update notes
- regenerate a working context file
- continue without fully re-explaining prior state

## Current proof artifacts

See:
- artifacts/automation-results.json
- artifacts/step3-results.json
- artifacts/step4-results.json
- artifacts/package-ids.txt
- artifacts/working_context_snapshot.md

## Current status

This is still an early prototype, not a production-ready system.

Not yet included:
- enterprise auth
- robust conflict UI
- benchmark module
- MCP adapter
- Codex/Claude live integration harness
- production reliability hardening

## Next steps

- benchmark module
- automated port-safe bootstrap
- Codex CLI workflow example
- Claude Code workflow example
- open-source cleanup
- MCP-compatible interface layer

## Why this matters

This project is exploring whether AI systems can carry forward durable working state in a structured way instead of relying on raw transcript length alone.
