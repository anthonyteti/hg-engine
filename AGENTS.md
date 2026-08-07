# AGENTS.md

## Mission

Build an LLM-native development toolchain for a custom Pokemon HeartGold fan game on HG-Engine.

The primary goal during early development is **automation infrastructure**, not game content volume.

## Read first

Before making changes, read:

1. `00_README.md`
2. `01_PROJECT_SPEC.md`
3. `02_RESEARCH_AND_DECISIONS.md`
4. `03_ARCHITECTURE.md`
5. `04_ROADMAP.md`

If repository reality conflicts with these documents, do not silently force the plan. Record the conflict, verify it against source/tool behavior, and update the decision documentation when appropriate.

## Core rules

### 1. Prefer headless workflows

Do not solve repetitive tasks by teaching the user to click through GUI applications.

For a GUI-only operation:

1. inspect whether the application is open source
2. identify its parser/serializer/converter logic
3. determine whether it can be invoked as a library
4. if not, extract/reimplement the smallest deterministic component required
5. use UI automation only as a temporary diagnostic fallback

### 2. Build before scaling

Never generate dozens of maps, hundreds of Pokemon entries, or large asset libraries until one representative item works end-to-end.

Use proof cases first.

### 3. Test actual outputs

When local tools are available, do not stop after editing files.

Run the relevant validator, compiler, ROM build, and smoke test.

If something cannot be tested, state exactly why.

### 4. Preserve upstream

Keep HG-Engine modifications separable from upstream where practical.

- do not rewrite upstream structure gratuitously
- prefer adapters/generators in project-owned directories
- document patches to upstream engine behavior
- keep the ability to merge future HG-Engine updates

### 5. Never commit ROM material

Do not add:

- commercial base ROMs
- generated playable ROMs
- extracted copyrighted game assets that should remain local
- user secrets/API keys

Maintain `.gitignore` accordingly.

### 6. Canonical source vs generated output

Canonical human/LLM-authored data belongs in project source files.

Generated files must be reproducible.

Do not hand-edit generated files unless debugging the generator.

### 7. Favor deterministic tooling

Use LLMs for:

- reasoning
- design
- reverse engineering
- code generation
- semantic transformation
- visual judgment

Use deterministic code for:

- binary serialization
- format conversion
- schema validation
- IDs
- packing
- mesh budgets
- file placement
- build orchestration

### 8. Keep token use controlled

Do not repeatedly read the whole repository when a smaller scope is sufficient.

- maintain concise architecture notes
- save reverse-engineering findings in `docs/knowledge/`
- prefer scripts that output compact structured summaries
- use cheap models for broad reconnaissance and bulk generation
- escalate hard tasks to expensive models only when needed

### 9. Record reverse-engineering knowledge

When you determine a file format, table meaning, address, structure, or build dependency, save it in the repository.

A future session should not have to rediscover it from scratch.

Preferred location:

```text
docs/knowledge/
```

Each note should include:

- finding
- evidence/source files
- confidence
- reproduction steps
- remaining unknowns

### 10. Avoid fake certainty

Clearly distinguish:

- confirmed by build/test
- confirmed by source inspection
- inferred
- speculative

## First assignment

Perform Stage 0 from `04_ROADMAP.md`.

Create `docs/AUTOMATION_AUDIT.md`.

Do not implement the fan game yet.

## Definition of done for a coding task

A normal task is done when:

- intended files are changed
- formatting/linting passes where available
- relevant unit/integration checks pass
- ROM/tool build passes when applicable
- behavior is tested when feasible
- generated artifacts are not accidentally committed
- documentation is updated if architecture/format knowledge changed
- final report lists changed files, commands run, tests, and unresolved risks
