# HGSS Stage 3E2 map-ID width audit

## Scope

This audit covers normal HeartGold field loading, adjacency, warps,
events/scripts, map objects, and persisted location state for the supported US
revision. Optional and story-specific consumers are classified separately; a
wide field does not imply that its static data table knows project locations.

Primary source is pret/pokeheartgold revision
`8dcf4c981ac650ae1f4f80c926b588b06293ee0e`, corroborated by the local ARM9
and Stage 3E2 runtime.

## Classification

| Runtime path | Storage/API | Class | Evidence and effect |
|---|---|---|---|
| active/persisted location | `Location.mapId` is `int` | `SAFE_U16_OR_WIDER` | `LocalFieldData` embeds five complete `Location` records; reset/Continue retained 541 |
| field-system location | pointer to `Location` | `SAFE_U16_OR_WIDER` | live memory reported 540 then 541 |
| field warp task inputs | `u32 mapId` | `SAFE_U16_OR_WIDER` | normal script warp entered 540 and exited 541 to 540 |
| event warp destination | `WarpEvent.header` is `u16` | `SAFE_U16_OR_WIDER` | binary format supports 540+; Stage 3E2 used the script path for its runtime warp |
| script warp operand | read as `u16`, promoted to `u32` task API | `SAFE_U16_OR_WIDER` | generated script command reached project headers |
| matrix header grid | serialized `u16` cells | `SAFE_U16_OR_WIDER` | runtime grid `[540, 541]` drove native adjacency |
| public header accessors | input `u32 mapId` | `SAFE_U16_OR_WIDER` after patch | all 27 direct table readers route through the hybrid selector |
| retail table bound | `NELEMS(sMapHeaders) == 540` | `FIXED_BOUND` patched | original accessor entries are redirected; retail table stays unchanged |
| live map objects | internal map ID `u32` | `SAFE_U16_OR_WIDER` | normal NPC/event loading worked on both project maps |
| persisted map objects | `SavedMapObject.mapId` is `u16` | `SAFE_U16_OR_WIDER` | supports project IDs through 65535 |
| local/common scripts and messages | header returns `u16` NARC members | `SAFE_U16_OR_WIDER` | appended resources for both headers loaded and executed |
| photo records | `u16 mapId` | `SAFE_U16_OR_WIDER` | width safe; project-photo behavior was not runtime-tested |
| Pokédex launch args | `u16 mapId` | `SAFE_U16_OR_WIDER` | width safe; map visualization tables remain vanilla-oriented |
| Pokégear map location specs | `u16 mapId` | `SAFE_U16_OR_WIDER` | no truncation; project entries are not automatically added to UI lists |
| phone book entries | `u16 mapId` | `SAFE_U16_OR_WIDER` | no truncation; static phone content remains outside Stage 3E2 |
| field-move/item checks | `u32 mapId` | `SAFE_U16_OR_WIDER` | header capability checks use patched accessors |
| loaded matrix cached ID | `u8 matrix_id` | `TRUNCATING_U8` | this is a **matrix ID**, not a map-header ID; Stage 3E1/3E2 already expose the limitation |
| map preview graphic index | returns `u8` index | `FIXED_BOUND` optional | index into a vanilla preview list, not storage of the active map ID |
| Town Map/Fly destination availability | static vanilla tables | `FIXED_BOUND` optional | project IDs remain valid field maps but need future UI/content registration |
| healing/respawn and story comparisons | hardcoded vanilla mappings/comparisons | `UNKNOWN` / isolated | no central truncation found; project semantics require future content policy |
| Safari, Battle Tower, Union, and minigame special cases | hardcoded map comparisons/modes | `UNKNOWN` / isolated | not on the normal-overworld proof path and not generalized |

## Save and reload

`src/save_local_field_data.c` embeds `Location currentPosition` directly in the
normal save block; `Location.mapId` is a 32-bit `int`. The east proof script
used HeartGold's normal `save_game_normal` command. It then warped to header
540. A real emulator reset followed by Continue loaded header 541 at the saved
coordinates and selected its appended matrix/event/script/text resources.
This rules out an ordinary-save truncation at 8 bits or at the retail bound.

An emulator savestate was not used for this assertion. The generated `.dsv`
remains ignored and untracked.

## Central-bound conclusion

The critical fixed bound was the retail table lookup itself, not the main
field/save/warp data model. No `u8` map-header storage was found on the normal
field progression path. The one known `u8` truncation is the cached **matrix
member ID**, a distinct Stage 3E1 limitation.

Therefore project map IDs 540 and 541 are viable for ordinary overworld
progression. This audit does not promise that vanilla-only UIs or story tables
will display or categorize them without future canonical registrations.
