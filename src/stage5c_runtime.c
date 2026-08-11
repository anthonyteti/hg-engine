#include "config.h"

#ifdef STAGE5C_EVOLUTION_PROOF

#include "bag.h"
#include "constants/ability.h"
#include "constants/item.h"
#include "constants/pokemon.h"
#include "constants/species.h"
#include "map_events_internal.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "save.h"
#include "script.h"
#include "stage5c_runtime.h"

#define STAGE5C_MAGIC 0x35434556u
#define STAGE5C_PID 0x050C0001u
#define STAGE5C_OT_ID 0x050C0A11u
/* 0x4000..0x401F are HGSS temporary script variables and ordinary menu /
 * evolution scripts may overwrite them.  Reserve the final three persistent
 * save variables for this opt-in proof so its seed and box bookkeeping survive
 * the exact runtime path being tested. */
#define STAGE5C_PHASE_VAR 0x416D
#define STAGE5C_BOX_VAR 0x416E
#define STAGE5C_SLOT_VAR 0x416F
#define STAGE5C_INVALID_LOCATION 0xFFFF
#define STAGE5C_PC_SAVE_ARRAY 41
#define STAGE5C_HAVE_FOLLOWER_FLAG 2402
#define STAGE5C_GOT_STARTER_FLAG 106
#define STAGE5C_GOT_BAG_FLAG 283
#define STAGE5C_GOT_TRAINER_CARD_FLAG 284
#define STAGE5C_GOT_SAVE_BUTTON_FLAG 285
#define STAGE5C_GOT_OPTIONS_BUTTON_FLAG 286
#define STAGE5C_DEX_CAUGHT_OFFSET 0x4
#define STAGE5C_DEX_SEEN_OFFSET 0x400

void LONG_CALL FollowMon_ChangeMon(void *mapObjectManager, u32 mapNo);

volatile struct Stage5CRuntimeState gStage5CRuntimeState;

static struct Party *Stage5C_GetParty(void) {
    return SaveData_GetPlayerPartyPtr(gFieldSysPtr->savedata);
}

static PCStorage *Stage5C_GetStorage(void) {
    return SaveArray_Get((SaveData *)gFieldSysPtr->savedata, STAGE5C_PC_SAVE_ARRAY);
}

static struct PartyPokemon *Stage5C_GetPartyMon(void) {
    struct Party *party = Stage5C_GetParty();
    if (party->count == 0)
        return NULL;
    struct PartyPokemon *mon = Party_GetMonByIndex(party, 0);
    u32 species = GetMonData(mon, MON_DATA_SPECIES, NULL);
    if (species < SPECIES_POPPLIO || species > SPECIES_PRIMARINA)
        return NULL;
    return mon;
}

static struct BoxPokemon *Stage5C_GetBoxMon(void) {
    u16 box = GetScriptVar(STAGE5C_BOX_VAR);
    u16 slot = GetScriptVar(STAGE5C_SLOT_VAR);
    if (box >= NUM_PC_BOXES || slot >= MONS_PER_BOX)
        return NULL;
    struct BoxPokemon *mon = PCStorage_GetMonByIndexPair(Stage5C_GetStorage(), box, slot);
    u32 species = GetBoxMonData(mon, MON_DATA_SPECIES, NULL);
    if (species < SPECIES_POPPLIO || species > SPECIES_PRIMARINA)
        return NULL;
    return mon;
}

static void Stage5C_SeedPopplio(void) {
    struct PartyPokemon popplio;
    struct Party *party = Stage5C_GetParty();

    PokeParty_Init(party, 6);
    PokeParaSet(&popplio, SPECIES_POPPLIO, 16, 31, TRUE, STAGE5C_PID, TRUE, STAGE5C_OT_ID);
    RecalcPartyPokemonStats(&popplio);
    PokeParty_Add(party, &popplio);
    Bag_AddItem(Sav2_Bag_get(gFieldSysPtr->savedata), ITEM_RARE_CANDY, 24, 11);
    SetScriptFlag(STAGE5C_GOT_STARTER_FLAG);
    SetScriptFlag(STAGE5C_GOT_BAG_FLAG);
    SetScriptFlag(STAGE5C_GOT_TRAINER_CARD_FLAG);
    SetScriptFlag(STAGE5C_GOT_SAVE_BUTTON_FLAG);
    SetScriptFlag(STAGE5C_GOT_OPTIONS_BUTTON_FLAG);
    SetScriptVar(STAGE5C_PHASE_VAR, 1);
    SetScriptVar(STAGE5C_BOX_VAR, STAGE5C_INVALID_LOCATION);
    SetScriptVar(STAGE5C_SLOT_VAR, STAGE5C_INVALID_LOCATION);
}

