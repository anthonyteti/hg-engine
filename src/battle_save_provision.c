#include "config.h"

#ifdef BATTLE_SAVE_PROVISION

#include "battle_save_provision.h"
#include "constants/species.h"
#include "pokemon.h"
#include "save.h"
#include "script.h"

volatile struct BattleSaveProvisionState gBattleSaveProvisionState;

static void BattleSaveProvisionEnsureParty(void) {
    struct Party *party = SaveData_GetPlayerPartyPtr((SaveData *)gFieldSysPtr->savedata);
    if (party->count == 0) {
        struct PartyPokemon starter;
        PokeParaSet(&starter, SPECIES_CHIKORITA, 5, 31, FALSE, 0, TRUE, 0x050B0002);
        InitBoxMonMoveset(&starter.box);
        RecalcPartyPokemonStats(&starter);
        PokeParty_Add(party, &starter);
    }
    gBattleSaveProvisionState.partyCount = party->count;
    gBattleSaveProvisionState.leadSpecies = GetMonData(Party_GetMonByIndex(party, 0), MON_DATA_SPECIES, NULL);
}

void BattleSaveProvisionTick(void) {
    gBattleSaveProvisionState.magic = BATTLE_SAVE_PROVISION_MAGIC;
    gBattleSaveProvisionState.ticks++;
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL || gFieldSysPtr->location == NULL)
        return;
    gBattleSaveProvisionState.mapId = gFieldSysPtr->location->mapId;
    gBattleSaveProvisionState.x = gFieldSysPtr->location->x;
    gBattleSaveProvisionState.z = gFieldSysPtr->location->z;
    if (gBattleSaveProvisionState.attempted || gBattleSaveProvisionState.ticks < 300)
        return;
    BattleSaveProvisionEnsureParty();
    gBattleSaveProvisionState.attempted = TRUE;
    gBattleSaveProvisionState.writeStatus = SaveGameNormal((SaveData *)gFieldSysPtr->savedata);
}

#endif
