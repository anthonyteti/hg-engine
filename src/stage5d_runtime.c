#include "config.h"

#ifdef STAGE5D_REGIONAL_FORM_PROOF

#include "bag.h"
#include "constants/item.h"
#include "constants/pokemon.h"
#include "constants/species.h"
#include "map_events_internal.h"
#include "pokemon.h"
#include "pokemon_storage_system.h"
#include "save.h"
#include "script.h"
#include "stage5d_runtime.h"

#define STAGE5D_MAGIC 0x35445246u
#define STAGE5D_PID 0x050D0001u
#define STAGE5D_OT_ID 0x050D0A11u
#define STAGE5D_PHASE_VAR 0x416A
#define STAGE5D_BOX_VAR 0x416B
#define STAGE5D_SLOT_VAR 0x416C
#define STAGE5D_INVALID_LOCATION 0xFFFF
#define STAGE5D_PC_SAVE_ARRAY 41
#define STAGE5D_HAVE_FOLLOWER_FLAG 2402
#define STAGE5D_GOT_STARTER_FLAG 106
#define STAGE5D_GOT_BAG_FLAG 283
#define STAGE5D_GOT_TRAINER_CARD_FLAG 284
#define STAGE5D_GOT_SAVE_BUTTON_FLAG 285
#define STAGE5D_GOT_OPTIONS_BUTTON_FLAG 286
#define STAGE5D_DEX_CAUGHT_OFFSET 0x4
#define STAGE5D_DEX_SEEN_OFFSET 0x400

void LONG_CALL FollowMon_ChangeMon(void *mapObjectManager, u32 mapNo);

volatile struct Stage5DRuntimeState gStage5DRuntimeState;

static struct Party *Stage5D_GetParty(void) {
    return SaveData_GetPlayerPartyPtr(gFieldSysPtr->savedata);
}

static PCStorage *Stage5D_GetStorage(void) {
    return SaveArray_Get((SaveData *)gFieldSysPtr->savedata, STAGE5D_PC_SAVE_ARRAY);
}

static BOOL Stage5D_IsRepresentative(u32 species, u32 form) {
    return form == 1 && (species == SPECIES_ZORUA || species == SPECIES_ZOROARK);
}

static struct PartyPokemon *Stage5D_GetPartyMon(void) {
    struct Party *party = Stage5D_GetParty();
    if (party->count == 0)
        return NULL;
    struct PartyPokemon *mon = Party_GetMonByIndex(party, 0);
    u32 species = GetMonData(mon, MON_DATA_SPECIES, NULL);
    u32 form = GetMonData(mon, MON_DATA_FORM, NULL);
    return Stage5D_IsRepresentative(species, form) ? mon : NULL;
}

static struct BoxPokemon *Stage5D_GetBoxMon(void) {
    u16 box = GetScriptVar(STAGE5D_BOX_VAR);
    u16 slot = GetScriptVar(STAGE5D_SLOT_VAR);
    if (box >= NUM_PC_BOXES || slot >= MONS_PER_BOX)
        return NULL;
    struct BoxPokemon *mon = PCStorage_GetMonByIndexPair(Stage5D_GetStorage(), box, slot);
    u32 species = GetBoxMonData(mon, MON_DATA_SPECIES, NULL);
    u32 form = GetBoxMonData(mon, MON_DATA_FORM, NULL);
    return Stage5D_IsRepresentative(species, form) ? mon : NULL;
}

static void Stage5D_SeedHisuianZorua(void) {
    struct PartyPokemon zorua;
    struct Party *party = Stage5D_GetParty();
    u8 form = 1;

    PokeParty_Init(party, 6);
    PokeParaSet(&zorua, SPECIES_ZORUA, 29, 31, TRUE, STAGE5D_PID, TRUE, STAGE5D_OT_ID);
    SetMonData(&zorua, MON_DATA_FORM, &form);
    ResetPartyPokemonAbility(&zorua);
    InitBoxMonMoveset(&zorua.box);
    RecalcPartyPokemonStats(&zorua);
    PokeParty_Add(party, &zorua);
    Bag_AddItem(Sav2_Bag_get(gFieldSysPtr->savedata), ITEM_RARE_CANDY, 2, 11);
    SetScriptFlag(STAGE5D_GOT_STARTER_FLAG);
    SetScriptFlag(STAGE5D_GOT_BAG_FLAG);
    SetScriptFlag(STAGE5D_GOT_TRAINER_CARD_FLAG);
    SetScriptFlag(STAGE5D_GOT_SAVE_BUTTON_FLAG);
    SetScriptFlag(STAGE5D_GOT_OPTIONS_BUTTON_FLAG);
    SetScriptVar(STAGE5D_PHASE_VAR, 1);
    SetScriptVar(STAGE5D_BOX_VAR, STAGE5D_INVALID_LOCATION);
    SetScriptVar(STAGE5D_SLOT_VAR, STAGE5D_INVALID_LOCATION);
}

