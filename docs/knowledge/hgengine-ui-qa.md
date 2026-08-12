# Stage 6 UI QA contract

## Finding

UI regression is represented by a semantic-first registry rather than a set of
pixel-golden tests. Canonical source is
`presentation/ui/qa/stage6_ui_smoke.json`; compilation and graph/static checks
are in `tools/pokeagent/ui_qa.py`.

## Evidence and reproduction

```bash
make stage6h-ui-qa
```

The output `docs/data/stage6_ui_qa.json` records immutable scenario plan hashes,
screen coverage, semantic assertion vocabulary, and static checks.

## Confidence

High for registry completeness, scenario resolution, navigation reachability,
cancel behavior, native bounds, and determinism. Screenshot aesthetic review
remains AI/human visual judgment rather than a universal pixel hash.

## Remaining unknowns

Individual overlay internals remain native where Stage 6G classified partial
control. Add semantic observers only when a future UI revision needs a stable
assertion; do not expose raw addresses in author sources.
