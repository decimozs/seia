# Regtrace CLI Reference

## Synopsis

```bash
regtrace <command> [options]
```

## Global options

| Flag | Description |
|------|-------------|
| `--config <path>` | Path to config file (default: `regtrace.config.yaml`) |
| `--verbose` | Enable verbose logging |
| `--version` | Show version number |
| `--help` | Show help |

## Commands

### `init`

Scaffold a new regtrace project. Creates `regtrace.config.yaml`,
`golden-sets/qa.yaml`, `.env.example`, and `.gitignore`.

```bash
regtrace init [options]
```

| Option | Description |
|--------|-------------|
| `--dir <path>` | Target directory (default: current dir) |
| `--force` | Overwrite existing files without prompt |

### `run`

Run evaluation on all enabled golden sets.

```bash
regtrace run [options]
```

| Option | Description |
|--------|-------------|
| `--config <path>` | Path to config file |
| `--set <name>` | Run a specific golden set (path or alias) |
| `--trigger <type>` | Trigger type: cli, ci, watch (default: cli) |
| `--format <type>` | Output: terminal, json, markdown (default: terminal) |
| `--output <path>` | Write report to file |
| `--ci` | CI mode — exit 1 on quality gate failure |
| `--no-ci` | Disable CI mode auto-detection |
| `--verbose` | Show all test cases (including passing) |
| `--quiet` | Suppress human-readable output (only errors shown) |
| `--dry-run` | Validate config, golden sets, env without evaluating |
| `--bail` | Stop after first suite that fails quality gates |
| `--generate` | Auto-generate actual_output from LLM for null cases |

**Common flag combinations:**

```bash
regtrace run                              # default terminal output
regtrace run --format json                # JSON to stdout, pipeable to jq
regtrace run --format json -o report.json # JSON to file
regtrace run --format markdown -o report.md  # Markdown report
regtrace run --ci                         # CI mode, no color, exit 1 on failure
regtrace run --ci --bail                  # CI mode, stop early
regtrace run --dry-run                    # validate without running
regtrace run --set my-set.yaml            # run a single golden set
regtrace run --generate                   # auto-generate null outputs then evaluate
regtrace run --quiet                      # suppress progress, show only errors
```

### `list`

List recent evaluation runs.

```bash
regtrace list [options]
```

| Option | Description |
|--------|-------------|
| `--config <path>` | Path to config file |

### `history`

Show detailed run information.

```bash
regtrace history [options]
```

| Option | Description |
|--------|-------------|
| `--config <path>` | Path to config file |
| `--run-id <id>` | Show a specific run |
| `--diff <run-a> [run-b]` | Diff against another run |

### `watch`

Watch golden set files for changes and re-run evaluation.

```bash
regtrace watch [options]
```

| Option | Description |
|--------|-------------|
| `--config <path>` | Path to config file |

### `baseline`

Manage regression baselines.

```bash
regtrace baseline <subcommand>
```

| Subcommand | Description |
|------------|-------------|
| `pin <run-id>` | Pin a specific run as baseline |
| `unpin` | Revert to `last_passing` strategy |
| `show` | Display current baseline info |

### `db`

Manage the SQLite run database.

```bash
regtrace db rebuild [options]
```

| Subcommand | Description |
|------------|-------------|
| `rebuild` | Rebuild database from `.regtrace/runs/` JSON files |

| Option | Description |
|--------|-------------|
| `--config <path>` | Path to config file |

### `upgrade`

Upgrade the regtrace binary to the latest GitHub release.

```bash
regtrace upgrade [options]
```

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |
| `--prerelease` | Include prerelease (beta/rc) versions |
| `--no-verify` | Skip SHA256 checksum verification |
| `--dry-run` | Check version without downloading |

Checks GitHub Releases API for the latest release, downloads the matching
platform binary, verifies SHA256, spawns the new binary to complete the swap
in-place, and exits 0. Backs up the old binary to `.backup`; restores it if
the new binary fails `--version` verification.

### `uninstall`

Remove the regtrace binary from your system.

```bash
regtrace uninstall [options]
```

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |

