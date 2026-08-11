#ifndef STAGE5C_RUNTIME_H
#define STAGE5C_RUNTIME_H

#include "types.h"

enum Stage5CRuntimeCommand {
    STAGE5C_COMMAND_NONE = 0,
    STAGE5C_COMMAND_ENABLE_FOLLOWER = 1,
    STAGE5C_COMMAND_RESET_ICON_OBSERVATION = 2,
    STAGE5C_COMMAND_ADD_PC_COMPANION = 3,
    STAGE5C_COMMAND_DEPOSIT = 4,
};

struct Stage5CRuntimeState {
    u32 magic;
    u32 command;
    u32 commandResult;
    u32 phase;
    u32 partyCount;
    u32 partySpecies;
    u32 partyLevel;
    u32 partyForm;
    u32 partyPid;
    u32 partyOtId;
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
    u32 partyFriendship;
    u32 partyHeldItem;
    u32 partyBall;
    u32 partyGender;
    u32 partyIvs;
    u32 rareCandyCount;
    u32 followerSpecies;
    u32 followerForm;
    u32 followerSprite;
    u32 followerActive;
    u32 currentMap;
    u32 evolutionCheckCount;
    u32 evolutionSource;
    u32 evolutionTarget;
    u32 evolutionMethod;
    u32 evolutionContext;
    u32 speciesMutationCount;
    u32 mutationSource;
    u32 mutationTarget;
    u32 iconIndexCallCount;
    u32 iconSpecies;
    u32 iconForm;
    u32 iconIndex;
    u32 iconPaletteCallCount;
    u32 iconPaletteSpecies;
    u32 iconPaletteForm;
    u32 iconPalette;
    u32 dexPopplioSeen;
    u32 dexPopplioCaught;
    u32 dexBrionneSeen;
    u32 dexBrionneCaught;
    u32 dexPrimarinaSeen;
    u32 dexPrimarinaCaught;
    u32 boxNumber;
    u32 boxSlot;
    u32 boxSpecies;
    u32 boxLevel;
    u32 boxForm;
    u32 boxPid;
    u32 boxExperience;
    u32 boxMoves[4];
    u32 levelCheckpointCount;
    u32 levelCheckpointSpecies;
    u32 levelCheckpointLevel;
};

#ifdef STAGE5C_EVOLUTION_PROOF
extern volatile struct Stage5CRuntimeState gStage5CRuntimeState;
void Stage5C_RuntimeTick(void);
void Stage5C_RecordEvolutionCheck(u32 source, u32 target, u32 method, u32 context);
void Stage5C_RecordSpeciesMutation(u32 source, u32 target);
void Stage5C_RecordIconIndex(u32 species, u32 form, u32 index);
void Stage5C_RecordIconPalette(u32 species, u32 form, u32 palette);
void Stage5C_RecordLevelCheckpoint(u32 species, u32 level);
#endif

#endif
