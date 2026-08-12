#include "config.h"

#ifdef STAGE5E_MEGA_PROOF

#include "battle.h"
#include "constants/ability.h"
#include "constants/battle_constants.h"
#include "constants/item.h"
#include "constants/moves.h"
#include "constants/pokemon.h"
#include "constants/species.h"
#include "map_events_internal.h"
#include "pokemon.h"
#include "save.h"
#include "script.h"
#include "stage5e_runtime.h"

#define STAGE5E_MAGIC 0x35454D47u
#define STAGE5E_PID 0x050E0010u
#define STAGE5E_OT_ID 0x050E0A11u
#define STAGE5E_PHASE_VAR 0x416D
#define STAGE5E_HAVE_FOLLOWER_FLAG 2403
#define STAGE5E_GOT_STARTER_FLAG 106
#define STAGE5E_GOT_BAG_FLAG 283
#define STAGE5E_GOT_TRAINER_CARD_FLAG 284
#define STAGE5E_GOT_SAVE_BUTTON_FLAG 285
#define STAGE5E_GOT_OPTIONS_BUTTON_FLAG 286

volatile struct Stage5ERuntimeState gStage5ERuntimeState;

static struct Party *Stage5E_GetParty(void) {
    return SaveData_GetPlayerPartyPtr(gFieldSysPtr->savedata);
}

static struct PartyPokemon *Stage5E_GetAltaria(void) {
    struct Party *party = Stage5E_GetParty();
    if (party->count == 0)
        return NULL;
    struct PartyPokemon *mon = Party_GetMonByIndex(party, 0);
    return GetMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_ALTARIA ? mon : NULL;
}

static void Stage5E_SeedAltaria(void) {
    struct PartyPokemon altaria;
    struct Party *party = Stage5E_GetParty();
    u16 item = ITEM_ALTARIANITE;
    u16 moves[4] = { MOVE_COTTON_GUARD, MOVE_TAKE_DOWN, MOVE_MOONBLAST, MOVE_PERISH_SONG };

    PokeParty_Init(party, 6);
    PokeParaSet(&altaria, SPECIES_ALTARIA, 50, 31, TRUE, STAGE5E_PID, TRUE, STAGE5E_OT_ID);
    SetMonData(&altaria, MON_DATA_HELD_ITEM, &item);
    for (int i = 0; i < 4; i++)
        SetMonData(&altaria, MON_DATA_MOVE1 + i, &moves[i]);
    RecalcPartyPokemonStats(&altaria);
    PokeParty_Add(party, &altaria);
    SetScriptFlag(STAGE5E_GOT_STARTER_FLAG);
    SetScriptFlag(STAGE5E_GOT_BAG_FLAG);
    SetScriptFlag(STAGE5E_GOT_TRAINER_CARD_FLAG);
    SetScriptFlag(STAGE5E_GOT_SAVE_BUTTON_FLAG);
    SetScriptFlag(STAGE5E_GOT_OPTIONS_BUTTON_FLAG);
    SetScriptFlag(FLAG_MEGA_EVOLUTION_ENABLED);
    SetScriptVar(STAGE5E_PHASE_VAR, 1);
}

#ifdef STAGE6E_BATTLE_UI_PROOF
static void Stage6E_AddSwitchTarget(void) {
    struct Party *party = Stage5E_GetParty();
    if (party->count != 1)
        return;
    struct PartyPokemon magikarp;
    u16 move = MOVE_TACKLE;
    PokeParaSet(&magikarp, SPECIES_MAGIKARP, 50, 31, TRUE, 0x060E0002u, TRUE, STAGE5E_OT_ID);
    SetMonData(&magikarp, MON_DATA_MOVE1, &move);
    RecalcPartyPokemonStats(&magikarp);
    PokeParty_Add(party, &magikarp);
}
#endif

static BOOL Stage5E_EnableFollower(void) {
    struct PartyPokemon *mon = Stage5E_GetAltaria();
    if (mon == NULL)
        return FALSE;
    SetScriptFlag(STAGE5E_HAVE_FOLLOWER_FLAG);
    FollowPokeFsysParamSet(gFieldSysPtr, SPECIES_ALTARIA, 0, FALSE,
                          GetMonData(mon, MON_DATA_GENDER, NULL));
    return TRUE;
}

static void Stage5E_HandleCommand(void) {
    u32 command = gStage5ERuntimeState.command;
    BOOL result = FALSE;
    if (command == STAGE5E_COMMAND_NONE)
        return;
    if (command == STAGE5E_COMMAND_ENABLE_FOLLOWER)
        result = Stage5E_EnableFollower();
#ifdef STAGE6E_BATTLE_UI_PROOF
    else if (command == 2) {
        Stage6E_AddSwitchTarget();
        result = Stage5E_GetParty()->count == 2;
    }
#endif
    gStage5ERuntimeState.commandResult = result ? command : (0x80000000u | command);
    gStage5ERuntimeState.command = STAGE5E_COMMAND_NONE;
}

