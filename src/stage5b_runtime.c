#include "config.h"

#ifdef STAGE5B_RUNTIME_PROOF

#include "constants/ability.h"
#include "constants/file.h"
#include "constants/item.h"
#include "constants/moves.h"
#include "constants/pokemon.h"
#include "constants/species.h"
#include "bag.h"
#include "map_events_internal.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "save.h"
#include "script.h"
#include "stage5b_runtime.h"

#define STAGE5B_MAGIC 0x35425649u
#define STAGE5B_PHASE_VAR 0x4001
#define STAGE5B_BOX_VAR 0x4002
#define STAGE5B_SLOT_VAR 0x4003
#define STAGE5B_PC_SAVE_ARRAY 41
#define STAGE5B_INVALID_LOCATION 0xFFFF
#define STAGE5B_HAVE_FOLLOWER_FLAG 2401
#define STAGE5BC_GOT_STARTER_FLAG 106
#define STAGE5BC_GOT_BAG_FLAG 283
#define STAGE5BC_GOT_TRAINER_CARD_FLAG 284
#define STAGE5BC_GOT_SAVE_BUTTON_FLAG 285
#define STAGE5BC_GOT_OPTIONS_BUTTON_FLAG 286
#define STAGE5BC_MAGIC 0x3542434Cu
#define STAGE5BC_DEX_CAUGHT_OFFSET 0x4
#define STAGE5BC_DEX_SEEN_OFFSET 0x400

void LONG_CALL FollowMon_ChangeMon(void *mapObjectManager, u32 mapNo);

#ifdef STAGE3E2_HEADER_TEST
u32 ExpandedMapHeader_HasWildEncounters(u32 id);
u32 ExpandedMapHeader_GetWildEncounterBank(u32 id);
#endif

volatile struct Stage5BRuntimeState gStage5BRuntimeState;

static struct Party *Stage5B_GetParty(void) {
    return SaveData_GetPlayerPartyPtr(gFieldSysPtr->savedata);
}

static PCStorage *Stage5B_GetStorage(void) {
    return SaveArray_Get((SaveData *)gFieldSysPtr->savedata, STAGE5B_PC_SAVE_ARRAY);
}

static void Stage5B_SeedVictini(void) {
    struct PartyPokemon victini;
    struct Party *party = Stage5B_GetParty();
    u16 hp = 37;

    PokeParty_Init(party, 6);
    PokeParaSet(&victini, SPECIES_VICTINI, 20, 31, TRUE, 0, TRUE, 0x050B0001);
    InitBoxMonMoveset(&victini.box);
    RecalcPartyPokemonStats(&victini);
    SetMonData(&victini, MON_DATA_HP, &hp);
    PokeParty_Add(party, &victini);
    SetScriptVar(STAGE5B_PHASE_VAR, 1);
    SetScriptVar(STAGE5B_BOX_VAR, STAGE5B_INVALID_LOCATION);
    SetScriptVar(STAGE5B_SLOT_VAR, STAGE5B_INVALID_LOCATION);
#ifdef STAGE5BC_RUNTIME_PROOF
    /* Proof-only initial inventory/state.  The subsequent encounter and catch
     * still use the ordinary field and battle paths. */
    Bag_AddItem(Sav2_Bag_get(gFieldSysPtr->savedata), ITEM_MASTER_BALL, 1, 11);
    /* The controlled new-game entry precedes the story scripts that ordinarily
     * unlock the field menu.  Enable the ordinary menu UI only in the opt-in
     * proof build so party/icon validation uses the real application. */
    SetScriptFlag(STAGE5BC_GOT_STARTER_FLAG);
    SetScriptFlag(STAGE5BC_GOT_BAG_FLAG);
    SetScriptFlag(STAGE5BC_GOT_TRAINER_CARD_FLAG);
    SetScriptFlag(STAGE5BC_GOT_SAVE_BUTTON_FLAG);
    SetScriptFlag(STAGE5BC_GOT_OPTIONS_BUTTON_FLAG);
#endif
}

static struct PartyPokemon *Stage5B_GetPartyVictini(void) {
    struct Party *party = Stage5B_GetParty();
    if (party->count < 1)
        return NULL;
    struct PartyPokemon *mon = Party_GetMonByIndex(party, 0);
    return GetMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_VICTINI ? mon : NULL;
}

