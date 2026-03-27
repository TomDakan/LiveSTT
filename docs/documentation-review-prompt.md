You are performing a professional documentation review of the LiveSTT repository.
Your goal is to identify every place where documentation has drifted from the actual
implementation — outdated architecture descriptions, missing services, wrong file paths,
superseded docs, or claims that no longer match the code.

## Ground rules

- **Never assume or infer.** For every factual claim in a doc, read the relevant source
  file(s) to verify it. Do not rely on prior knowledge or memory.
- **Read everything.** Open each .md file fully before reviewing it. Open the source
  files it references before forming a judgement.
- **Be systematic.** Work through one logical chunk at a time and complete it before
  moving on. If context is getting large, finish the current chunk, produce a partial
  report, and continue in a follow-up session.

## Methodology

**Step 1 — Inventory**
Run one of the following depending on your shell:
- Unix/Git Bash: `find . -name "*.md" -not -path "./.git/*" | sort`
- PowerShell: `Get-ChildItem -Recurse -Filter *.md | Where-Object { $_.FullName -notmatch '\.git' } | Select-Object -ExpandProperty FullName | Sort-Object`

Record the full list. This is your work queue.

**Step 2 — Inventory the implementation**
Run: `ls services/` and `ls libs/` to get the current service and library list.
Read `libs/messaging/src/messaging/streams.py` for current NATS stream definitions and subject patterns.
Read `libs/messaging/src/messaging/service.py` for the BaseService interface.
Read `docker-compose.yml` (repo root) for the current service topology. If a `docker-compose.override.yml` exists, read that too.
Read `justfile` for canonical command recipes — this is the source of truth for how commands are run. Docs that reference raw commands (e.g. bare `uv run ...`) may be outdated.
The current design version is **v8.0** (`docs/20_architecture/system_design_v8.0.md`). Use this as the anchor when checking whether a doc reflects the current or a prior design.
This gives you the ground truth to check docs against.

**Step 3 — Review each doc**
For each .md file, work through it section by section:
- Identify every factual claim (service names, file paths, stream names, API endpoints,
  architecture descriptions, command examples, env var names).
- For each claim, read the source file(s) needed to verify it.
- Flag any discrepancy, gap, or outdated content.

Work in these chunks to manage context:
- **Chunk A**: `docs/20_architecture/` — all architecture docs and ADRs
- **Chunk B**: `docs/implementation_guides/` and `docs/60_ops/`
- **Chunk C**: Root-level docs — `CLAUDE.md`, `CONTRIBUTING.md`, `ROADMAP.md`,
  `docs/api.md`, any other root .md files
- **Chunk D**: Any remaining docs not covered above (e.g. `README.md`, per-service
  `README`s inside `services/*/`, loose docs in `docs/` not under a subdirectory)

If a single document exceeds ~500 lines, read it in sections rather than all at once.
Finish reviewing each section before reading the next; note where you paused if you
need to continue in a follow-up session.

## What to look for

- Services mentioned in docs that no longer exist, or existing services not mentioned
- Stream names, subject patterns, or NATS config that don't match `streams.py`
- Hardcoded NATS subject strings in service source files that don't match the declared
  subjects in `streams.py` (grep for quoted subject literals in `services/*/`)
- File paths that don't exist
- Architecture diagrams or descriptions that reflect a prior design version
- API endpoints described that don't exist in `api-gateway/main.py`
- Env vars referenced that aren't used in the actual service code
- Docs that explicitly or implicitly contradict each other
- Commands shown in docs that differ from the canonical `just` recipes in `justfile`
- Docs marked as current that appear to have been superseded by a newer version (anchor:
  current design is v8.0)
- Missing docs — services or subsystems that have no documentation at all

## Output format

For each issue found, record:

**File**: `path/to/file.md`
**Section**: (heading or line range)
**Issue**: One-sentence description of the discrepancy
**Severity**: `high` (materially wrong, would mislead a developer) / `medium` (outdated
but not dangerously so) / `low` (minor, cosmetic, or nitpick)
**Suggested fix**: What the doc should say, or what needs to be checked/decided

Group findings by chunk. At the end, include a short summary of the most significant
gaps and any patterns you noticed (e.g. "the architecture docs consistently reflect v7.x,
not v8.0").