On Linux and macOS the binary is removed immediately. On Windows a background
batch script deletes it after the process exits. Project files (configs, golden
sets, run history) are left in place.

## Config file reference

Minimal `regtrace.config.yaml`:

```yaml
project:
  name: my-project
  version: "1.0"
golden_sets:
  - path: golden-sets/qa.yaml
    enabled: true
metrics:
  enabled: [factuality, format, tone, regression]
  default_threshold: 0.7
  factuality:
    mode: lenient          # lenient or strict
    claim_extraction_depth: shallow  # shallow (heuristic) or deep (LLM judge)
  format:
    sub_checks:
      length: true
      json_validity: false
      required_fields: true
      forbidden_content: true
    length_tolerance: 0.3
  tone:
    sub_dimensions:
      formality: true
      sentiment: true
      assertiveness: true
  regression:
    baseline_strategy: last_passing  # last_passing or pinned
    tolerance: 0.05
    critical_threshold: 0.15
quality_gates:
  suite_score_minimum: 0.7
  max_failed_test_cases: 0
  regression_gate: true
```

### Judge configuration

```yaml
judge:
  primary:
    provider: anthropic      # anthropic, openai, groq, gemini, ollama
    model: claude-haiku-4-5-20251001
    temperature: 0.1
    max_tokens: 4096
    timeout_ms: 30000
    retry_attempts: 3

  fallback:                  # optional: used when primary exhausts retries
    provider: openai
    model: gpt-5.4-mini-2026-03-17
    temperature: 0.1
    max_tokens: 4096
    timeout_ms: 30000
    retry_attempts: 2
```

Retries use exponential backoff with jitter: `min(1000 × 2^attempt + random(500), 30000)`. On failure after all retries, `judge.fallback` is tried (if configured). No double-fallback.

### Quality gates

| Gate | Default | Description |
|------|---------|-------------|
| `suite_score_minimum` | 0.7 | Minimum aggregate score |
| `max_failed_test_cases` | 0 | Maximum allowed failed test cases |
| `max_low_confidence_ratio` | 0.1 | Max fraction of low-confidence results |
| `regression_gate` | true | Fail on critical regression |

### Storage (optional)

```yaml
storage:
  db:
    enabled: false
    path: .regtrace/regtrace.db
```

## Golden set format

```yaml
name: my-qa-set
version: "1.0.0"
description: My QA test cases
interaction_type: single_turn  # single_turn or rag
tags: [qa, general]
author: you@example.com
test_cases:
  - id: qa-001
    description: "Basic question about the capital of France"
    input: "What is the capital of France?"
    system_prompt: null
    expected_output: "The capital of France is Paris."
    actual_output: null            # fill in to evaluate
    metrics: [factuality, format]
    tags: [geography]
    weight: 1.0
    thresholds:
      factuality: 0.8             # optional per-case threshold override
```

### RAG test case

Add `context` with retrieved documents:

```yaml
  - id: rag-001
    input: "How do I authenticate?"
    expected_output: "Use Bearer token..."
    actual_output: "You need a Bearer token..."
    metrics: [factuality, format]
    context:
      documents:
        - source: "docs/api.md"
          content: "Authentication is performed via Bearer tokens..."
          retrieval_score: 0.95
```

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All quality gates passed |
| 1 | One or more quality gates failed |
| 2 | Config or schema error — evaluation did not run |

## Environment variables

| Variable | For | Required? |
|----------|-----|-----------|
| `ANTHROPIC_API_KEY` | Anthropic judge | See below |
| `OPENAI_API_KEY` | OpenAI judge | See below |
| `GROQ_API_KEY` | Groq judge | See below |
| `GEMINI_API_KEY` | Gemini judge (via `x-goog-api-key` header) | See below |

API keys are only needed when using LLM-judged metrics (factuality deep mode,
tone). Format metrics are always deterministic and require no API key.
Ollama requires no key (runs locally).

Missing keys are caught immediately (fail-fast) with a descriptive error
naming the provider and expected env var — no silent degradation. API error
responses are sanitized (truncated to 400 chars, key patterns redacted).
