#ifndef STAGE5D_RUNTIME_H
#define STAGE5D_RUNTIME_H

#include "types.h"

enum Stage5DRuntimeCommand {
    STAGE5D_COMMAND_NONE = 0,
    STAGE5D_COMMAND_ENABLE_FOLLOWER = 1,
    STAGE5D_COMMAND_RESET_PRESENTATION = 2,
    STAGE5D_COMMAND_ADD_PC_COMPANION = 3,
    STAGE5D_COMMAND_DEPOSIT = 4,
    STAGE5D_COMMAND_WITHDRAW = 5,
};

struct Stage5DRuntimeState {
    u32 magic;
    u32 command;
    u32 commandResult;
    u32 phase;
    u32 partyCount;
    u32 partySpecies;
    u32 partyForm;
    u32 partyAdjustedSpecies;
    u32 partyLevel;
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
    u32 followerAdjustedSpecies;
    u32 followerSprite;
    u32 followerActive;
    u32 currentMap;
    u32 evolutionCheckCount;
    u32 evolutionSource;
    u32 evolutionSourceForm;
    u32 evolutionTarget;
    u32 evolutionTargetForm;
    u32 evolutionMethod;
    u32 evolutionContext;
    u32 speciesMutationCount;
    u32 mutationSource;
    u32 mutationSourceForm;
    u32 mutationTarget;
    u32 mutationTargetForm;
    u32 iconIndexCallCount;
    u32 iconSpecies;
    u32 iconForm;
    u32 iconAdjustedSpecies;
    u32 iconIndex;
    u32 iconPaletteCallCount;
    u32 iconPaletteSpecies;
    u32 iconPaletteForm;
    u32 iconPaletteAdjustedSpecies;
    u32 iconPalette;
    u32 picCallCount;
    u32 picSpecies;
    u32 picForm;
    u32 picAdjustedSpecies;
    u32 picDirection;
    u32 picArc;
    u32 picCharacterIndex;
    u32 picPaletteIndex;
    u32 picBackCallCount;
    u32 picBackAdjustedSpecies;
    u32 picFrontCallCount;
    u32 picFrontAdjustedSpecies;
    u32 wildCallCount;
    u32 wildSpecies;
    u32 wildForm;
    u32 wildAdjustedSpecies;
    u32 wildLevel;
    u32 wildMoves[4];
    u32 boxNumber;
    u32 boxSlot;
    u32 boxSpecies;
    u32 boxForm;
    u32 boxAdjustedSpecies;
    u32 boxLevel;
    u32 boxPid;
    u32 boxExperience;
    u32 boxMoves[4];
    u32 dexZoruaSeen;
    u32 dexZoruaCaught;
    u32 dexZoroarkSeen;
    u32 dexZoroarkCaught;
    u32 levelCheckpointCount;
    u32 levelCheckpointSpecies;
    u32 levelCheckpointForm;
    u32 levelCheckpointLevel;
    u32 followerRuntimeSpecies;
    u32 dexHisuianZoruaSeen;
    u32 dexHisuianZoruaCaught;
    u32 dexHisuianZoroarkSeen;
    u32 dexHisuianZoroarkCaught;
};

#ifdef STAGE5D_REGIONAL_FORM_PROOF
extern volatile struct Stage5DRuntimeState gStage5DRuntimeState;
void Stage5D_RuntimeTick(void);
void Stage5D_RecordEvolutionCheck(u32 source, u32 sourceForm, u32 target, u32 targetForm, u32 method, u32 context);
void Stage5D_RecordSpeciesMutation(u32 source, u32 sourceForm, u32 target, u32 targetForm);
void Stage5D_RecordIconIndex(u32 species, u32 form, u32 index);
void Stage5D_RecordIconPalette(u32 species, u32 form, u32 palette);
void Stage5D_RecordPic(u32 species, u32 form, u32 direction, u32 arc, u32 characterIndex, u32 paletteIndex);
void LONG_CALL Stage5D_RecordWild(u32 species, u32 level, u32 form, const u16 moves[4]);
void Stage5D_RecordLevelCheckpoint(u32 species, u32 form, u32 level);
#endif

#endif
