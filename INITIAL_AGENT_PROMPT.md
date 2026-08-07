# Initial Agent Prompt

You are entering an existing research-driven project whose goal is to build an LLM-native Pokemon HeartGold fan-game development pipeline on top of HG-Engine.

Read these files completely before changing code:

- `00_README.md`
- `01_PROJECT_SPEC.md`
- `02_RESEARCH_AND_DECISIONS.md`
- `03_ARCHITECTURE.md`
- `04_ROADMAP.md`
- `AGENTS.md`

Your first assignment is **Stage 0: repository and automation audit**.

Do not begin designing the fan game's region, story, Pokemon roster, or final assets.

## Goals

1. Inspect the actual HG-Engine repository and verify its current build process.
2. Identify all project data/content surfaces relevant to a fully custom game:
   - maps/world geometry
   - map headers/matrices or equivalents
   - collision
   - warps
   - NPC/event placement
   - scripts
   - dialogue/text
   - trainers
   - wild encounters
   - Pokemon data
   - forms
   - battle sprites/icons
   - moves
   - abilities
   - items
   - music assignment
3. Trace which operations are already source/data driven and which normally depend on GUI tools.
4. Inspect the source of Pokemon DS Map Studio and other relevant open tooling rather than treating their GUIs as black boxes.
5. Determine the shortest credible route to create and insert a completely new small HeartGold map from a script or structured text file.
6. Determine an emulator automation strategy suitable for build verification, scripted input, screenshots, and smoke tests.
7. Do not rely on assumptions from these planning documents where source code or an actual test can answer the question.

## Required output

Create:

`docs/AUTOMATION_AUDIT.md`

For every major operation, classify it as one of:

- `HEADLESS_NOW`
- `HEADLESS_WITH_WRAPPER`
- `REQUIRES_FORMAT_IMPLEMENTATION`
- `GUI_ONLY_TEMPORARILY`
- `UNKNOWN`

For each classification provide:

- relevant repository/tool files
- current workflow
- proposed automated workflow
- confidence level
- smallest proof-of-concept test
- risks/unknowns

Also include:

### Recommended Stage 1 architecture

Give the exact files/modules you propose creating first. Prefer a minimal implementation over a speculative framework.

### HeartGold viability verdict

Choose one:

- `PROCEED_HEARTGOLD`
- `PROCEED_WITH_SPECIFIC_RISK`
- `PIVOT_TO_PLATINUM`

Explain the decision using evidence from the audit.

## Operating constraints

- Do not distribute, upload, or commit a commercial ROM.
- Assume the user will supply the required base ROM locally when needed.
- Do not commit generated playable ROMs.
- Prefer scripts, parsers, libraries, and CLIs over repetitive GUI automation.
- UI automation is acceptable only as a temporary investigative tool.
- Do not make massive generated changes during the audit.
- Run safe local commands/tests whenever possible.
- Preserve findings in the repository so future agent sessions do not repeat the research.
- If an external project has changed since the planning snapshot, use the current source as truth and document the difference.

At the end of the session, report:

1. files created/changed
2. commands run
3. builds/tests performed
4. confirmed findings
5. inferred findings
6. blocking unknowns
7. recommended next task