static BOOL Stage5D_EnableFollower(void) {
    struct PartyPokemon *mon = Stage5D_GetPartyMon();
    if (mon == NULL)
        return FALSE;
    u32 species = GetMonData(mon, MON_DATA_SPECIES, NULL);
    u32 form = GetMonData(mon, MON_DATA_FORM, NULL);
    u32 gender = GetMonData(mon, MON_DATA_GENDER, NULL);
    SetScriptFlag(STAGE5D_HAVE_FOLLOWER_FLAG);
    FollowPokeFsysParamSet(gFieldSysPtr, species, form, FALSE, gender);
    return TRUE;
}

static BOOL Stage5D_AddPcCompanion(void) {
    struct PartyPokemon companion;
    struct Party *party = Stage5D_GetParty();
    if (party->count != 1 || Stage5D_GetPartyMon() == NULL)
        return FALSE;
    PokeParaSet(&companion, SPECIES_CHIKORITA, 5, 31, TRUE, 0x050D0002u, TRUE, STAGE5D_OT_ID);
    RecalcPartyPokemonStats(&companion);
    return PokeParty_Add(party, &companion);
}

static BOOL Stage5D_Deposit(void) {
    struct PartyPokemon *mon = Stage5D_GetPartyMon();
    int box;
    int slot;
    if (mon == NULL || !PCStorage_FindFirstEmptySlot(Stage5D_GetStorage(), &box, &slot))
        return FALSE;
    u32 species = GetMonData(mon, MON_DATA_SPECIES, NULL);
    if (!PCStorage_PlaceMonInBoxByIndexPair(Stage5D_GetStorage(), box, slot, &mon->box))
        return FALSE;
    PokeParty_Delete(Stage5D_GetParty(), 0);
    ClearScriptFlag(STAGE5D_HAVE_FOLLOWER_FLAG);
    FollowMon_ChangeMon(gFieldSysPtr->mapObjectMan, gFieldSysPtr->location->mapId);
    SetScriptVar(STAGE5D_BOX_VAR, box);
    SetScriptVar(STAGE5D_SLOT_VAR, slot);
    SetScriptVar(STAGE5D_PHASE_VAR, species == SPECIES_ZOROARK ? 5 : 2);
    return TRUE;
}

static BOOL Stage5D_Withdraw(void) {
    struct BoxPokemon *boxMon = Stage5D_GetBoxMon();
    struct PartyPokemon mon;
    u16 box = GetScriptVar(STAGE5D_BOX_VAR);
    u16 slot = GetScriptVar(STAGE5D_SLOT_VAR);
    if (boxMon == NULL)
        return FALSE;
    CopyBoxPokemonToPokemon(boxMon, &mon);
    if (!PokeParty_Add(Stage5D_GetParty(), &mon))
        return FALSE;
    PCStorage_DeleteBoxMonByIndexPair(Stage5D_GetStorage(), box, slot);
    SetScriptVar(STAGE5D_PHASE_VAR, 3);
    return TRUE;
}

static void Stage5D_ResetPresentation(void) {
    gStage5DRuntimeState.iconIndexCallCount = 0;
    gStage5DRuntimeState.iconPaletteCallCount = 0;
    gStage5DRuntimeState.picCallCount = 0;
    gStage5DRuntimeState.iconSpecies = 0;
    gStage5DRuntimeState.iconForm = 0;
    gStage5DRuntimeState.iconAdjustedSpecies = 0;
    gStage5DRuntimeState.iconIndex = 0;
    gStage5DRuntimeState.picSpecies = 0;
    gStage5DRuntimeState.picForm = 0;
    gStage5DRuntimeState.picAdjustedSpecies = 0;
    gStage5DRuntimeState.picBackCallCount = 0;
    gStage5DRuntimeState.picBackAdjustedSpecies = 0;
    gStage5DRuntimeState.picFrontCallCount = 0;
    gStage5DRuntimeState.picFrontAdjustedSpecies = 0;
}