static void Stage5E_Refresh(void) {
    struct PartyPokemon *mon = Stage5E_GetAltaria();
    struct Party *party = Stage5E_GetParty();
    u32 species = mon == NULL ? SPECIES_NONE : GetMonData(mon, MON_DATA_SPECIES, NULL);
    u32 form = mon == NULL ? 0 : GetMonData(mon, MON_DATA_FORM, NULL);

    gStage5ERuntimeState.magic = STAGE5E_MAGIC;
    gStage5ERuntimeState.phase = GetScriptVar(STAGE5E_PHASE_VAR);
    gStage5ERuntimeState.partyCount = party->count;
    gStage5ERuntimeState.partySpecies = species;
    gStage5ERuntimeState.partyForm = form;
    gStage5ERuntimeState.partyAdjustedSpecies = mon == NULL ? SPECIES_NONE : GetSpeciesBasedOnForm(species, form);
    gStage5ERuntimeState.partyPid = mon == NULL ? 0 : GetMonData(mon, MON_DATA_PERSONALITY, NULL);
    gStage5ERuntimeState.partyOtId = mon == NULL ? 0 : GetMonData(mon, MON_DATA_OTID, NULL);
    gStage5ERuntimeState.partyLevel = mon == NULL ? 0 : GetMonData(mon, MON_DATA_LEVEL, NULL);
    gStage5ERuntimeState.partyExperience = mon == NULL ? 0 : GetMonData(mon, MON_DATA_EXPERIENCE, NULL);
    gStage5ERuntimeState.partyHp = mon == NULL ? 0 : GetMonData(mon, MON_DATA_HP, NULL);
    gStage5ERuntimeState.partyMaxHp = mon == NULL ? 0 : GetMonData(mon, MON_DATA_MAXHP, NULL);
    gStage5ERuntimeState.partyAttack = mon == NULL ? 0 : GetMonData(mon, MON_DATA_ATTACK, NULL);
    gStage5ERuntimeState.partyDefense = mon == NULL ? 0 : GetMonData(mon, MON_DATA_DEFENSE, NULL);
    gStage5ERuntimeState.partySpeed = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPEED, NULL);
    gStage5ERuntimeState.partySpAttack = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPECIAL_ATTACK, NULL);
    gStage5ERuntimeState.partySpDefense = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPECIAL_DEFENSE, NULL);
    gStage5ERuntimeState.partyAbility = mon == NULL ? 0 : GetMonData(mon, MON_DATA_ABILITY, NULL);
    gStage5ERuntimeState.partyType1 = mon == NULL ? 0 : GetMonData(mon, MON_DATA_TYPE_1, NULL);
    gStage5ERuntimeState.partyType2 = mon == NULL ? 0 : GetMonData(mon, MON_DATA_TYPE_2, NULL);
    for (int i = 0; i < 4; i++)
        gStage5ERuntimeState.partyMoves[i] = mon == NULL ? 0 : GetMonData(mon, MON_DATA_MOVE1 + i, NULL);
    gStage5ERuntimeState.partyHeldItem = mon == NULL ? 0 : GetMonData(mon, MON_DATA_HELD_ITEM, NULL);
    gStage5ERuntimeState.followerSpecies = mon != NULL && CheckScriptFlag(STAGE5E_HAVE_FOLLOWER_FLAG) ? species : SPECIES_NONE;
    gStage5ERuntimeState.followerForm = gFieldSysPtr->followMon.forme;
    gStage5ERuntimeState.followerAdjustedSpecies = mon == NULL ? SPECIES_NONE : GetSpeciesBasedOnForm(species, form);
    gStage5ERuntimeState.followerSprite = mon == NULL ? 0 : FollowingPokemon_GetSpriteID(species, form, GetMonData(mon, MON_DATA_GENDER, NULL));
    gStage5ERuntimeState.followerActive = gFieldSysPtr->followMon.mapObject != NULL;
    gStage5ERuntimeState.currentMap = gFieldSysPtr->location == NULL ? 0xFFFFFFFFu : (u32)gFieldSysPtr->location->mapId;
}

