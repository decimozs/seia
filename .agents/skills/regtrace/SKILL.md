---
name: regtrace
description: >
  LLM evaluation CLI for measuring output quality across Factuality, Format, Tone, and Regression.
  Use this skill whenever a user mentions regtrace, golden sets, LLM evaluation, model regression,
  quality gates, CI/CD evaluation pipelines, or asks how to test/compare LLM outputs. Also trigger
  for tasks like: setting up a new regtrace project, writing test cases for a prompt, debugging a
  failing evaluation, pinning a regression baseline, switching judge providers, integrating regtrace
  into CI, running evaluations, understanding scores, formatting output, generating test outputs,
  troubleshooting API keys, configuring metrics, or managing run history. When in doubt, use this
  skill — it covers the full regtrace workflow from install to production.
---

# Regtrace

Regtrace evaluates LLM outputs across four dimensions — **Factuality**, **Format**, **Tone**, and **Regression** — using golden sets (YAML test cases) and a configurable LLM judge. Think of it as a linter for LLM outputs: it tells you which dimension failed, why, how confident the evaluator is, and how the score compares to the last passing baseline.

---

## Installation

Download the binary from GitHub Releases:

```bash
curl -L -o /usr/local/bin/regtrace https://github.com/decimozs/regtrace/releases/latest/download/regtrace
chmod +x /usr/local/bin/regtrace
regtrace --version
```

macOS Gatekeeper blocks unsigned binaries:
```bash
xattr -d com.apple.quarantine ./regtrace
```

---

## Quick start (5 minutes)

```bash
regtrace init                    # scaffold: config, golden set, .env.example, .gitignore
export ANTHROPIC_API_KEY=sk-ant-...   # or set in .env
regtrace run --dry-run           # validate setup without spending tokens
regtrace run --generate          # auto-fill null outputs, then evaluate
regtrace run                     # evaluate against golden set
regtrace list                    # show recent runs
regtrace history --run-id <id>   # inspect a run
```

---

## Project setup

### Initialize a project

```bash
regtrace init                    # scaffold in current directory
regtrace init --dir ./project    # target directory
regtrace init --force            # overwrite existing files
```

Creates: `regtrace.config.yaml`, `golden-sets/qa.yaml`, `.env.example`, `.gitignore`, `.regtrace/runs/`.

### API keys

Set in `.env` (loaded via dotenv from CWD) or as environment variables:

| Provider | Env var | Notes |
|----------|---------|-------|
| Anthropic | `ANTHROPIC_API_KEY` | Default provider |
| OpenAI | `OPENAI_API_KEY` | |
| Groq | `GROQ_API_KEY` | |
| Gemini | `GEMINI_API_KEY` | Uses `x-goog-api-key` header |
| Ollama | *(none)* | Runs locally at `localhost:11434`, configurable via `local_endpoint` |

Missing keys fail immediately with a descriptive error naming the provider and expected env var. Error responses are sanitized: body truncated to 400 chars, API key patterns redacted (`sk-...`, `gsk_...`, `AIza...`).

Format metrics are deterministic and need no API key. Only factuality (deep mode) and tone require keys.

---

## Config file

Full `regtrace.config.yaml` schema:

```yaml
project:
  name: my-project
  version: "1.0"

golden_sets:
  - path: golden-sets/qa.yaml
    enabled: true
    weight: 1                 # contribution weight in multi-set runs
    store_in_db: true          # persist runs to SQLite database

metrics:
  enabled: [factuality, format, tone, regression]
  default_threshold: 0.7
  factuality:
    mode: strict               # strict (default) or lenient
    claim_extraction_depth: shallow  # shallow (heuristic, fast) or deep (LLM judge)
    rag_faithfulness_only: false     # only check against context docs
  format:
    sub_checks:
      length: true
      json_validity: true
      json_schema: true
      markdown_structure: true
      required_fields: true
      forbidden_content: true
      regex_match: true         # patterns >500 chars rejected (ReDoS protection)
    length_tolerance: 0.3
    strict_json: false          # reject trailing commas, comments
  tone:
    tone_profile: null          # e.g. "confident, approachable, professional"
    sub_dimensions:
      formality: true
      sentiment: true
      assertiveness: true
      persona_consistency: true
      verbosity: true
    sub_dimension_weights: null # e.g. { formality: 2.0, verbosity: 0.5 }
  regression:
    baseline_strategy: last_passing  # last_passing or pinned
    tolerance: 0.05              # warning threshold
    critical_threshold: 0.15     # gate-failing threshold
    exclude_new_test_cases: true # exclude cases not in baseline

judge:
  primary:
    provider: anthropic          # anthropic | openai | gemini | groq | ollama
    model: claude-haiku-4-5-20251001
    temperature: 0.1
    max_tokens: 4096
    timeout_ms: 30000
    retry_attempts: 3
  fallback:                      # optional
    provider: openai
    model: gpt-4.1-mini
    temperature: 0.1
    max_tokens: 4096
    timeout_ms: 30000
    retry_attempts: 2

generator:                       # optional — falls back to judge.primary when absent
  provider: anthropic
  model: claude-haiku-4-5-20251001
  temperature: 0.4               # higher for creative, lower for factual
  max_tokens: 4096
  timeout_ms: 60000
  retry_attempts: 3

run:
  concurrency: 1                 # parallel test cases per batch (1-20)

quality_gates:
  suite_score_minimum: 0.7
  metric_score_minimums:         # per-metric thresholds (optional)
    factuality: 0.8
    format: 0.6
  max_failed_test_cases: 0
  max_low_confidence_ratio: 0.1
  regression_gate: true

output:
  run_history_limit: 50
  default_format: terminal       # terminal | json | markdown
  color: auto                    # auto | always | never
  ci_mode_auto_detect: true
  report_path: null              # overridden by --output
```

