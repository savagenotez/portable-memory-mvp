# Portable Memory MVP - Demo Runbook

Run ID: `run-20260324T214221Z-429eb2dd`
Customer deck: `portable-memory-customer-deck-run-20260324T214221Z-429eb2dd.pptx`
Investor deck: `portable-memory-investor-deck-run-20260324T214221Z-429eb2dd.pptx`

## Opening Goal
Show that robustness-aware pruning preserves continuity while reducing context more safely than simpler approaches.

## Scenario
- Scenario ID: `mixed_constraints_plus_identity`
- Title: `Mixed-recall: constraints plus identity`
- Query: What are the main constraints and what system is being built?
- Expected phrases: `['fastest_working_prototype', 'portable memory package', 'mergeable memory container']`

## Presenter Setup
- Open customer deck: portable-memory-customer-deck-run-20260324T214221Z-429eb2dd.pptx
- Keep investor deck available for follow-up: portable-memory-investor-deck-run-20260324T214221Z-429eb2dd.pptx
- Keep the demo script markdown open in a side pane or second monitor.
- Be ready to zoom in on the comparison previews for compression, hybrid, and robustness-aware pruning.

## Demo Sequence
### Step 1
- Screen action: Show customer deck slide 1
- Say: We help AI systems keep continuity without dragging around bloated context.
- Goal: Set the audience frame fast.

### Step 2
- Screen action: Show customer deck slides 2 and 3
- Say: The core problem is that most systems either keep too much context or lose important meaning. Our approach rescues the needed context, then prunes only when meaning remains robust.
- Goal: Explain the problem and solution in plain language.

### Step 3
- Screen action: Show the selected benchmark scenario title and query
- Say: We will use this benchmark scenario: Mixed-recall: constraints plus identity. The question is: What are the main constraints and what system is being built?
- Goal: Ground the demo in one concrete case.

### Step 4
- Screen action: Show compression preview
- Say: Compression mode gets retrieval hit rate 0.6667 and context reduction -15.12. It compresses, but it risks losing critical context structure.
- Goal: Establish the low-cost baseline.

### Step 5
- Screen action: Show hybrid preview
- Say: Hybrid mode rescues important meaning, but context reduction is -15.12, which means it still carries too much baggage.
- Goal: Show rescue without disciplined pruning.

### Step 6
- Screen action: Show robustness-aware pruning preview
- Say: Robustness-aware pruning keeps retrieval hit rate 0.6667 and soft hit rate 0.6667 while improving context reduction to 59.42.
- Goal: Show the main win clearly.

### Step 7
- Screen action: Show customer deck core metrics slide
- Say: This is the important point: we are not just compressing. We are preserving the minimum robust meaning needed for continuity.
- Goal: Turn the example into the product claim.

### Step 8
- Screen action: Show customer deck deployment-fit slide
- Say: This fits enterprise copilots, long-session assistants, support workflows, and memory middleware for AI products.
- Goal: Connect the demo to buyer use cases.

### Step 9
- Screen action: Show trustworthiness / validation slide
- Say: This policy also held up under adversarial validation, which matters because real users paraphrase and vary wording.
- Goal: Reinforce confidence.

### Step 10
- Screen action: Close on next-customer-step slide
- Say: The next step with a customer is simple: run this against their own traces and measure cost savings and continuity quality.
- Goal: Create a direct call to action.

## Comparison Snapshot
### compression_mode
- Retrieval hit rate: `0.6667`
- Soft hit rate: `0.6667`
- Context reduction percent: `-15.12`
- Preview:

```text
Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
```

### hybrid_mode
- Retrieval hit rate: `0.6667`
- Soft hit rate: `0.6667`
- Context reduction percent: `-15.12`
- Preview:

```text
Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
Fact: project.goal = The goal is to make this work across Codex CLI and Claude Code. Optimize for fastest working prototype.
Project: Portable memory system planning. Status: active. Summary: Portable, persistent, mergeable AI memory system for continuity across chats and agents.
```

### robustness_aware_pruning_mode
- Retrieval hit rate: `0.6667`
- Soft hit rate: `0.6667`
- Context reduction percent: `59.42`
- Pruned line count: `2`
- Controller choice: `robust_pruned_phrase_saver`
- Preview:

```text
Fact: product.core_definition = We want a portable memory package for AI chats. The real product is a mergeable memory container. Be direct and grounded.
```

## Objection Handling
- Objection: Why not just summarize harder?
  - Response: Because harder summarization often loses the exact constraints and identity details that matter next. This policy is designed to preserve robust meaning, not just shorten text.
- Objection: Why is this better than retrieval alone?
  - Response: Retrieval can bring back too much or the wrong thing. This controller rescues useful context and then prunes safely under robustness constraints.
- Objection: How do you know it is reliable?
  - Response: It was benchmarked across exact, soft, and adversarial checks, and robustness-aware pruning was unbeaten across the current scenario set.
- Objection: What is the business value?
  - Response: Lower context cost, stronger continuity, fewer dropped details, and a more trustworthy memory layer for assistants and copilots.

## Presenter Notes
### Tone
- Keep the explanation concrete and operational.
- Do not over-explain algorithms before the win is visible.
- Emphasize lower cost plus better continuity together.

### Timing
- 30 seconds for the problem.
- 60 seconds for the scenario walkthrough.
- 30 seconds for the metrics.
- 30 seconds for use cases and call to action.

### Must-Say Lines
- This is minimum robust meaning for continuity.
- We are not just summarizing; we are preserving what matters under variation.
- The result is lower context cost without sacrificing continuity quality.