void LONG_CALL Stage5E_RecordEligibility(void *rawBip, u32 result, u32 canMega, u32 playerMegaed) {
    struct BI_PARAM *bip = rawBip;
    if (bip == NULL || bip->bw == NULL || bip->bw->sp == NULL)
        return;
    struct BattlePokemon *mon = &bip->bw->sp->battlemon[bip->client_no];
    if (mon->species != SPECIES_ALTARIA)
        return;
    gStage5ERuntimeState.eligibilityChecks++;
    gStage5ERuntimeState.eligibilityResult = result;
    gStage5ERuntimeState.eligibilitySpecies = mon->species;
    gStage5ERuntimeState.eligibilityForm = mon->form_no;
    gStage5ERuntimeState.eligibilityAdjustedSpecies = GetSpeciesBasedOnForm(mon->species, mon->form_no);
    gStage5ERuntimeState.eligibilityItem = mon->item;
    gStage5ERuntimeState.eligibilityCanMega = canMega;
    gStage5ERuntimeState.eligibilityPlayerMegaed = playerMegaed;
}

void LONG_CALL Stage5E_RecordMegaCommandReturn(void *rawBip) {
    struct BI_PARAM *bip = rawBip;
    if (bip == NULL || bip->bw == NULL || bip->bw->sp == NULL)
        return;
    struct BattlePokemon *mon = &bip->bw->sp->battlemon[bip->client_no];
    if (mon->species != SPECIES_ALTARIA || mon->form_no != 1 ||
        mon->states[STAT_DEFENSE] <= 6 || gStage5ERuntimeState.moveWhileMegaCount != 0)
        return;
    gStage5ERuntimeState.moveWhileMegaCount = 1;
    gStage5ERuntimeState.moveWhileMega = MOVE_COTTON_GUARD;
    gStage5ERuntimeState.moveBattleForm = mon->form_no;
    gStage5ERuntimeState.moveAdjustedSpecies =
        GetSpeciesBasedOnForm(mon->species, mon->form_no);
}

void LONG_CALL Stage5E_RecordMegaTouch(void *rawBip, u32 accepted, u32 requested) {
    struct BI_PARAM *bip = rawBip;
    if (bip == NULL || bip->bw == NULL || bip->bw->sp == NULL ||
        bip->bw->sp->battlemon[bip->client_no].species != SPECIES_ALTARIA)
        return;
    gStage5ERuntimeState.megaTouchCount++;
    gStage5ERuntimeState.megaTouchAccepted = accepted;
    gStage5ERuntimeState.megaRequested = requested;
}

void LONG_CALL Stage5E_RecordMegaQueue(void *rawBattle, u32 client, u32 sideUsed) {
    struct BattleStruct *battle = rawBattle;
    if (battle == NULL || battle->battlemon[client].species != SPECIES_ALTARIA)
        return;
    gStage5ERuntimeState.megaQueuedCount++;
    gStage5ERuntimeState.megaQueueSpecies = battle->battlemon[client].species;
    gStage5ERuntimeState.megaQueueForm = battle->battlemon[client].form_no;
    gStage5ERuntimeState.megaQueueAdjustedSpecies = GetSpeciesBasedOnForm(battle->battlemon[client].species, battle->battlemon[client].form_no);
    gStage5ERuntimeState.megaQueueSideUsed = sideUsed;
}

void LONG_CALL Stage5E_RecordMegaActive(void *rawBattle, u32 client, u32 playerMegaed, u32 sideMega) {
    struct BattleStruct *battle = rawBattle;
    if (battle == NULL || battle->battlemon[client].species != SPECIES_ALTARIA)
        return;
    struct BattlePokemon *mon = &battle->battlemon[client];
    gStage5ERuntimeState.megaActiveCount++;
    gStage5ERuntimeState.battleSpecies = mon->species;
    gStage5ERuntimeState.battleForm = mon->form_no;
    gStage5ERuntimeState.battleAdjustedSpecies = GetSpeciesBasedOnForm(mon->species, mon->form_no);
    gStage5ERuntimeState.battleItem = mon->item;
    gStage5ERuntimeState.battleHp = mon->hp;
    gStage5ERuntimeState.battleMaxHp = mon->maxhp;
    gStage5ERuntimeState.battleAttack = mon->attack;
    gStage5ERuntimeState.battleDefense = mon->defense;
    gStage5ERuntimeState.battleSpeed = mon->speed;
    gStage5ERuntimeState.battleSpAttack = mon->spatk;
    gStage5ERuntimeState.battleSpDefense = mon->spdef;
    gStage5ERuntimeState.battleAbility = mon->ability;
    gStage5ERuntimeState.battleType1 = mon->type1;
    gStage5ERuntimeState.battleType2 = mon->type2;
    gStage5ERuntimeState.playerMegaed = playerMegaed;
    gStage5ERuntimeState.sideMega = sideMega;
}

