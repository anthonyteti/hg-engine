#ifndef STAGE5B_RUNTIME_H
#define STAGE5B_RUNTIME_H

#include "types.h"

enum Stage5BRuntimeCommand {
    STAGE5B_COMMAND_NONE = 0,
    STAGE5B_COMMAND_MARK_SEEN = 1,
    STAGE5B_COMMAND_MARK_CAUGHT = 2,
    STAGE5B_COMMAND_DEPOSIT = 3,
    STAGE5B_COMMAND_WITHDRAW = 4,
    STAGE5B_COMMAND_ENABLE_FOLLOWER = 5,
    STAGE5B_COMMAND_RESET_ICON_OBSERVATION = 6,
    STAGE5B_COMMAND_ADD_PC_COMPANION = 7,
};

struct Stage5BRuntimeState {
    u32 magic;
    u32 phase;
    u32 command;
    u32 commandResult;
    u32 partySpecies;
    u32 partyLevel;
    u32 partyForm;
    u32 partyMoves[4];
    u32 partyHp;
    u32 partyMaxHp;
    u32 partyAttack;
    u32 partyDefense;
    u32 partySpeed;
    u32 partySpAttack;
    u32 partySpDefense;
    u32 partyAbility;
    u32 type1;
    u32 type2;
    u32 boxSpecies;
    u32 boxLevel;
    u32 boxForm;
    u32 boxMoves[4];
    u32 boxNumber;
    u32 boxSlot;
    u32 dexOwned;
    u32 followerSpecies;
    u32 followerForm;
    u32 followerSprite;
    u32 seenCommands;
    u32 caughtCommands;
    u32 depositCommands;
    u32 withdrawCommands;
    u32 enabledFollowerCommands;
#ifdef STAGE5BC_RUNTIME_PROOF
    /* Stage 5B-C appends shared-path observations so the Stage 5B offsets above
     * remain byte-identical for the already-proven storage scenario. */
    u32 stage5bcMagic;
    u32 currentMap;
    u32 followerActive;
    u32 trainerLoadCount;
    u32 trainerId;
    u32 trainerSpecies;
    u32 trainerLevel;
    u32 trainerForm;
    u32 trainerMoves[4];
    u32 wildLoadCount;
    u32 wildSpecies;
    u32 wildLevel;
    u32 wildForm;
    u32 wildMoves[4];
    u32 partyCount;
    u32 capturedSpecies;
    u32 capturedLevel;
    u32 capturedForm;
    u32 capturedMoves[4];
    u32 capturedAbility;
    u32 capturedPid;
    u32 dexSeen;
    u32 dexCaught;
    u32 cryRequestCount;
    u32 cryRequestedSpecies;
    u32 cryRequestedForm;
    u32 cryIdentity;
    u32 cryBankLoadCount;
    u32 cryBank;
    u32 iconIndexCallCount;
    u32 iconSpecies;
    u32 iconForm;
    u32 iconIndex;
    u32 iconPaletteCallCount;
    u32 iconPaletteSpecies;
    u32 iconPaletteForm;
    u32 iconPalette;
    u32 mapHasWildEncounters;
    u32 mapWildEncounterBank;
    u32 loadedWalkEncounterRate;
    u32 currentMetatileBehavior;
    u32 loadedFirstLandLevel;
    u32 loadedFirstLandSpecies;
    u32 encounterInhibitSteps;
    u32 reverseTurnFrameSteps;
    u32 encounterSeenAtCry;
    u32 encounterCaughtAtCry;
    u32 battleTurnCount;
#endif
};

#ifdef STAGE5B_RUNTIME_PROOF
extern volatile struct Stage5BRuntimeState gStage5BRuntimeState;
void Stage5B_RuntimeTick(void);
#endif

#ifdef STAGE5BC_RUNTIME_PROOF
void LONG_CALL Stage5BC_RecordTrainer(u32 trainerId, u32 species, u32 level, u32 form, const u16 moves[4]);
void LONG_CALL Stage5BC_RecordWild(u32 species, u32 level, u32 form, const u16 moves[4]);
void Stage5BC_RecordCryRequest(u32 species, u32 form, u32 identity);
void Stage5BC_RecordCryBank(u32 bank);
void Stage5BC_RecordIconIndex(u32 species, u32 form, u32 index);
void Stage5BC_RecordIconPalette(u32 species, u32 form, u32 palette);
void LONG_CALL Stage5BC_RecordBattleDex(void *dex);
#endif

#endif