static struct BoxPokemon *Stage5B_GetBoxVictini(void) {
    u16 box = GetScriptVar(STAGE5B_BOX_VAR);
    u16 slot = GetScriptVar(STAGE5B_SLOT_VAR);
    if (box >= NUM_PC_BOXES || slot >= MONS_PER_BOX)
        return NULL;
    struct BoxPokemon *mon = PCStorage_GetMonByIndexPair(Stage5B_GetStorage(), box, slot);
    return GetBoxMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_VICTINI ? mon : NULL;
}

static BOOL Stage5B_Deposit(void) {
    struct PartyPokemon *mon = Stage5B_GetPartyVictini();
    int box;
    int slot;
    if (mon == NULL || !PCStorage_FindFirstEmptySlot(Stage5B_GetStorage(), &box, &slot))
        return FALSE;
    if (!PCStorage_PlaceMonInBoxByIndexPair(Stage5B_GetStorage(), box, slot, &mon->box))
        return FALSE;
    PokeParty_Delete(Stage5B_GetParty(), 0);
    ClearScriptFlag(STAGE5B_HAVE_FOLLOWER_FLAG);
#ifdef STAGE5BC_RUNTIME_PROOF
    /* The real storage overlay refreshes the field follower after a deposit.
     * The API-level proof helper must preserve that same lifecycle invariant. */
    FollowMon_ChangeMon(gFieldSysPtr->mapObjectMan, gFieldSysPtr->location->mapId);
#endif
    SetScriptVar(STAGE5B_BOX_VAR, box);
    SetScriptVar(STAGE5B_SLOT_VAR, slot);
    SetScriptVar(STAGE5B_PHASE_VAR, 2);
    return TRUE;
}

static BOOL Stage5B_Withdraw(void) {
    struct BoxPokemon *boxMon = Stage5B_GetBoxVictini();
    struct PartyPokemon mon;
    u16 box = GetScriptVar(STAGE5B_BOX_VAR);
    u16 slot = GetScriptVar(STAGE5B_SLOT_VAR);
    if (boxMon == NULL)
        return FALSE;
    CopyBoxPokemonToPokemon(boxMon, &mon);
    if (!PokeParty_Add(Stage5B_GetParty(), &mon))
        return FALSE;
    PCStorage_DeleteBoxMonByIndexPair(Stage5B_GetStorage(), box, slot);
    SetScriptVar(STAGE5B_PHASE_VAR, 3);
    return TRUE;
}

static BOOL Stage5B_EnableFollower(void) {
    if (Stage5B_GetPartyVictini() == NULL)
        return FALSE;
    SetScriptFlag(STAGE5B_HAVE_FOLLOWER_FLAG);
    FollowPokeFsysParamSet(gFieldSysPtr, SPECIES_VICTINI, 0, FALSE, 2);
    return TRUE;
}

#ifdef STAGE5BC_RUNTIME_PROOF
static BOOL Stage5BC_AddPcCompanion(void) {
    struct PartyPokemon companion;
    struct Party *party = Stage5B_GetParty();

    if (party->count != 1 || Stage5B_GetPartyVictini() == NULL)
        return FALSE;
    PokeParaSet(&companion, SPECIES_CHIKORITA, 5, 31, TRUE, 0, TRUE, 0x050B0002);
    InitBoxMonMoveset(&companion.box);
    RecalcPartyPokemonStats(&companion);
    return PokeParty_Add(party, &companion);
}
#endif