void LONG_CALL Stage5E_RecordMove(void *rawBattle) {
    struct BattleStruct *battle = rawBattle;
    if (battle == NULL || battle->attack_client >= CLIENT_MAX)
        return;
    struct BattlePokemon *mon = &battle->battlemon[battle->attack_client];
    if (mon->species != SPECIES_ALTARIA || mon->form_no != 1)
        return;
    if (gStage5ERuntimeState.moveWhileMegaCount != 0)
        return;
    gStage5ERuntimeState.moveWhileMegaCount++;
    gStage5ERuntimeState.moveWhileMega = battle->current_move_index;
    gStage5ERuntimeState.moveBattleForm = mon->form_no;
    gStage5ERuntimeState.moveAdjustedSpecies = GetSpeciesBasedOnForm(mon->species, mon->form_no);
}

void LONG_CALL Stage5E_RecordPic(u32 species, u32 form, u32 direction, u32 arc, u32 characterIndex, u32 paletteIndex) {
    if (species != SPECIES_ALTARIA)
        return;
    gStage5ERuntimeState.picCallCount++;
    gStage5ERuntimeState.picSpecies = species;
    gStage5ERuntimeState.picForm = form;
    gStage5ERuntimeState.picAdjustedSpecies = GetSpeciesBasedOnForm(species, form);
    gStage5ERuntimeState.picDirection = direction;
    gStage5ERuntimeState.picArc = arc;
    gStage5ERuntimeState.picCharacterIndex = characterIndex;
    gStage5ERuntimeState.picPaletteIndex = paletteIndex;
    if (form == 1 && direction < 2)
        gStage5ERuntimeState.picBackMegaCount++;
}

void LONG_CALL Stage5E_RecordBattleEndBefore(void *rawBattleSystem) {
    struct BattleSystem *battleSystem = rawBattleSystem;
    if (battleSystem == NULL || BattleWorkPokeCountGet(battleSystem, 0) == 0)
        return;
    struct PartyPokemon *mon = BattleWorkPokemonParamGet(battleSystem, 0, 0);
    gStage5ERuntimeState.battleEndBeforeSpecies = GetMonData(mon, MON_DATA_SPECIES, NULL);
    gStage5ERuntimeState.battleEndBeforeForm = GetMonData(mon, MON_DATA_FORM, NULL);
    gStage5ERuntimeState.battleEndBeforeAdjustedSpecies = GetSpeciesBasedOnForm(gStage5ERuntimeState.battleEndBeforeSpecies, gStage5ERuntimeState.battleEndBeforeForm);
}

void LONG_CALL Stage5E_RecordBattleEndAfter(void *rawBattleSystem, u32 flagsCleared) {
    struct BattleSystem *battleSystem = rawBattleSystem;
    if (battleSystem == NULL || BattleWorkPokeCountGet(battleSystem, 0) == 0)
        return;
    struct PartyPokemon *mon = BattleWorkPokemonParamGet(battleSystem, 0, 0);
    gStage5ERuntimeState.battleEndCount++;
    gStage5ERuntimeState.battleEndAfterSpecies = GetMonData(mon, MON_DATA_SPECIES, NULL);
    gStage5ERuntimeState.battleEndAfterForm = GetMonData(mon, MON_DATA_FORM, NULL);
    gStage5ERuntimeState.battleEndAfterAdjustedSpecies = GetSpeciesBasedOnForm(gStage5ERuntimeState.battleEndAfterSpecies, gStage5ERuntimeState.battleEndAfterForm);
    gStage5ERuntimeState.battleEndPid = GetMonData(mon, MON_DATA_PERSONALITY, NULL);
    gStage5ERuntimeState.battleEndItem = GetMonData(mon, MON_DATA_HELD_ITEM, NULL);
    gStage5ERuntimeState.battleEndFlagsCleared = flagsCleared;
}

void Stage5E_RuntimeTick(void) {
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL)
        return;
    if (gStage5ERuntimeState.battleEndCount != 0 && gFieldSysPtr->map_events != NULL)
        gFieldSysPtr->map_events->wildEncounters.rateWalk = 0;
    else if (gFieldSysPtr->location != NULL && gFieldSysPtr->location->mapId == 541 &&
             GetMetatileBehaviorAt(gFieldSysPtr, gFieldSysPtr->location->x,
                                   gFieldSysPtr->location->z) == 3)
        gFieldSysPtr->reverseTurnFrameSteps = 4;
    if (GetScriptVar(STAGE5E_PHASE_VAR) == 0 && gFieldSysPtr->location != NULL &&
        gFieldSysPtr->location->mapId == 540)
        Stage5E_SeedAltaria();
    Stage5E_HandleCommand();
    Stage5E_Refresh();
}

#endif
