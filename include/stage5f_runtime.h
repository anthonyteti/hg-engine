#ifndef STAGE5F_RUNTIME_H
#define STAGE5F_RUNTIME_H

#include "types.h"

#define STAGE5F_DEX_REPRESENTATIVE_COUNT 5

struct Stage5FRuntimeState {
    u32 magic;
    u32 initialized;
    u32 representativeCount;
    u32 species[STAGE5F_DEX_REPRESENTATIVE_COUNT];
    u32 seen[STAGE5F_DEX_REPRESENTATIVE_COUNT];
    u32 caught[STAGE5F_DEX_REPRESENTATIVE_COUNT];
    u32 ownedCount;
    u32 currentMap;
    u32 boundarySpecies;
    u32 boundarySeen;
    u32 boundaryCaught;
};

#ifdef STAGE5F_DEX_PROOF
extern volatile struct Stage5FRuntimeState gStage5FRuntimeState;
void Stage5F_RuntimeTick(void);
#endif

#endif
