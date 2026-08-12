# HGSS Stage 6 Environment Kit

## Finding

The existing Stage 4D map path can host a reusable high-level environment
vocabulary without expanding its safety limits. A compiler can compose symbolic
module recipes into bounded OBJ sources, and the existing asset compiler then
owns normalization, texture binding, display-list generation, collision, and
ROM installation.

## Evidence

- `presentation/environment/stage6i_environment_kit.json`
- `tools/pokeagent/environment_kit.py`
- `assets/manifests/stage6i_rural_kit.json`
- `assets/manifests/stage6i_coastal_kit.json`
- `fixtures/stage6i_presentation_sandbox.json`
- `qa/scenarios/stage6i_environment_sandbox.json`
- `docs/data/stage6_environment_kit.json`

The runtime scenario passed 13/13 assertions. Rural and coastal composites use
different catalog textures and inherited Nitro shapes while remaining within
2,496 and 1,068-byte display-list capacities respectively.

## Authoring contract

World authors select stable module identities and biome tags. They do not choose
Nitro shapes, material indices, texture slots, NARC members, or display-list
addresses. Canonical variation remains deterministic and bounded; arbitrary
material or transform mutation is not part of the contract.

## Confidence

High for deterministic generation, Stage 4 compilation, ROM placement,
collision, and runtime stability. Medium for final art density: the sandbox is
a representative modular proof and deliberately not a production route.

## Reproduction

```bash
make stage6i-environment-kit
python3 -m tools.pokeagent qa run \
  qa/scenarios/stage6i_environment_sandbox.json --timeout 300
```

## Remaining unknowns

- Stage 6J must define approved variant composition and canonical catalog IDs.
- Stage 6K must independently prove a real externally generated landmark.
- Final terrain-transition density and architecture dressing belong to the
  integrated Stage 6L showcase and Stage 7 production locations.