**Required blocks** (Zod enforces these — `regtrace init` creates them): `metrics.tone`, `metrics.factuality`, `metrics.format`, `metrics.regression`.

**Ollama** accepts `local_endpoint` (default `http://localhost:11434`):
```yaml
judge:
  primary:
    provider: ollama
    model: llama3
    local_endpoint: http://192.168.1.100:11434
```

**Retry behavior:** exponential backoff with jitter — `min(1000 × 2^attempt + random(500), 30000)`. If primary exhausts retries, fallback is tried. No double-fallback. If both fail, metric falls back to heuristic scoring (factuality: n-gram overlap; tone: keyword matching). Heuristic scores flagged with low confidence.

**Regression two-tier:** score drop >= tolerance → `warning` (suite still passes). Drop >= critical_threshold → `critical` (gate fails). No baseline → `new` status.

---

## Golden set format

```yaml
name: my-qa-set
version: "1.0.0"                 # bump on changes (patch/minor/major)
description: My QA test cases
interaction_type: single_turn    # single_turn or rag
tags: [qa, general]
author: you@example.com
created_at: "2025-01-01"         # required ISO 8601
updated_at: "2025-06-01"        # required ISO 8601
test_cases:
  - id: qa-001
    description: "Capital of France"
    input: "What is the capital of France?"
    system_prompt: null
    expected_output: "The capital of France is Paris."
    actual_output: null           # fill in or use --generate
    metrics: [factuality, format]
    tags: [geography]
    weight: 1.0
    thresholds:
      factuality: 0.8            # per-case override
    context: null                 # required for rag interaction_type
```

Versioning: patch = typo/clarifying fixes. Minor = new cases or meaningful changes. Major = restructuring or changing interaction_type.

### RAG test case

```yaml
  - id: rag-001
    input: "How do I authenticate?"
    interaction_type: rag
    expected_output: "Use Bearer token..."
    actual_output: "You need a Bearer token..."
    metrics: [factuality, format]
    context:
      documents:
        - source: "docs/api.md"
          content: "Authentication is performed via Bearer tokens..."
          retrieval_score: 0.95
```

With `rag_faithfulness_only: true`, factuality only checks claims against context documents.

---

## CLI commands

### `regtrace run` — evaluate golden sets

```bash
regtrace run                              # default terminal output
regtrace run --generate                   # fill null actual_output via LLM
regtrace run --set golden-sets/qa.yaml   # single golden set
regtrace run --format json                # JSON to stdout (pipeable)
regtrace run --format json -o out.json   # JSON to file
regtrace run --format markdown -o out.md  # Markdown report
regtrace run --ci                         # CI mode: no color, exit 1 on gate failure
regtrace run --no-ci                      # force color in CI environments
regtrace run --ci --bail                  # stop at first failing suite
regtrace run --dry-run                    # validate config + golden sets, no LLM calls
regtrace run --verbose                    # show all test cases including passing
regtrace run --quiet                      # suppress progress, show only errors
regtrace run --trigger ci                 # set trigger metadata (default: cli)
regtrace run --config path/to/config.yaml # custom config path
```

**Output streams:** human-readable → stderr, JSON → stdout. Pipe JSON while seeing progress:
```bash
regtrace run --format json 2>/dev/null | jq '.suite.suite_score'
```

### `regtrace list` — show recent runs

```bash
regtrace list                            # terminal table
regtrace list --format json              # machine-readable JSON
regtrace list --limit 20                 # show last 20 runs
regtrace list --suite my-qa-set          # filter by suite name
regtrace list --status passed            # filter: passed | failed
```

### `regtrace history` — inspect runs

```bash
regtrace history                         # latest run details
regtrace history --run-id run_abc        # specific run
regtrace history --run-id <a> --diff <b> # diff two runs
regtrace history --diff <a>              # diff against predecessor
```