static void Stage5D_HandleCommand(void) {
    u32 command = gStage5DRuntimeState.command;
    BOOL result = FALSE;
    if (command == STAGE5D_COMMAND_NONE)
        return;
    if (command == STAGE5D_COMMAND_ENABLE_FOLLOWER)
        result = Stage5D_EnableFollower();
    else if (command == STAGE5D_COMMAND_RESET_PRESENTATION) {
        Stage5D_ResetPresentation();
        result = TRUE;
    } else if (command == STAGE5D_COMMAND_ADD_PC_COMPANION)
        result = Stage5D_AddPcCompanion();
    else if (command == STAGE5D_COMMAND_DEPOSIT)
        result = Stage5D_Deposit();
    else if (command == STAGE5D_COMMAND_WITHDRAW)
        result = Stage5D_Withdraw();
    gStage5DRuntimeState.commandResult = result ? command : 0x80000000u | command;
    gStage5DRuntimeState.command = STAGE5D_COMMAND_NONE;
}

static u32 Stage5D_DexBit(u8 *dex, u32 species, u32 offset) {
    u32 index = species - 1;
    return (dex[offset + index / 8] >> (index % 8)) & 1;
}

static void Stage5D_Refresh(void) {
    struct PartyPokemon *mon = Stage5D_GetPartyMon();
    struct BoxPokemon *boxMon = Stage5D_GetBoxMon();
    struct Party *party = Stage5D_GetParty();
    u8 *dex = SaveData_GetDexPtr(gFieldSysPtr->savedata);
    u32 species = mon == NULL ? SPECIES_NONE : GetMonData(mon, MON_DATA_SPECIES, NULL);
    u32 form = mon == NULL ? 0 : GetMonData(mon, MON_DATA_FORM, NULL);
    u32 boxSpecies = boxMon == NULL ? SPECIES_NONE : GetBoxMonData(boxMon, MON_DATA_SPECIES, NULL);
    u32 boxForm = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_FORM, NULL);

    gStage5DRuntimeState.magic = STAGE5D_MAGIC;
    gStage5DRuntimeState.phase = GetScriptVar(STAGE5D_PHASE_VAR);
    gStage5DRuntimeState.partyCount = party->count;
    gStage5DRuntimeState.partySpecies = species;
    gStage5DRuntimeState.partyForm = form;
    gStage5DRuntimeState.partyAdjustedSpecies = mon == NULL ? SPECIES_NONE : GetSpeciesBasedOnForm(species, form);
    gStage5DRuntimeState.partyLevel = mon == NULL ? 0 : GetMonData(mon, MON_DATA_LEVEL, NULL);
    gStage5DRuntimeState.partyPid = mon == NULL ? 0 : GetMonData(mon, MON_DATA_PERSONALITY, NULL);
    gStage5DRuntimeState.partyOtId = mon == NULL ? 0 : GetMonData(mon, MON_DATA_OTID, NULL);
    gStage5DRuntimeState.partyExperience = mon == NULL ? 0 : GetMonData(mon, MON_DATA_EXPERIENCE, NULL);
    gStage5DRuntimeState.partyHp = mon == NULL ? 0 : GetMonData(mon, MON_DATA_HP, NULL);
    gStage5DRuntimeState.partyMaxHp = mon == NULL ? 0 : GetMonData(mon, MON_DATA_MAXHP, NULL);
    gStage5DRuntimeState.partyAttack = mon == NULL ? 0 : GetMonData(mon, MON_DATA_ATTACK, NULL);
    gStage5DRuntimeState.partyDefense = mon == NULL ? 0 : GetMonData(mon, MON_DATA_DEFENSE, NULL);
    gStage5DRuntimeState.partySpeed = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPEED, NULL);
    gStage5DRuntimeState.partySpAttack = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPECIAL_ATTACK, NULL);
    gStage5DRuntimeState.partySpDefense = mon == NULL ? 0 : GetMonData(mon, MON_DATA_SPECIAL_DEFENSE, NULL);
    gStage5DRuntimeState.partyAbility = mon == NULL ? 0 : GetMonData(mon, MON_DATA_ABILITY, NULL);
    gStage5DRuntimeState.partyType1 = mon == NULL ? 0 : GetMonData(mon, MON_DATA_TYPE_1, NULL);
    gStage5DRuntimeState.partyType2 = mon == NULL ? 0 : GetMonData(mon, MON_DATA_TYPE_2, NULL);
    for (int i = 0; i < 4; i++)
        gStage5DRuntimeState.partyMoves[i] = mon == NULL ? 0 : GetMonData(mon, MON_DATA_MOVE1 + i, NULL);
    gStage5DRuntimeState.partyFriendship = mon == NULL ? 0 : GetMonData(mon, MON_DATA_FRIENDSHIP, NULL);
    gStage5DRuntimeState.partyHeldItem = mon == NULL ? 0 : GetMonData(mon, MON_DATA_HELD_ITEM, NULL);
    gStage5DRuntimeState.partyBall = mon == NULL ? 0 : GetMonData(mon, MON_DATA_POKEBALL, NULL);
    gStage5DRuntimeState.partyGender = mon == NULL ? 0 : GetMonData(mon, MON_DATA_GENDER, NULL);
    gStage5DRuntimeState.partyIvs = mon == NULL ? 0 : GetMonData(mon, MON_DATA_IVS_WORD, NULL);
    gStage5DRuntimeState.rareCandyCount = Bag_GetQuantity(Sav2_Bag_get(gFieldSysPtr->savedata), ITEM_RARE_CANDY, 11);
    gStage5DRuntimeState.followerSpecies = mon != NULL && CheckScriptFlag(STAGE5D_HAVE_FOLLOWER_FLAG) ? species : SPECIES_NONE;
    gStage5DRuntimeState.followerForm = gFieldSysPtr->followMon.forme;
    gStage5DRuntimeState.followerAdjustedSpecies = mon == NULL ? SPECIES_NONE : GetSpeciesBasedOnForm(species, form);
    gStage5DRuntimeState.followerSprite = mon == NULL ? 0 : FollowingPokemon_GetSpriteID(species, form, GetMonData(mon, MON_DATA_GENDER, NULL));
    gStage5DRuntimeState.followerActive = gFieldSysPtr->followMon.mapObject != NULL;
    gStage5DRuntimeState.currentMap = gFieldSysPtr->location == NULL ? 0xFFFFFFFFu : (u32)gFieldSysPtr->location->mapId;
    gStage5DRuntimeState.boxNumber = GetScriptVar(STAGE5D_BOX_VAR);
    gStage5DRuntimeState.boxSlot = GetScriptVar(STAGE5D_SLOT_VAR);
    gStage5DRuntimeState.boxSpecies = boxSpecies;
    gStage5DRuntimeState.boxForm = boxForm;
    gStage5DRuntimeState.boxAdjustedSpecies = boxMon == NULL ? SPECIES_NONE : GetSpeciesBasedOnForm(boxSpecies, boxForm);
    gStage5DRuntimeState.boxLevel = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_LEVEL, NULL);
    gStage5DRuntimeState.boxPid = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_PERSONALITY, NULL);
    gStage5DRuntimeState.boxExperience = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_EXPERIENCE, NULL);
    for (int i = 0; i < 4; i++)
        gStage5DRuntimeState.boxMoves[i] = boxMon == NULL ? 0 : GetBoxMonData(boxMon, MON_DATA_MOVE1 + i, NULL);
    gStage5DRuntimeState.dexZoruaSeen = Stage5D_DexBit(dex, SPECIES_ZORUA, STAGE5D_DEX_SEEN_OFFSET);
    gStage5DRuntimeState.dexZoruaCaught = Stage5D_DexBit(dex, SPECIES_ZORUA, STAGE5D_DEX_CAUGHT_OFFSET);
    gStage5DRuntimeState.dexZoroarkSeen = Stage5D_DexBit(dex, SPECIES_ZOROARK, STAGE5D_DEX_SEEN_OFFSET);
    gStage5DRuntimeState.dexZoroarkCaught = Stage5D_DexBit(dex, SPECIES_ZOROARK, STAGE5D_DEX_CAUGHT_OFFSET);
    gStage5DRuntimeState.dexHisuianZoruaSeen = Stage5D_DexBit(dex, SPECIES_ZORUA_HISUIAN, STAGE5D_DEX_SEEN_OFFSET);
    gStage5DRuntimeState.dexHisuianZoruaCaught = Stage5D_DexBit(dex, SPECIES_ZORUA_HISUIAN, STAGE5D_DEX_CAUGHT_OFFSET);
    gStage5DRuntimeState.dexHisuianZoroarkSeen = Stage5D_DexBit(dex, SPECIES_ZOROARK_HISUIAN, STAGE5D_DEX_SEEN_OFFSET);
    gStage5DRuntimeState.dexHisuianZoroarkCaught = Stage5D_DexBit(dex, SPECIES_ZOROARK_HISUIAN, STAGE5D_DEX_CAUGHT_OFFSET);
}