static void Stage5B_HandleCommand(void) {
    u32 command = gStage5BRuntimeState.command;
    struct PartyPokemon *mon = Stage5B_GetPartyVictini();
    BOOL result = FALSE;
    if (command == STAGE5B_COMMAND_NONE)
        return;
    if (command == STAGE5B_COMMAND_MARK_SEEN && mon != NULL) {
        SetPokemonSee(SaveData_GetDexPtr(gFieldSysPtr->savedata), mon);
        gStage5BRuntimeState.seenCommands++;
        result = TRUE;
    } else if (command == STAGE5B_COMMAND_MARK_CAUGHT && mon != NULL) {
        SetPokemonGet(SaveData_GetDexPtr(gFieldSysPtr->savedata), mon);
        gStage5BRuntimeState.caughtCommands++;
        result = TRUE;
    } else if (command == STAGE5B_COMMAND_DEPOSIT) {
        result = Stage5B_Deposit();
        if (result)
            gStage5BRuntimeState.depositCommands++;
    } else if (command == STAGE5B_COMMAND_WITHDRAW) {
        result = Stage5B_Withdraw();
        if (result)
            gStage5BRuntimeState.withdrawCommands++;
    } else if (command == STAGE5B_COMMAND_ENABLE_FOLLOWER) {
        result = Stage5B_EnableFollower();
        if (result)
            gStage5BRuntimeState.enabledFollowerCommands++;
#ifdef STAGE5BC_RUNTIME_PROOF
    } else if (command == STAGE5B_COMMAND_RESET_ICON_OBSERVATION) {
        gStage5BRuntimeState.iconIndexCallCount = 0;
        gStage5BRuntimeState.iconSpecies = 0;
        gStage5BRuntimeState.iconForm = 0;
        gStage5BRuntimeState.iconIndex = 0;
        gStage5BRuntimeState.iconPaletteCallCount = 0;
        gStage5BRuntimeState.iconPaletteSpecies = 0;
        gStage5BRuntimeState.iconPaletteForm = 0;
        gStage5BRuntimeState.iconPalette = 0;
        result = TRUE;
    } else if (command == STAGE5B_COMMAND_ADD_PC_COMPANION) {
        /* Retail PC storage never permits depositing the final party member.
         * Keep that native invariant in the isolated box-UI proof. */
        result = Stage5BC_AddPcCompanion();
#endif
    }
    gStage5BRuntimeState.commandResult = result ? command : 0x80000000u | command;
    gStage5BRuntimeState.command = STAGE5B_COMMAND_NONE;
}

static void Stage5B_Refresh(void) {
    struct PartyPokemon *partyMon = Stage5B_GetPartyVictini();
    struct BoxPokemon *boxMon = Stage5B_GetBoxVictini();
    gStage5BRuntimeState.magic = STAGE5B_MAGIC;
    gStage5BRuntimeState.phase = GetScriptVar(STAGE5B_PHASE_VAR);
    gStage5BRuntimeState.partySpecies = partyMon == NULL ? SPECIES_NONE : GetMonData(partyMon, MON_DATA_SPECIES, NULL);
    gStage5BRuntimeState.partyLevel = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_LEVEL, NULL);
    gStage5BRuntimeState.partyForm = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_FORM, NULL);
    for (int i = 0; i < 4; i++)
        gStage5BRuntimeState.partyMoves[i] = partyMon == NULL ? MOVE_NONE : GetMonData(partyMon, MON_DATA_MOVE1 + i, NULL);
    gStage5BRuntimeState.partyHp = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_HP, NULL);
    gStage5BRuntimeState.partyMaxHp = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_MAXHP, NULL);
    gStage5BRuntimeState.partyAttack = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_ATTACK, NULL);
    gStage5BRuntimeState.partyDefense = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_DEFENSE, NULL);
    gStage5BRuntimeState.partySpeed = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_SPEED, NULL);
    gStage5BRuntimeState.partySpAttack = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_SPECIAL_ATTACK, NULL);
    gStage5BRuntimeState.partySpDefense = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_SPECIAL_DEFENSE, NULL);
    gStage5BRuntimeState.partyAbility = partyMon == NULL ? 0 : GetMonData(partyMon, MON_DATA_ABILITY, NULL);
    gStage5BRuntimeState.type1 = PokeFormNoPersonalParaGet(SPECIES_VICTINI, 0, PERSONAL_TYPE_1);
    gStage5BRuntimeState.type2 = PokeFormNoPersonalParaGet(SPECIES_VICTINI, 0, PERSONAL_TYPE_2);
    gStage5BRuntimeState.boxSpecies = boxMon == NULL ? SPECIES_NONE : GetBoxMonData(boxMon, MON_DATA_SPECIES, NULL);
    gStage5BRuntimeState.boxLevel = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_LEVEL, NULL);
    gStage5BRuntimeState.boxForm = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_FORM, NULL);
    for (int i = 0; i < 4; i++)
        gStage5BRuntimeState.boxMoves[i] = boxMon == NULL ? MOVE_NONE : GetBoxMonData(boxMon, MON_DATA_MOVE1 + i, NULL);
    gStage5BRuntimeState.boxNumber = GetScriptVar(STAGE5B_BOX_VAR);
    gStage5BRuntimeState.boxSlot = GetScriptVar(STAGE5B_SLOT_VAR);
    gStage5BRuntimeState.dexOwned = Pokedex_CountDexOwned(SaveData_GetDexPtr(gFieldSysPtr->savedata));
    gStage5BRuntimeState.followerSpecies = partyMon != NULL && CheckScriptFlag(STAGE5B_HAVE_FOLLOWER_FLAG)
        ? GetMonData(partyMon, MON_DATA_SPECIES, NULL)
        : SPECIES_NONE;
    gStage5BRuntimeState.followerForm = gFieldSysPtr->followMon.forme;
    gStage5BRuntimeState.followerSprite = FollowingPokemon_GetSpriteID(SPECIES_VICTINI, 0, 2);
