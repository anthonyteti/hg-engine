#ifndef STAGE6D_RUNTIME_H
#define STAGE6D_RUNTIME_H

#include "types.h"

typedef struct Stage6DRuntimeState {
    u32 magic;
    u32 command;
    u32 acknowledgedCommand;
    u32 open;
    u32 selected;
    u32 actionCount;
    u32 lastAction;
    u32 touchCount;
    u32 sourceToken;
    u32 componentCount;
    u32 bindingCount;
    u32 tileCount;
    u32 leadSpecies;
    u32 leadLevel;
    u32 leadHp;
    u32 leadMaxHp;
} Stage6DRuntimeState;

extern volatile Stage6DRuntimeState gStage6DRuntimeState;
void Stage6D_RuntimeTick(void);

#endif