### `regtrace baseline` — regression baselines

```bash
regtrace baseline show                   # current baseline info
regtrace baseline pin <run-id>          # pin to specific run
regtrace baseline unpin                  # revert to last_passing strategy
```

### `regtrace watch` — file-watch mode

```bash
regtrace watch                   # re-run on golden set changes (500ms debounce)
regtrace watch --config path     # custom config
```

### `regtrace db rebuild` — rebuild SQLite database

```bash
regtrace db rebuild              # reconstruct DB from .regtrace/runs/ JSON files
```

JSON files are the source of truth. The database is a derived cache. Corrupt JSON files are skipped.

---

## Quality gates

All four gates must pass for the suite to succeed (AND logic):

| Gate | Default | Description |
|------|---------|-------------|
| `suite_score_minimum` | 0.7 | Aggregate suite score (weighted) |
| `metric_score_minimums` | — | Per-metric minimum floors (optional) |
| `max_failed_test_cases` | 0 | Max allowed individual failures |
| `max_low_confidence_ratio` | 0.1 | Max fraction with confidence < 0.6 |
| `regression_gate` | true | Fail on critical regression |

**Without `--ci`**, gate failures display but don't affect exit code. **With `--ci`**, exit code 1 on failure.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | All quality gates passed |
| 1 | One or more quality gates failed |
| 2 | Config or schema error — evaluation did not run |

---

## Run record

Each run creates `.regtrace/runs/run_YYYYMMDD_<suffix>.json`.

Key fields: `run_id`, `timestamp`, `trigger` (cli/ci/watch), `duration_ms`, `judge_provider`, `judge_model`, `suite_score`, `metric_summary`, `test_case_results`, `regression` (baseline_run_id, suite_delta, regression_status, version_change_detected).

Each `TestCaseResult` has: `overall_passed`, `severity` (pass/warn/fail), `metric_results`.

Each `MetricResult` has: `score`, `confidence`, `passed`, `threshold`, `explanation`, `evaluation_type` (deterministic/llm_judged), `token_cost`.

---

## Weight cascade

Config `default_weight` → all metrics. Golden set `weight` → multi-set contribution. Test case `weight` → contribution within a set. All default to 1.

```
Sub-Check Scores → (weighted avg) → Metric Score → (metric weight) → Test Case Score → (case weight) → Suite Score
```

---

## CI/CD patterns

### Minimal GitHub Actions

```yaml
- name: Run LLM quality gates
  run: regtrace run --ci
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### PR comment with Markdown report

```yaml
- run: regtrace run --ci --format markdown --output report.md
- uses: juliangruber/read-file-action@v1
  id: report
  with:
    path: report.md
- uses: actions/github-script@v7
  with:
    script: |
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner, repo: context.repo.repo,
        body: `## Regtrace Evaluation\n\n${{ steps.report.outputs.content }}`
      });
```
Requires `permissions: pull-requests: write`.

### Nightly generate + evaluate

```yaml
on:
  schedule:
    - cron: "0 6 * * *"
steps:
  - run: regtrace run --generate --ci --format json --output report.json
  - uses: actions/upload-artifact@v4
    with:
      name: regtrace-report
      path: report.json
```

### Cache regression history in CI

```yaml
- uses: actions/cache@v4
  with:
    path: .regtrace
    key: regtrace-${{ hashFiles('golden-sets/**', 'regtrace.config.yaml') }}
```

### Baseline pinning workflow

```yaml
- run: regtrace baseline pin ${{ github.event.inputs.run_id }}
- uses: peter-evans/create-pull-request@v6
  with:
    commit-message: "chore: pin baseline"
    branch: baseline-pin
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `anthropic API key not configured` | Missing env var | `export ANTHROPIC_API_KEY=...` or create `.env` |
| Suite Score: 0.0% | All `actual_output: null` | `regtrace run --generate` or fill manually |
| `No regtrace.config.yaml found` | Missing config | `regtrace init` or `--config path` |
| Schema validation error | Invalid config/golden set | Check provider, interaction_type, metric names |
| `ECONNREFUSED localhost:11434` | Ollama not running | `ollama serve` or set `local_endpoint` |
| API error 408 | Provider timeout | Increase `timeout_ms` or add fallback |
| macOS: "cannot be opened" | Gatekeeper | `xattr -d com.apple.quarantine ./regtrace` |
| Low-confidence in CI | Model non-determinism | Raise `max_low_confidence_ratio` or `max_failed_test_cases` |
| Generate mode times out | Too many null outputs | Increase `generator.timeout_ms`, reduce `run.concurrency` |
| Dry-run passes, real run fails | Network/API key issue | Check connectivity and keys |
| Cache restores old baseline | Stale `.regtrace/` | Include `hashFiles` in cache key |