#ifdef STAGE5BC_RUNTIME_PROOF
    struct Party *party = Stage5B_GetParty();
    u8 *dex = SaveData_GetDexPtr(gFieldSysPtr->savedata);
    u32 dexIndex = SPECIES_VICTINI - 1;
    gStage5BRuntimeState.stage5bcMagic = STAGE5BC_MAGIC;
    gStage5BRuntimeState.currentMap = gFieldSysPtr->location == NULL ? 0xFFFFFFFFu : (u32)gFieldSysPtr->location->mapId;
    /* The engine's byte named active is cleared during ordinary lifecycle
     * transitions even while the follower object remains instantiated.  The
     * map-object pointer is the stable semantic proof that the field follower
     * is actually present. */
    gStage5BRuntimeState.followerActive = gFieldSysPtr->followMon.mapObject != NULL;
    gStage5BRuntimeState.partyCount = party->count;
    gStage5BRuntimeState.dexSeen = (dex[STAGE5BC_DEX_SEEN_OFFSET + dexIndex / 8] >> (dexIndex % 8)) & 1;
    gStage5BRuntimeState.dexCaught = (dex[STAGE5BC_DEX_CAUGHT_OFFSET + dexIndex / 8] >> (dexIndex % 8)) & 1;
#ifdef STAGE3E2_HEADER_TEST
    if (gFieldSysPtr->location != NULL) {
        u32 mapId = gFieldSysPtr->location->mapId;
        gStage5BRuntimeState.mapHasWildEncounters = ExpandedMapHeader_HasWildEncounters(mapId);
        gStage5BRuntimeState.mapWildEncounterBank = ExpandedMapHeader_GetWildEncounterBank(mapId);
        gStage5BRuntimeState.loadedWalkEncounterRate = gFieldSysPtr->map_events->wildEncounters.rateWalk;
        gStage5BRuntimeState.currentMetatileBehavior = GetMetatileBehaviorAt(
            gFieldSysPtr, gFieldSysPtr->location->x, gFieldSysPtr->location->z);
        /* The proof controls only the ordinary encounter-rate roll.  Very tall
         * grass plus the engine's existing four-step rate boost makes both
         * native rolls 100%; the native encounter constructor remains
         * untouched. */
        if (mapId == 541 && gStage5BRuntimeState.currentMetatileBehavior == 3)
            gFieldSysPtr->reverseTurnFrameSteps = 4;
        gStage5BRuntimeState.loadedFirstLandLevel = gFieldSysPtr->map_events->wildEncounters.landSlots.levels[0];
        gStage5BRuntimeState.loadedFirstLandSpecies = gFieldSysPtr->map_events->wildEncounters.landSlots.speciesMorning[0];
        gStage5BRuntimeState.encounterInhibitSteps = gFieldSysPtr->encounterInhibitSteps;
        gStage5BRuntimeState.reverseTurnFrameSteps = gFieldSysPtr->reverseTurnFrameSteps;
    }
#endif
    if (party->count > 1) {
        struct PartyPokemon *captured = Party_GetMonByIndex(party, party->count - 1);
        gStage5BRuntimeState.capturedSpecies = GetMonData(captured, MON_DATA_SPECIES, NULL);
        gStage5BRuntimeState.capturedLevel = GetMonData(captured, MON_DATA_LEVEL, NULL);
        gStage5BRuntimeState.capturedForm = GetMonData(captured, MON_DATA_FORM, NULL);
        for (int i = 0; i < 4; i++)
            gStage5BRuntimeState.capturedMoves[i] = GetMonData(captured, MON_DATA_MOVE1 + i, NULL);
        gStage5BRuntimeState.capturedAbility = GetMonData(captured, MON_DATA_ABILITY, NULL);
        gStage5BRuntimeState.capturedPid = GetMonData(captured, MON_DATA_PERSONALITY, NULL);
    }