static BOOL Stage5C_EnableFollower(void) {
    struct PartyPokemon *mon = Stage5C_GetPartyMon();
    if (mon == NULL)
        return FALSE;
    u32 species = GetMonData(mon, MON_DATA_SPECIES, NULL);
    u32 form = GetMonData(mon, MON_DATA_FORM, NULL);
    u32 gender = GetMonData(mon, MON_DATA_GENDER, NULL);
    SetScriptFlag(STAGE5C_HAVE_FOLLOWER_FLAG);
    FollowPokeFsysParamSet(gFieldSysPtr, species, form, FALSE, gender);
    return TRUE;
}

static BOOL Stage5C_AddPcCompanion(void) {
    struct PartyPokemon companion;
    struct Party *party = Stage5C_GetParty();
    if (party->count != 1 || Stage5C_GetPartyMon() == NULL)
        return FALSE;
    PokeParaSet(&companion, SPECIES_CHIKORITA, 5, 31, TRUE, 0x050C0002u, TRUE, STAGE5C_OT_ID);
    RecalcPartyPokemonStats(&companion);
    return PokeParty_Add(party, &companion);
}

static BOOL Stage5C_Deposit(void) {
    struct PartyPokemon *mon = Stage5C_GetPartyMon();
    int box;
    int slot;
    if (mon == NULL || !PCStorage_FindFirstEmptySlot(Stage5C_GetStorage(), &box, &slot))
        return FALSE;
    if (!PCStorage_PlaceMonInBoxByIndexPair(Stage5C_GetStorage(), box, slot, &mon->box))
        return FALSE;
    PokeParty_Delete(Stage5C_GetParty(), 0);
    ClearScriptFlag(STAGE5C_HAVE_FOLLOWER_FLAG);
    FollowMon_ChangeMon(gFieldSysPtr->mapObjectMan, gFieldSysPtr->location->mapId);
    SetScriptVar(STAGE5C_BOX_VAR, box);
    SetScriptVar(STAGE5C_SLOT_VAR, slot);
    SetScriptVar(STAGE5C_PHASE_VAR, 2);
    return TRUE;
}

static void Stage5C_HandleCommand(void) {
    u32 command = gStage5CRuntimeState.command;
    BOOL result = FALSE;
    if (command == STAGE5C_COMMAND_NONE)
        return;
    if (command == STAGE5C_COMMAND_ENABLE_FOLLOWER) {
        result = Stage5C_EnableFollower();
    } else if (command == STAGE5C_COMMAND_RESET_ICON_OBSERVATION) {
        gStage5CRuntimeState.iconIndexCallCount = 0;
        gStage5CRuntimeState.iconSpecies = 0;
        gStage5CRuntimeState.iconForm = 0;
        gStage5CRuntimeState.iconIndex = 0;
        gStage5CRuntimeState.iconPaletteCallCount = 0;
        gStage5CRuntimeState.iconPaletteSpecies = 0;
        gStage5CRuntimeState.iconPaletteForm = 0;
        gStage5CRuntimeState.iconPalette = 0;
        result = TRUE;
    } else if (command == STAGE5C_COMMAND_ADD_PC_COMPANION) {
        result = Stage5C_AddPcCompanion();
    } else if (command == STAGE5C_COMMAND_DEPOSIT) {
        result = Stage5C_Deposit();
    }
    gStage5CRuntimeState.commandResult = result ? command : 0x80000000u | command;
    gStage5CRuntimeState.command = STAGE5C_COMMAND_NONE;
}

static u32 Stage5C_DexBit(u8 *dex, u32 species, u32 offset) {
    u32 index = species - 1;
    return (dex[offset + index / 8] >> (index % 8)) & 1;
}

