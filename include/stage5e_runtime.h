#ifndef STAGE5E_RUNTIME_H
#define STAGE5E_RUNTIME_H

#include "types.h"

enum Stage5ERuntimeCommand {
    STAGE5E_COMMAND_NONE = 0,
    STAGE5E_COMMAND_ENABLE_FOLLOWER = 1,
};

struct Stage5ERuntimeState {
    u32 magic;
    u32 command;
    u32 commandResult;
    u32 phase;
    u32 partyCount;
    u32 partySpecies;
    u32 partyForm;
    u32 partyAdjustedSpecies;
    u32 partyPid;
    u32 partyOtId;
    u32 partyLevel;
    u32 partyExperience;
    u32 partyHp;
    u32 partyMaxHp;
    u32 partyAttack;
    u32 partyDefense;
    u32 partySpeed;
    u32 partySpAttack;
    u32 partySpDefense;
    u32 partyAbility;
    u32 partyType1;
    u32 partyType2;
    u32 partyMoves[4];
    u32 partyHeldItem;
    u32 followerSpecies;
    u32 followerForm;
    u32 followerAdjustedSpecies;
    u32 followerSprite;
    u32 followerActive;
    u32 currentMap;
    u32 eligibilityChecks;
    u32 eligibilityResult;
    u32 eligibilitySpecies;
    u32 eligibilityForm;
    u32 eligibilityAdjustedSpecies;
    u32 eligibilityItem;
    u32 eligibilityCanMega;
    u32 eligibilityPlayerMegaed;
    u32 megaTouchCount;
    u32 megaTouchAccepted;
    u32 megaRequested;
    u32 megaQueuedCount;
    u32 megaQueueSpecies;
    u32 megaQueueForm;
    u32 megaQueueAdjustedSpecies;
    u32 megaQueueSideUsed;
    u32 megaActiveCount;
    u32 battleSpecies;
    u32 battleForm;
    u32 battleAdjustedSpecies;
    u32 battleItem;
    u32 battleHp;
    u32 battleMaxHp;
    u32 battleAttack;
    u32 battleDefense;
    u32 battleSpeed;
    u32 battleSpAttack;
    u32 battleSpDefense;
    u32 battleAbility;
    u32 battleType1;
    u32 battleType2;
    u32 playerMegaed;
    u32 sideMega;
    u32 moveWhileMegaCount;
    u32 moveWhileMega;
    u32 moveBattleForm;
    u32 moveAdjustedSpecies;
    u32 picCallCount;
    u32 picSpecies;
    u32 picForm;
    u32 picAdjustedSpecies;
    u32 picDirection;
    u32 picArc;
    u32 picCharacterIndex;
    u32 picPaletteIndex;
    u32 picBackMegaCount;
    u32 battleEndCount;
    u32 battleEndBeforeSpecies;
    u32 battleEndBeforeForm;
    u32 battleEndBeforeAdjustedSpecies;
    u32 battleEndAfterSpecies;
    u32 battleEndAfterForm;
    u32 battleEndAfterAdjustedSpecies;
    u32 battleEndPid;
    u32 battleEndItem;
    u32 battleEndFlagsCleared;
};

#ifdef STAGE5E_MEGA_PROOF
extern volatile struct Stage5ERuntimeState gStage5ERuntimeState;
void Stage5E_RuntimeTick(void);
void LONG_CALL Stage5E_RecordEligibility(void *bip, u32 result, u32 canMega, u32 playerMegaed);
void LONG_CALL Stage5E_RecordMegaCommandReturn(void *bip);
void LONG_CALL Stage5E_RecordMegaTouch(void *bip, u32 accepted, u32 requested);
void LONG_CALL Stage5E_RecordMegaQueue(void *battle, u32 client, u32 sideUsed);
void LONG_CALL Stage5E_RecordMegaActive(void *battle, u32 client, u32 playerMegaed, u32 sideMega);
void LONG_CALL Stage5E_RecordMove(void *battle);
void LONG_CALL Stage5E_RecordPic(u32 species, u32 form, u32 direction, u32 arc, u32 characterIndex, u32 paletteIndex);
void LONG_CALL Stage5E_RecordBattleEndBefore(void *battleSystem);
void LONG_CALL Stage5E_RecordBattleEndAfter(void *battleSystem, u32 flagsCleared);
#endif

#endif