void Stage5D_RecordEvolutionCheck(u32 source, u32 sourceForm, u32 target, u32 targetForm, u32 method, u32 context) {
    if (!Stage5D_IsRepresentative(source, sourceForm) || target == SPECIES_NONE)
        return;
    gStage5DRuntimeState.evolutionCheckCount++;
    gStage5DRuntimeState.evolutionSource = source;
    gStage5DRuntimeState.evolutionSourceForm = sourceForm;
    gStage5DRuntimeState.evolutionTarget = target;
    gStage5DRuntimeState.evolutionTargetForm = targetForm;
    gStage5DRuntimeState.evolutionMethod = method;
    gStage5DRuntimeState.evolutionContext = context;
}

void Stage5D_RecordSpeciesMutation(u32 source, u32 sourceForm, u32 target, u32 targetForm) {
    if (!Stage5D_IsRepresentative(source, sourceForm) || source == target)
        return;
    gStage5DRuntimeState.speciesMutationCount++;
    gStage5DRuntimeState.mutationSource = source;
    gStage5DRuntimeState.mutationSourceForm = sourceForm;
    gStage5DRuntimeState.mutationTarget = target;
    gStage5DRuntimeState.mutationTargetForm = targetForm;
}

void Stage5D_RecordIconIndex(u32 species, u32 form, u32 index) {
    if (!Stage5D_IsRepresentative(species, form))
        return;
    gStage5DRuntimeState.iconIndexCallCount++;
    gStage5DRuntimeState.iconSpecies = species;
    gStage5DRuntimeState.iconForm = form;
    gStage5DRuntimeState.iconAdjustedSpecies = GetSpeciesBasedOnForm(species, form);
    gStage5DRuntimeState.iconIndex = index;
}

