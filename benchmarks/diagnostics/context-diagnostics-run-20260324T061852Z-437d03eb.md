# Context Diagnostics Report

- Run ID: `run-20260324T061852Z-437d03eb`
- Timestamp: `2026-03-24T06:18:52Z`
- Merge success rate: `1.0`

## Scenario: Project and constraints retrieval

- Query: `What is the project and what are the constraints?`
- Expected phrases: 4

### recall_mode

- Retrieval hit rate: `0.75`
- Context reduction percent: `-254.38`
- Repeated explanation items removed: `3`
- Preview bytes: `1336`
- Preview entropy bits: `5.8305`
- Preview lines: `6`

#### Likely durable lines
- L1: Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L2: Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- L5: Conversation: Portable memory system follow-up. Summary: Portable memory system follow-up: user: The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype. | assistant: Got it.

#### Likely situational lines
- L3: Conversation: Portable memory system planning. Summary: Portable memory system planning: user: We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded. | assistant: Understood.
- L6: Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.

#### Likely costly lines
- L6 (319 bytes): Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.
- L4 (273 bytes): Conversation: Portable memory system durable updates. Summary: Portable memory system durable updates: user: We want Codex CLI and Claude Code to share the same memory layer. Working context should be assembled from structured state, not raw transcript. | assistant: Noted.
- L3 (241 bytes): Conversation: Portable memory system planning. Summary: Portable memory system planning: user: We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded. | assistant: Understood.
- L5 (221 bytes): Conversation: Portable memory system follow-up. Summary: Portable memory system follow-up: user: The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype. | assistant: Got it.
- L1 (153 bytes): Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.

### compression_mode

- Retrieval hit rate: `0.75`
- Context reduction percent: `-15.12`
- Repeated explanation items removed: `3`
- Preview bytes: `434`
- Preview entropy bits: `5.3106`
- Preview lines: `3`

#### Likely durable lines
- L1: Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L2: Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- L3: Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.

#### Likely costly lines
- L3 (155 bytes): Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- L1 (153 bytes): Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L2 (124 bytes): Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.

### hybrid_mode

- Retrieval hit rate: `0.75`
- Context reduction percent: `-15.12`
- Repeated explanation items removed: `3`
- Preview bytes: `434`
- Preview entropy bits: `5.3106`
- Preview lines: `3`

#### Likely durable lines
- L1: Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L2: Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- L3: Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.

#### Likely costly lines
- L3 (155 bytes): Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- L1 (153 bytes): Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L2 (124 bytes): Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.

## Scenario: Durable update retrieval

- Query: `What has now been proven and what should happen next?`
- Expected phrases: 4

### recall_mode

- Retrieval hit rate: `1.0`
- Context reduction percent: `-107.64`
- Repeated explanation items removed: `4`
- Preview bytes: `1250`
- Preview entropy bits: `5.8997`
- Preview lines: `6`

#### Likely durable lines
- L3: Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- L4: Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- L5: Conversation: Portable memory system follow-up. Summary: Portable memory system follow-up: user: The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype. | assistant: Got it.
- L6: Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.

#### Likely situational lines
- L1: Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.

#### Likely costly lines
- L1 (319 bytes): Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.
- L2 (273 bytes): Conversation: Portable memory system durable updates. Summary: Portable memory system durable updates: user: We want Codex CLI and Claude Code to share the same memory layer. Working context should be assembled from structured state, not raw transcript. | assistant: Noted.
- L5 (221 bytes): Conversation: Portable memory system follow-up. Summary: Portable memory system follow-up: user: The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype. | assistant: Got it.
- L3 (155 bytes): Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- L6 (153 bytes): Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.

### compression_mode

- Retrieval hit rate: `0.25`
- Context reduction percent: `27.91`
- Repeated explanation items removed: `1`
- Preview bytes: `434`
- Preview entropy bits: `5.3106`
- Preview lines: `3`

#### Likely durable lines
- L1: Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- L2: Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L3: Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.

#### Likely costly lines
- L3 (155 bytes): Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- L2 (153 bytes): Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L1 (124 bytes): Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.

### hybrid_mode

- Retrieval hit rate: `1.0`
- Context reduction percent: `-25.25`
- Repeated explanation items removed: `4`
- Preview bytes: `754`
- Preview entropy bits: `5.8345`
- Preview lines: `4`

#### Likely durable lines
- L1: Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
- L2: Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L3: Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.

#### Likely situational lines
- L4: Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.

#### Likely costly lines
- L4 (319 bytes): Conversation: Durable update ingestion. Summary: Durable update ingestion: user: New durable update: - Codex CLI and Claude Code should share the same memory layer. - Working context should be assembled from structured state, not raw transcript. - The memory package system has now | assistant: Durable update recorded.
- L3 (155 bytes): Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
- L2 (153 bytes): Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
- L1 (124 bytes): Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
