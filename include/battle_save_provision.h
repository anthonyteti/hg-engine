#ifndef BATTLE_SAVE_PROVISION_H
#define BATTLE_SAVE_PROVISION_H

#include "types.h"

#define BATTLE_SAVE_PROVISION_MAGIC 0x42535650u

struct BattleSaveProvisionState {
    u32 magic;
    u32 ticks;
    u32 attempted;
    u32 writeStatus;
    u32 mapId;
    u32 x;
    u32 z;
    u32 partyCount;
    u32 leadSpecies;
};

#ifdef BATTLE_SAVE_PROVISION
extern volatile struct BattleSaveProvisionState gBattleSaveProvisionState;
void BattleSaveProvisionTick(void);
#endif

#endif
