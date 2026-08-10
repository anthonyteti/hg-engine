#ifndef STAGE5B_RUNTIME_H
#define STAGE5B_RUNTIME_H

#include "types.h"

enum Stage5BRuntimeCommand {
    STAGE5B_COMMAND_NONE = 0,
    STAGE5B_COMMAND_MARK_SEEN = 1,
    STAGE5B_COMMAND_MARK_CAUGHT = 2,
    STAGE5B_COMMAND_DEPOSIT = 3,
    STAGE5B_COMMAND_WITHDRAW = 4,
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
};

#ifdef STAGE5B_RUNTIME_PROOF
extern volatile struct Stage5BRuntimeState gStage5BRuntimeState;
void Stage5B_RuntimeTick(void);
#endif

#endif
