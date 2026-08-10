#include "config.h"

#ifdef STAGE5B_RUNTIME_PROOF

#include "constants/ability.h"
#include "constants/file.h"
#include "constants/item.h"
#include "constants/moves.h"
#include "constants/pokemon.h"
#include "constants/species.h"
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
}

void Stage5B_RuntimeTick(void) {
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL)
        return;
    if (GetScriptVar(STAGE5B_PHASE_VAR) == 0)
        Stage5B_SeedVictini();
    Stage5B_HandleCommand();
    Stage5B_Refresh();
}

#endif
