# Upgrade Rules Report

- Source diagnostics run: `run-20260324T061852Z-437d03eb`
- Source timestamp: `2026-03-24T06:18:52Z`

## Synthesized Rules

### R1 - Always prefer high-durability core lines
- Why: These lines repeatedly survive in high-recall and hybrid modes.
- Action: Promote preference/fact/project lines with strong durability and centrality into the default retained set.

### R2 - Protect phrase-saving situational lines
- Why: These lines help recover expected phrases even when compression is active.
- Action: Allow a small budget for query-relevant situational lines when they restore missed expected phrases.

### R4 - Compress costly lines unless they save recall
- Why: These lines consume many bytes and often drive negative context reduction.
- Action: Only keep costly lines when they materially improve expected-phrase coverage or central project state.

## Keep Priority Lines

- score=3 | kind=fact | cost=124 | Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- score=3 | kind=fact | cost=153 | Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- score=3 | kind=project | cost=155 | Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.

## Durable Core Lines

- score=10 | kind=fact | cost=153 | Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- score=10 | kind=fact | cost=124 | Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- score=8 | kind=project | cost=155 | Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- score=4 | kind=conversation | cost=221 | Conversation: Portable memory system follow-up. Summary: Portable memory system follow-up: user: The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype. | assistant: Got it.

## Costly Compression Candidates

- score=6 | kind=fact | cost=153 | Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- score=5 | kind=durable_update | cost=319 | Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.
- score=4 | kind=durable_update | cost=273 | Conversation: Portable memory system durable updates. Summary: Portable memory system durable updates: user: We want Codex CLI and Claude Code to share the same memory layer. Working context should be assembled from structured state, not raw transcript. | assistant: Noted.
- score=4 | kind=conversation | cost=221 | Conversation: Portable memory system follow-up. Summary: Portable memory system follow-up: user: The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype. | assistant: Got it.
- score=4 | kind=project | cost=155 | Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- score=2 | kind=conversation | cost=241 | Conversation: Portable memory system planning. Summary: Portable memory system planning: user: We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded. | assistant: Understood.
- score=2 | kind=fact | cost=124 | Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.

## Phrase Saver Lines

- score=4 | kind=durable_update | cost=319 | Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.
- score=1 | kind=conversation | cost=241 | Conversation: Portable memory system planning. Summary: Portable memory system planning: user: We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded. | assistant: Understood.

## Decision Hints

- compress_or_drop | keep=4 drop=5 | recall=2 comp=0 hybrid=1 | Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.
- compress_or_drop | keep=0 drop=4 | recall=2 comp=0 hybrid=0 | Conversation: Portable memory system durable updates. Summary: Portable memory system durable updates: user: We want Codex CLI and Claude Code to share the same memory layer. Working context should be assembled from structured state, not raw transcript. | assistant: Noted.
- review | keep=4 drop=4 | recall=2 comp=0 hybrid=0 | Conversation: Portable memory system follow-up. Summary: Portable memory system follow-up: user: The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype. | assistant: Got it.
- compress_or_drop | keep=1 drop=2 | recall=1 comp=0 hybrid=0 | Conversation: Portable memory system planning. Summary: Portable memory system planning: user: We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded. | assistant: Understood.
- keep_or_prefer | keep=13 drop=6 | recall=2 comp=2 hybrid=2 | Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- keep_or_prefer | keep=13 drop=2 | recall=2 comp=2 hybrid=2 | Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- keep_or_prefer | keep=11 drop=4 | recall=1 comp=2 hybrid=2 | Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