static void Stage5C_Refresh(void) {
    struct PartyPokemon *mon = Stage5C_GetPartyMon();
    struct BoxPokemon *boxMon = Stage5C_GetBoxMon();
    struct Party *party = Stage5C_GetParty();
    u8 *dex = SaveData_GetDexPtr(gFieldSysPtr->savedata);

    gStage5CRuntimeState.magic = STAGE5C_MAGIC;
    gStage5CRuntimeState.phase = GetScriptVar(STAGE5C_PHASE_VAR);
    gStage5CRuntimeState.partyCount = party->count;
    gStage5CRuntimeState.partySpecies = mon == NULL ? SPECIES_NONE : GetMonData(mon, MON_DATA_SPECIES, NULL);
    gStage5CRuntimeState.partyLevel = mon == NULL ? 0 : GetMonData(mon, MON_DATA_LEVEL, NULL);
    gStage5CRuntimeState.partyForm = mon == NULL ? 0 : GetMonData(mon, MON_DATA_FORM, NULL);
    gStage5CRuntimeState.partyPid = mon == NULL ? 0 : GetMonData(mon, MON_DATA_PERSONALITY, NULL);
    gStage5CRuntimeState.partyOtId = mon == NULL ? 0 : GetMonData(mon, MON_DATA_OTID, NULL);
    gStage5CRuntimeState.partyExperience = mon == NULL ? 0 : GetMonData(mon, MON_DATA_EXPERIENCE, NULL);
    gStage5CRuntimeState.partyHp = mon == NULL ? 0 : GetMonData(mon, MON_DATA_HP, NULL);
    gStage5CRuntimeState.partyMaxHp = mon == NULL ? 0 : GetMonData(mon, MON_DATA_MAXHP, NULL);
    gStage5CRuntimeState.partyAttack = mon == NULL ? 0 : GetMonData(mon, MON_DATA_ATTACK, NULL);
    gStage5CRuntimeState.partyDefense = mon == NULL ? 0 : GetMonData(mon, MON_DATA_DEFENSE, NULL);
    gStage5CRuntimeState.partySpeed = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPEED, NULL);
    gStage5CRuntimeState.partySpAttack = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPECIAL_ATTACK, NULL);
    gStage5CRuntimeState.partySpDefense = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPECIAL_DEFENSE, NULL);
    gStage5CRuntimeState.partyAbility = mon == NULL ? 0 : GetMonData(mon, MON_DATA_ABILITY, NULL);
    gStage5CRuntimeState.partyType1 = mon == NULL ? 0 : GetMonData(mon, MON_DATA_TYPE_1, NULL);
    gStage5CRuntimeState.partyType2 = mon == NULL ? 0 : GetMonData(mon, MON_DATA_TYPE_2, NULL);
    for (int i = 0; i < 4; i++)
        gStage5CRuntimeState.partyMoves[i] = mon == NULL ? 0 : GetMonData(mon, MON_DATA_MOVE1 + i, NULL);
    gStage5CRuntimeState.partyFriendship = mon == NULL ? 0 : GetMonData(mon, MON_DATA_FRIENDSHIP, NULL);
    gStage5CRuntimeState.partyHeldItem = mon == NULL ? 0 : GetMonData(mon, MON_DATA_HELD_ITEM, NULL);
    gStage5CRuntimeState.partyBall = mon == NULL ? 0 : GetMonData(mon, MON_DATA_POKEBALL, NULL);
    gStage5CRuntimeState.partyGender = mon == NULL ? 0 : GetMonData(mon, MON_DATA_GENDER, NULL);
    gStage5CRuntimeState.partyIvs = mon == NULL ? 0 : GetMonData(mon, MON_DATA_IVS_WORD, NULL);
    gStage5CRuntimeState.rareCandyCount = Bag_GetQuantity(Sav2_Bag_get(gFieldSysPtr->savedata), ITEM_RARE_CANDY, 11);
    /* The packed field-follower state is not a canonical species reader.
     * Observe the active party identity behind the ordinary follower flag,
     * matching the proven Stage 5B semantic boundary. */
    gStage5CRuntimeState.followerSpecies = mon != NULL && CheckScriptFlag(STAGE5C_HAVE_FOLLOWER_FLAG)
        ? GetMonData(mon, MON_DATA_SPECIES, NULL)
        : SPECIES_NONE;
    gStage5CRuntimeState.followerForm = gFieldSysPtr->followMon.forme;
    gStage5CRuntimeState.followerSprite = mon == NULL ? 0 : FollowingPokemon_GetSpriteID(
        GetMonData(mon, MON_DATA_SPECIES, NULL), GetMonData(mon, MON_DATA_FORM, NULL), GetMonData(mon, MON_DATA_GENDER, NULL));
    gStage5CRuntimeState.followerActive = gFieldSysPtr->followMon.mapObject != NULL;
    gStage5CRuntimeState.currentMap = gFieldSysPtr->location == NULL ? 0xFFFFFFFFu : (u32)gFieldSysPtr->location->mapId;
    gStage5CRuntimeState.dexPopplioSeen = Stage5C_DexBit(dex, SPECIES_POPPLIO, STAGE5C_DEX_SEEN_OFFSET);
    gStage5CRuntimeState.dexPopplioCaught = Stage5C_DexBit(dex, SPECIES_POPPLIO, STAGE5C_DEX_CAUGHT_OFFSET);
    gStage5CRuntimeState.dexBrionneSeen = Stage5C_DexBit(dex, SPECIES_BRIONNE, STAGE5C_DEX_SEEN_OFFSET);
    gStage5CRuntimeState.dexBrionneCaught = Stage5C_DexBit(dex, SPECIES_BRIONNE, STAGE5C_DEX_CAUGHT_OFFSET);
    gStage5CRuntimeState.dexPrimarinaSeen = Stage5C_DexBit(dex, SPECIES_PRIMARINA, STAGE5C_DEX_SEEN_OFFSET);
    gStage5CRuntimeState.dexPrimarinaCaught = Stage5C_DexBit(dex, SPECIES_PRIMARINA, STAGE5C_DEX_CAUGHT_OFFSET);
    gStage5CRuntimeState.boxNumber = GetScriptVar(STAGE5C_BOX_VAR);
    gStage5CRuntimeState.boxSlot = GetScriptVar(STAGE5C_SLOT_VAR);
    gStage5CRuntimeState.boxSpecies = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_SPECIES, NULL);
    gStage5CRuntimeState.boxLevel = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_LEVEL, NULL);
    gStage5CRuntimeState.boxForm = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_FORM, NULL);
    gStage5CRuntimeState.boxPid = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_PERSONALITY, NULL);
    gStage5CRuntimeState.boxExperience = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_EXPERIENCE, NULL);
    for (int i = 0; i < 4; i++)
        gStage5CRuntimeState.boxMoves[i] = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_MOVE1 + i, NULL);
}