#endif
}

#ifdef STAGE5BC_RUNTIME_PROOF
void Stage5BC_RecordTrainer(u32 trainerId, u32 species, u32 level, u32 form, const u16 moves[4]) {
    gStage5BRuntimeState.trainerLoadCount = 1;
    gStage5BRuntimeState.trainerId = trainerId;
    gStage5BRuntimeState.trainerSpecies = species;
    gStage5BRuntimeState.trainerLevel = level;
    gStage5BRuntimeState.trainerForm = form;
    for (int i = 0; i < 4; i++)
        gStage5BRuntimeState.trainerMoves[i] = moves[i];
}

void Stage5BC_RecordWild(u32 species, u32 level, u32 form, const u16 moves[4]) {
    gStage5BRuntimeState.wildLoadCount = 1;
    gStage5BRuntimeState.wildSpecies = species;
    gStage5BRuntimeState.wildLevel = level;
    gStage5BRuntimeState.wildForm = form;
    for (int i = 0; i < 4; i++)
        gStage5BRuntimeState.wildMoves[i] = moves[i];
}

void Stage5BC_RecordCryRequest(u32 species, u32 form, u32 identity) {
    u8 *dex;
    u32 dexIndex;

    if (species != SPECIES_VICTINI)
        return;
    gStage5BRuntimeState.cryRequestCount = 1;
    gStage5BRuntimeState.cryRequestedSpecies = species;
    gStage5BRuntimeState.cryRequestedForm = form;
    gStage5BRuntimeState.cryIdentity = identity;
    dex = SaveData_GetDexPtr(gFieldSysPtr->savedata);
    dexIndex = SPECIES_VICTINI - 1;
    gStage5BRuntimeState.encounterSeenAtCry =
        (dex[STAGE5BC_DEX_SEEN_OFFSET + dexIndex / 8] >> (dexIndex % 8)) & 1;
    gStage5BRuntimeState.encounterCaughtAtCry =
        (dex[STAGE5BC_DEX_CAUGHT_OFFSET + dexIndex / 8] >> (dexIndex % 8)) & 1;
}

void Stage5BC_RecordCryBank(u32 bank) {
    if (bank != CRY_PSEUDOBANK_START)
        return;
    gStage5BRuntimeState.cryBankLoadCount = 1;
    gStage5BRuntimeState.cryBank = bank;
}

void Stage5BC_RecordIconIndex(u32 species, u32 form, u32 index) {
    if (species != SPECIES_VICTINI)
        return;
    gStage5BRuntimeState.iconIndexCallCount = 1;
    gStage5BRuntimeState.iconSpecies = species;
    gStage5BRuntimeState.iconForm = form;
    gStage5BRuntimeState.iconIndex = index;
}

void Stage5BC_RecordIconPalette(u32 species, u32 form, u32 palette) {
    if (species != SPECIES_VICTINI)
        return;
    gStage5BRuntimeState.iconPaletteCallCount = 1;
    gStage5BRuntimeState.iconPaletteSpecies = species;
    gStage5BRuntimeState.iconPaletteForm = form;
    gStage5BRuntimeState.iconPalette = palette;
}

void Stage5BC_RecordBattleDex(void *battleDex) {
    u8 *dex = battleDex;
    u32 dexIndex = SPECIES_VICTINI - 1;
    gStage5BRuntimeState.encounterSeenAtCry =
        (dex[STAGE5BC_DEX_SEEN_OFFSET + dexIndex / 8] >> (dexIndex % 8)) & 1;
    gStage5BRuntimeState.encounterCaughtAtCry =
        (dex[STAGE5BC_DEX_CAUGHT_OFFSET + dexIndex / 8] >> (dexIndex % 8)) & 1;
    gStage5BRuntimeState.battleTurnCount++;
}
#endif

void Stage5B_RuntimeTick(void) {
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL)
        return;
    if (GetScriptVar(STAGE5B_PHASE_VAR) == 0)
        Stage5B_SeedVictini();
    Stage5B_HandleCommand();
    Stage5B_Refresh();
}

#endif
