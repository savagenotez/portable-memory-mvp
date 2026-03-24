# Non-Pruning Adversarial Winner Analysis

- Source adversarial summary: `adversarial-winner-summary-run-20260324T131334Z-516d87ae.json`
- Source adversarial validation: `adversarial-pruning-validation-run-20260324T131334Z-516d87ae.json`
- Source benchmark run: `run-20260324T131334Z-516d87ae.json`
- Run ID: `run-20260324T131334Z-516d87ae`
- Non-pruning winner scenarios: `2`

## Mixed-recall: project plus next step

- Winner mode: `hybrid_mode`
- Winner adversarial hit rate: `1.0`
- Pruning adversarial hit rate: `0.75`
- Winner soft hit rate: `0.75`
- Pruning soft hit rate: `0.75`
- Winner exact hit rate: `0.75`
- Pruning exact hit rate: `0.75`
- Winner context reduction percent: `-25.25`
- Pruning context reduction percent: `47.01`
- Winner bytes: `754`
- Pruning bytes: `319`

### Likely reasons
- winner_has_higher_adversarial_variant_hit_rate
- winner_kept_more_context_than_pruning
- winner_preserved_better_token_overlap_for_some_phrases

### Exact-missing phrases
- Winner missing: ['Portable Memory MVP']
- Pruning missing: ['Portable Memory MVP']

### Phrase-level differences
- `Portable Memory MVP` | winner_exact=False pruning_exact=False | winner_overlap=0.6667 pruning_overlap=0.3333 | winner_adv=True pruning_adv=False
- `durable update ingestion` | winner_exact=True pruning_exact=True | winner_overlap=1.0 pruning_overlap=1.0 | winner_adv=True pruning_adv=True
- `Codex CLI` | winner_exact=True pruning_exact=True | winner_overlap=1.0 pruning_overlap=1.0 | winner_adv=True pruning_adv=True
- `Claude Code` | winner_exact=True pruning_exact=True | winner_overlap=1.0 pruning_overlap=1.0 | winner_adv=True pruning_adv=True

## Mixed-recall: constraints plus identity

- Winner mode: `compression_mode`
- Winner adversarial hit rate: `1.0`
- Pruning adversarial hit rate: `0.6667`
- Winner soft hit rate: `1.0`
- Pruning soft hit rate: `0.6667`
- Winner exact hit rate: `1.0`
- Pruning exact hit rate: `0.6667`
- Winner context reduction percent: `-15.12`
- Pruning context reduction percent: `59.42`
- Winner bytes: `434`
- Pruning bytes: `153`

### Likely reasons
- winner_has_higher_adversarial_variant_hit_rate
- winner_kept_more_context_than_pruning
- winner_preserved_better_token_overlap_for_some_phrases

### Exact-missing phrases
- Winner missing: ['fastest_working_prototype']
- Pruning missing: ['fastest_working_prototype']

### Phrase-level differences
- `fastest_working_prototype` | winner_exact=False pruning_exact=False | winner_overlap=1.0 pruning_overlap=0.0 | winner_adv=True pruning_adv=False
- `portable memory package` | winner_exact=True pruning_exact=True | winner_overlap=1.0 pruning_overlap=1.0 | winner_adv=True pruning_adv=True
- `mergeable memory container` | winner_exact=True pruning_exact=True | winner_overlap=1.0 pruning_overlap=1.0 | winner_adv=True pruning_adv=True
