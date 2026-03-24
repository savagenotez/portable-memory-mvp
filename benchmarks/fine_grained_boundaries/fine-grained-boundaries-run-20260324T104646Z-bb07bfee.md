# Fine-Grained Boundary Mining

- Source run: `run-20260324T104646Z-bb07bfee.json`
- Run ID: `run-20260324T104646Z-bb07bfee`
- Scenario count: `13`

## Mined Rules

### phrase_saver_when_compression_misses_and_saver_can_restore
- Preferred mode: `phrase_saver_per_byte_mode`
- Evidence count: `0`
- Conditions:
  - missing_under_compression_count >= 1
  - top_phrase_saver_restored >= 1
- Notes: Use phrase-saver rescue when compression drops required phrases and local saver evidence exists.

### hybrid_when_compression_misses_and_phrase_saver_signal_is_absent
- Preferred mode: `hybrid_mode`
- Evidence count: `5`
- Conditions:
  - missing_under_compression_count >= 1
  - top_phrase_saver_restored == 0 OR phrase_saver insufficient
- Notes: Use hybrid when compression misses required phrases and local middle-strength rescue is absent or insufficient.

### fragment_when_fragment_signal_is_real_and_small_gap_remains
- Preferred mode: `phrase_fragment_per_byte_mode`
- Evidence count: `1`
- Conditions:
  - missing_under_compression_count >= 1
  - top_fragment_restored >= 1
  - top_fragment_ppc > 0
- Notes: Use fragment rescue only when fragment evidence is real.

### compression_when_nothing_important_is_missing
- Preferred mode: `compression_mode`
- Evidence count: `3`
- Conditions:
  - missing_under_compression_count == 0
- Notes: Keep compression when it already preserves required signal.

### do_not_force_compression_when_required_phrases_are_missing
- Preferred mode: `threshold_gated_adaptive_mode`
- Evidence count: `2`
- Conditions:
  - learned_choice == compression_mode
  - missing_under_compression_count >= 1
- Notes: Coarse learned boundaries over-compress when missing phrases are not explicitly checked.

### phrase_saver_is_primary_middle_state
- Preferred mode: `phrase_saver_per_byte_mode`
- Evidence count: `12`
- Conditions:
  - saver_equals_threshold on many scenarios
- Notes: Phrase-saver is the key middle-strength rescue mode.

## Scenario Notes

### Project and constraints retrieval
- Scenario ID: `project_and_constraints`
- Threshold choice: `hybrid_fallback`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `1`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Durable update retrieval
- Scenario ID: `durable_update_retrieval`
- Threshold choice: `fragment_escalation`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `3`
- Top phrase-saver restored: `3`
- Top fragment restored: `3`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.032258`
- Threshold beats learned: `True`

### Project and constraints core retrieval
- Scenario ID: `project_constraints_core`
- Threshold choice: `hybrid_fallback`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `1`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Durable update and current state retrieval
- Scenario ID: `durable_update_state`
- Threshold choice: `phrase_saver_escalation`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `3`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `True`

### Workflow continuity across tools
- Scenario ID: `workflow_continuity_tools`
- Threshold choice: `phrase_saver_escalation`
- Learned choice: `hybrid_mode`
- Classifier choice: `None`
- Missing under compression: `2`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Proof boundary and non-proven areas
- Scenario ID: `proof_and_scope_boundary`
- Threshold choice: `phrase_saver_escalation`
- Learned choice: `hybrid_mode`
- Classifier choice: `None`
- Missing under compression: `3`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### System identity summary retrieval
- Scenario ID: `memory_identity_summary`
- Threshold choice: `compression_seed`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `0`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Low-recall: lightweight repo identity
- Scenario ID: `lightweight_repo_identity`
- Threshold choice: `hybrid_fallback`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `1`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Low-recall: tooling note
- Scenario ID: `lightweight_tooling_note`
- Threshold choice: `compression_seed`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `0`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Low-recall: goal only
- Scenario ID: `lightweight_goal_only`
- Threshold choice: `compression_seed`
- Learned choice: `compression_mode`
- Classifier choice: `None`
- Missing under compression: `0`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Mixed-recall: project plus next step
- Scenario ID: `mixed_project_plus_next_step`
- Threshold choice: `hybrid_fallback`
- Learned choice: `hybrid_mode`
- Classifier choice: `None`
- Missing under compression: `2`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Mixed-recall: constraints plus identity
- Scenario ID: `mixed_constraints_plus_identity`
- Threshold choice: `hybrid_fallback`
- Learned choice: `hybrid_mode`
- Classifier choice: `None`
- Missing under compression: `1`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`

### Mixed-recall: proof and workflow
- Scenario ID: `mixed_proof_and_workflow`
- Threshold choice: `phrase_saver_escalation`
- Learned choice: `hybrid_mode`
- Classifier choice: `None`
- Missing under compression: `1`
- Top phrase-saver restored: `0`
- Top fragment restored: `0`
- Top phrase-saver ppb: `0.0`
- Top fragment ppc: `0.0`
- Threshold beats learned: `False`
