# HGSS Stage 4D field-camera scale investigation

## Finding

HeartGold map headers select one of 17 fixed 36-byte camera presets. A visibly
wider/higher preset can frame taller project geometry without changing the
asset pipeline. However, the native adjacent-map connection path asserts that
the old and new headers have the same camera type, so a normal-to-wide native
edge transition is not safe without a scoped engine patch.

Stage 4D camera sub-result: **`CAMERA_FIXED_ONLY`**.

Confidence is **high for the fixed camera preset and native-connection
constraint from source plus runtime screenshots; medium for the interpretation
of every unknown preset field**.

## Preset architecture

DSPRE revision `d86737dfccaec7a603a6f27474180a49945158a6` was used as
format/source evidence only. Its HGSS camera reader identifies 17 records of
36 bytes. The supported US overlay 1 contains a pointer to the runtime table at
`0x02206478` (overlay file offset `0x20b78`; pointer sites include `0x532c` and
`0x547c`). Relevant fields include:

```text
u32 distance
s16 angleAroundX
s16 angleAroundY
s16 angleAroundZ
u16 perspective/orthographic mode
u16 FOV/scale field
fx32 near
fx32 far
fx32 x/y/z offset
```

Preset 0 is the ordinary Stage 4C camera (`distance=0x29aec1`, pitch `-8862`,
perspective mode, FOV field `0x05c1`). Preset 4 is substantially farther and
higher (`distance=0x61b89b`, pitch `-9086`, orthographic mode, scale field
`0x0281`, far plane `0x6c7000`). Stage 4D selects preset 4 through the existing
six-bit `cameraType` map-header field; it does not patch the retail table.

## Runtime behavior

`pret/pokeheartgold` revision
`008257708bd41df5b8c9037e019088ba24df0a87`, `field_warp_tasks.c`, function
`sub_02053038`, distinguishes native connection loads from other map changes.
For a connection it asserts that the stored camera type equals the destination
header's camera type. For a non-connection map load it updates the saved type.
This is direct evidence that adjacent cells with different fixed camera types
are outside the retail native-connection contract.

The Stage 4D runtime uses one fixed-camera map. Headless screenshots visibly
show more surrounding ground and frame the tall stone monument without render
corruption. Movement, collision, and another 600 frames remain stable.

## Deferred work

- Native normal-to-wide adjacency was **not attempted** because source shows a
  camera-equality assertion; pretending it worked would be fragile.
- No clean field-script camera mutation/interpolation API was established in
  this bounded investigation.
- Smooth pullback is deferred because it would require a separate, tested
  camera-state/interpolation patch rather than asset-pipeline work.
- No Gen 5 camera semantics, free camera, cinematic system, or retail preset
  rewrite is claimed.

Any future camera stage should patch or wrap the connection camera state
explicitly, expose semantic QA camera evidence, and regression-test every
ordinary field transition. It should remain separate from texture allocation.
