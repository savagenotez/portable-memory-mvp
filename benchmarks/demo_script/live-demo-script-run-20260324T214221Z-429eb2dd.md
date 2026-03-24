# Portable Memory MVP - Live Demo Script

Run ID: `run-20260324T214221Z-429eb2dd`
Scenario: `Mixed-recall: constraints plus identity`

## Selected Scenario
- Scenario ID: `mixed_constraints_plus_identity`
- Query: What are the main constraints and what system is being built?
- Expected phrases: `['fastest_working_prototype', 'portable memory package', 'mergeable memory container']`

## Talk Track
- Start by stating the problem: memory systems either keep too much context or lose important meaning.
- Show the selected scenario and the user question.
- Show compression mode first and explain what it saves, but point out what it risks losing.
- Show hybrid mode next and explain that it rescues meaning, but grows context too much.
- Show robustness-aware pruning last and explain that it keeps the rescue value while cutting context safely.
- Call out the exact metrics on screen: retrieval hit rate, soft hit rate, and context reduction percent.
- Close with the message that this is minimum robust meaning for continuity, not naive summarization.

## Demo Flow
### Step 1: Frame the problem
- Script: We need memory that preserves continuity without dragging unnecessary context forward.

### Step 2: Introduce the scenario
- Script: Here is a real benchmark scenario: Mixed-recall: constraints plus identity. The query is: What are the main constraints and what system is being built?

### Step 3: Show compression baseline
- Script: Compression mode gets hit rate 0.6667 with context reduction -15.12. It compresses, but risks losing meaning.
- Preview:

```text
Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
```

### Step 4: Show hybrid rescue
- Script: Hybrid mode rescues meaning with hit rate 0.6667, but context reduction is -15.12, which means it is still bloated.
- Preview:

```text
Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
```

### Step 5: Show robustness-aware pruning
- Script: Robustness-aware pruning keeps hit rate 0.6667 and soft hit rate 0.6667 while reaching context reduction 59.42.
- Preview:

```text
Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
```

### Step 6: Explain why it wins
- Script: It starts from rescued context, then prunes only when exact recall, soft recall, and overlap robustness remain intact.

### Step 7: Close with business value
- Script: That means lower context cost, stronger continuity, and more trustworthy memory behavior for real AI products.

## Comparison Snapshot
### compression_mode
- Retrieval hit rate: `0.6667`
- Soft hit rate: `0.6667`
- Context reduction percent: `-15.12`

### hybrid_mode
- Retrieval hit rate: `0.6667`
- Soft hit rate: `0.6667`
- Context reduction percent: `-15.12`

### robustness_aware_pruning_mode
- Retrieval hit rate: `0.6667`
- Soft hit rate: `0.6667`
- Context reduction percent: `59.42`
- Pruned line count: `2`
- Controller choice: `robust_pruned_phrase_saver`