void Stage5C_RecordEvolutionCheck(u32 source, u32 target, u32 method, u32 context) {
    if (source < SPECIES_POPPLIO || source > SPECIES_PRIMARINA || target == SPECIES_NONE)
        return;
    gStage5CRuntimeState.evolutionCheckCount++;
    gStage5CRuntimeState.evolutionSource = source;
    gStage5CRuntimeState.evolutionTarget = target;
    gStage5CRuntimeState.evolutionMethod = method;
    gStage5CRuntimeState.evolutionContext = context;
}

void Stage5C_RecordSpeciesMutation(u32 source, u32 target) {
    if (source == target || source < SPECIES_POPPLIO || source > SPECIES_PRIMARINA)
        return;
    gStage5CRuntimeState.speciesMutationCount++;
    gStage5CRuntimeState.mutationSource = source;
    gStage5CRuntimeState.mutationTarget = target;
}

void Stage5C_RecordIconIndex(u32 species, u32 form, u32 index) {
    if (species < SPECIES_POPPLIO || species > SPECIES_PRIMARINA)
        return;
    gStage5CRuntimeState.iconIndexCallCount++;
    gStage5CRuntimeState.iconSpecies = species;
    gStage5CRuntimeState.iconForm = form;
    gStage5CRuntimeState.iconIndex = index;
}

void Stage5C_RecordIconPalette(u32 species, u32 form, u32 palette) {
    if (species < SPECIES_POPPLIO || species > SPECIES_PRIMARINA)
        return;
    gStage5CRuntimeState.iconPaletteCallCount++;
    gStage5CRuntimeState.iconPaletteSpecies = species;
    gStage5CRuntimeState.iconPaletteForm = form;
    gStage5CRuntimeState.iconPalette = palette;
}

void Stage5C_RecordLevelCheckpoint(u32 species, u32 level) {
    if (species < SPECIES_POPPLIO || species > SPECIES_PRIMARINA)
        return;
    gStage5CRuntimeState.levelCheckpointCount++;
    gStage5CRuntimeState.levelCheckpointSpecies = species;
    gStage5CRuntimeState.levelCheckpointLevel = level;
}

void Stage5C_RuntimeTick(void) {
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL)
        return;
    /* New-game initialization clears save variables after the first field
     * callbacks.  Seed only after the controlled project header is active so
     * the proof individual and Bag grant are created exactly once. */
    if (GetScriptVar(STAGE5C_PHASE_VAR) == 0 && gFieldSysPtr->location != NULL &&
        gFieldSysPtr->location->mapId == 540)
        Stage5C_SeedPopplio();
    Stage5C_HandleCommand();
    Stage5C_Refresh();
}

#endif
