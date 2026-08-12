#include "config.h"

#ifdef STAGE5F_DEX_PROOF

#include "constants/pokemon.h"
#include "constants/species.h"
#include "pokemon.h"
#include "save.h"
#include "script.h"
#include "stage5f_runtime.h"

#define STAGE5F_MAGIC 0x35464458u
#define STAGE5F_GOT_STARTER_FLAG 106
#define STAGE5F_GOT_POKEDEX_FLAG 107
#define STAGE5F_GOT_BAG_FLAG 283
#define STAGE5F_GOT_TRAINER_CARD_FLAG 284
#define STAGE5F_GOT_SAVE_BUTTON_FLAG 285
#define STAGE5F_GOT_OPTIONS_BUTTON_FLAG 286
#define STAGE5F_DEX_CAUGHT_OFFSET 0x4
#define STAGE5F_DEX_SEEN_OFFSET 0x400

static const u16 sStage5FDexSpecies[STAGE5F_DEX_REPRESENTATIVE_COUNT] = {
    SPECIES_VICTINI,
    SPECIES_CHESPIN,
    SPECIES_ROWLET,
    SPECIES_GROOKEY,
    SPECIES_SPRIGATITO,
};

volatile struct Stage5FRuntimeState gStage5FRuntimeState;

static u32 Stage5F_DexBit(u8 *dex, u32 species, u32 offset) {
    u32 index = species - 1;
    return (dex[offset + index / 8] >> (index % 8)) & 1;
}

static void Stage5F_Initialize(void) {
    struct PartyPokemon mon;
    struct Party *party = SaveData_GetPlayerPartyPtr(gFieldSysPtr->savedata);
    void *dex = SaveData_GetDexPtr(gFieldSysPtr->savedata);

    PokeParty_Init(party, 6);
    Pokedex_SetNatDexFlag(dex);
    for (u32 index = 0; index < STAGE5F_DEX_REPRESENTATIVE_COUNT; index++) {
        PokeParaSet(&mon, sStage5FDexSpecies[index], 20, 31, TRUE, 0, TRUE, 0x050F0001 + index);
        InitBoxMonMoveset(&mon.box);
        RecalcPartyPokemonStats(&mon);
        SetPokemonSee(dex, &mon);
        SetPokemonGet(dex, &mon);
        if (index == 0)
            PokeParty_Add(party, &mon);
    }
#ifdef STAGE5FS_SCOPE_PROOF
    PokeParaSet(&mon, SPECIES_PECHARUNT, 20, 31, TRUE, 0, TRUE, 0x050F1025);
    InitBoxMonMoveset(&mon.box);
    RecalcPartyPokemonStats(&mon);
    SetPokemonSee(dex, &mon);
    SetPokemonGet(dex, &mon);
#endif
    SetScriptFlag(STAGE5F_GOT_STARTER_FLAG);
    SetScriptFlag(STAGE5F_GOT_POKEDEX_FLAG);
    SetScriptFlag(STAGE5F_GOT_BAG_FLAG);
    SetScriptFlag(STAGE5F_GOT_TRAINER_CARD_FLAG);
    SetScriptFlag(STAGE5F_GOT_SAVE_BUTTON_FLAG);
    SetScriptFlag(STAGE5F_GOT_OPTIONS_BUTTON_FLAG);
    gStage5FRuntimeState.initialized = 1;
}

void Stage5F_RuntimeTick(void) {
    u8 *dex;
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL || gFieldSysPtr->location == NULL)
        return;
    if (!gStage5FRuntimeState.initialized)
        Stage5F_Initialize();
    dex = SaveData_GetDexPtr(gFieldSysPtr->savedata);
    gStage5FRuntimeState.magic = STAGE5F_MAGIC;
    gStage5FRuntimeState.representativeCount = STAGE5F_DEX_REPRESENTATIVE_COUNT;
    for (u32 index = 0; index < STAGE5F_DEX_REPRESENTATIVE_COUNT; index++) {
        gStage5FRuntimeState.species[index] = sStage5FDexSpecies[index];
        gStage5FRuntimeState.seen[index] = Stage5F_DexBit(dex, sStage5FDexSpecies[index], STAGE5F_DEX_SEEN_OFFSET);
        gStage5FRuntimeState.caught[index] = Stage5F_DexBit(dex, sStage5FDexSpecies[index], STAGE5F_DEX_CAUGHT_OFFSET);
    }
    gStage5FRuntimeState.ownedCount = Pokedex_CountDexOwned(dex);
    gStage5FRuntimeState.currentMap = gFieldSysPtr->location->mapId;
#ifdef STAGE5FS_SCOPE_PROOF
    gStage5FRuntimeState.boundarySpecies = SPECIES_PECHARUNT;
    gStage5FRuntimeState.boundarySeen = Stage5F_DexBit(dex, SPECIES_PECHARUNT, STAGE5F_DEX_SEEN_OFFSET);
    gStage5FRuntimeState.boundaryCaught = Stage5F_DexBit(dex, SPECIES_PECHARUNT, STAGE5F_DEX_CAUGHT_OFFSET);
#endif
}

#endif