void Stage5D_RecordIconPalette(u32 species, u32 form, u32 palette) {
    if (!Stage5D_IsRepresentative(species, form))
        return;
    gStage5DRuntimeState.iconPaletteCallCount++;
    gStage5DRuntimeState.iconPaletteSpecies = species;
    gStage5DRuntimeState.iconPaletteForm = form;
    gStage5DRuntimeState.iconPaletteAdjustedSpecies = GetSpeciesBasedOnForm(species, form);
    gStage5DRuntimeState.iconPalette = palette;
}

void Stage5D_RecordPic(u32 species, u32 form, u32 direction, u32 arc, u32 characterIndex, u32 paletteIndex) {
    if (!Stage5D_IsRepresentative(species, form))
        return;
    gStage5DRuntimeState.picCallCount++;
    gStage5DRuntimeState.picSpecies = species;
    gStage5DRuntimeState.picForm = form;
    gStage5DRuntimeState.picAdjustedSpecies = GetSpeciesBasedOnForm(species, form);
    gStage5DRuntimeState.picDirection = direction;
    gStage5DRuntimeState.picArc = arc;
    gStage5DRuntimeState.picCharacterIndex = characterIndex;
    gStage5DRuntimeState.picPaletteIndex = paletteIndex;
    if (direction < 2) {
        gStage5DRuntimeState.picBackCallCount++;
        gStage5DRuntimeState.picBackAdjustedSpecies = GetSpeciesBasedOnForm(species, form);
    } else {
        gStage5DRuntimeState.picFrontCallCount++;
        gStage5DRuntimeState.picFrontAdjustedSpecies = GetSpeciesBasedOnForm(species, form);
    }
}

void Stage5D_RecordWild(u32 species, u32 level, u32 form, const u16 moves[4]) {
    if (species != SPECIES_ZORUA)
        return;
    gStage5DRuntimeState.wildCallCount++;
    gStage5DRuntimeState.wildSpecies = species;
    gStage5DRuntimeState.wildForm = form;
    gStage5DRuntimeState.wildAdjustedSpecies = GetSpeciesBasedOnForm(species, form);
    gStage5DRuntimeState.wildLevel = level;
    for (int i = 0; i < 4; i++)
        gStage5DRuntimeState.wildMoves[i] = moves[i];
}

void Stage5D_RecordLevelCheckpoint(u32 species, u32 form, u32 level) {
    if (!Stage5D_IsRepresentative(species, form))
        return;
    gStage5DRuntimeState.levelCheckpointCount++;
    gStage5DRuntimeState.levelCheckpointSpecies = species;
    gStage5DRuntimeState.levelCheckpointForm = form;
    gStage5DRuntimeState.levelCheckpointLevel = level;
}

void Stage5D_RuntimeTick(void) {
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL)
        return;
    if (GetScriptVar(STAGE5D_PHASE_VAR) == 0 && gFieldSysPtr->location != NULL &&
        gFieldSysPtr->location->mapId == 540)
        Stage5D_SeedHisuianZorua();
    Stage5D_HandleCommand();
    Stage5D_Refresh();
    gStage5DRuntimeState.followerRuntimeSpecies = gFieldSysPtr->followMon.species;
}

#endif
