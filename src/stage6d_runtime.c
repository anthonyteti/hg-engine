#include "config.h"

#ifdef STAGE6D_DECLARATIVE_UI_PROOF

#include "constants/buttons.h"
#include "generated/stage6d_ui.h"
#include "message.h"
#include "pokemon.h"
#include "save.h"
#include "script.h"
#include "stage6d_runtime.h"
#include "system.h"
#include "sprite.h"
#include "window.h"

#define STAGE6D_MAGIC 0x36445549u
#define STAGE6D_ACTION_CLOSE 3
#define STAGE6D_BG_MAIN_3 3
#define STAGE6D_HEAP_FIELD1 4
#define STAGE6D_TEXT_COLOR 0x00010200u

volatile Stage6DRuntimeState gStage6DRuntimeState;
static struct Window sStage6DWindows[STAGE6D_UI_COMPONENT_COUNT];
static BOOL sStage6DAdded[STAGE6D_UI_COMPONENT_COUNT];
static u32 sStage6DSelection;
static u32 sStage6DPreviousSelection = 0xFFFFFFFFu;
static u16 sStage6DPreviousKeys;

static void Stage6D_PrintComponent(u32 index, BOOL selected) {
    const Stage6DUIComponent *component = &sStage6DUIComponents[index];
    String *text = String_New(STAGE6D_UI_MAX_TEXT, STAGE6D_HEAP_FIELD1);
    FillWindowPixelBuffer(&sStage6DWindows[index], selected ? component->selectedFill : component->fill);
    CopyU16ArrayToString(text, sStage6DUIText[index]);
    AddTextPrinterParameterizedWithColor(&sStage6DWindows[index], 0, text, 4, 4, 0xFF, STAGE6D_TEXT_COLOR, NULL);
    ScheduleWindowCopyToVram(&sStage6DWindows[index]);
    String_Delete(text);
}

static void Stage6D_RenderSelection(void) {
    for (u32 index = 0; index < STAGE6D_UI_COMPONENT_COUNT; index++) {
        BOOL selected = sStage6DUIComponents[index].buttonSlot == sStage6DSelection;
        Stage6D_PrintComponent(index, selected);
    }
    sStage6DPreviousSelection = sStage6DSelection;
}

static void Stage6D_Open(void) {
    if (gStage6DRuntimeState.open)
        return;
    /* Publish the lifecycle state before issuing asynchronous BG/window work;
     * QA must synchronize on the semantic screen state, not a later renderer
     * side effect. */
    gStage6DRuntimeState.open = 1;
    for (u32 index = 0; index < STAGE6D_UI_COMPONENT_COUNT; index++) {
        const Stage6DUIComponent *component = &sStage6DUIComponents[index];
        AddWindowParameterized(gFieldSysPtr->bg_config, &sStage6DWindows[index], STAGE6D_BG_MAIN_3,
            component->x, component->y, component->width, component->height,
            component->palette, component->baseTile);
        sStage6DAdded[index] = TRUE;
    }
    SetBgPriority(STAGE6D_BG_MAIN_3, 0);
    sStage6DSelection = STAGE6D_UI_INITIAL_SELECTION;
    Stage6D_RenderSelection();
}

static void Stage6D_Close(void) {
    for (u32 index = 0; index < STAGE6D_UI_COMPONENT_COUNT; index++) {
        if (sStage6DAdded[index]) {
            FillWindowPixelBuffer(&sStage6DWindows[index], 0);
            ScheduleWindowCopyToVram(&sStage6DWindows[index]);
            RemoveWindow(&sStage6DWindows[index]);
            sStage6DAdded[index] = FALSE;
        }
    }
    gStage6DRuntimeState.open = 0;
}

static void Stage6D_Activate(u32 action) {
    gStage6DRuntimeState.lastAction = action;
    gStage6DRuntimeState.actionCount++;
    if (action == STAGE6D_ACTION_CLOSE)
        Stage6D_Close();
}

static void Stage6D_HandleTouch(void) {
    if (!gSystem.touchNew)
        return;
    for (u32 index = 0; index < STAGE6D_UI_COMPONENT_COUNT; index++) {
        const Stage6DUIComponent *component = &sStage6DUIComponents[index];
        if (component->buttonSlot == 0xFF || component->touch[2] == 0)
            continue;
        if (gSystem.touchX >= component->touch[0] && gSystem.touchX < component->touch[2] &&
            gSystem.touchY >= component->touch[1] && gSystem.touchY < component->touch[3]) {
            sStage6DSelection = component->buttonSlot;
            gStage6DRuntimeState.touchCount++;
            Stage6D_Activate(sStage6DUINavigation[sStage6DSelection].confirmAction);
            return;
        }
    }
}

static void Stage6D_UpdateBindings(void) {
    struct Party *party = SaveData_GetPlayerPartyPtr(gFieldSysPtr->savedata);
    if (party->count <= 0) {
        gStage6DRuntimeState.leadSpecies = SPECIES_NONE;
        gStage6DRuntimeState.leadLevel = 0;
        gStage6DRuntimeState.leadHp = 0;
        gStage6DRuntimeState.leadMaxHp = 0;
        return;
    }
    struct PartyPokemon *mon = Party_GetMonByIndex(party, 0);
    gStage6DRuntimeState.leadSpecies = GetMonData(mon, MON_DATA_SPECIES, NULL);
    gStage6DRuntimeState.leadLevel = GetMonData(mon, MON_DATA_LEVEL, NULL);
    gStage6DRuntimeState.leadHp = GetMonData(mon, MON_DATA_HP, NULL);
    gStage6DRuntimeState.leadMaxHp = GetMonData(mon, MON_DATA_MAXHP, NULL);
}

void Stage6D_RuntimeTick(void) {
    u16 heldKeys;
    u16 newKeys;
    if (gFieldSysPtr == NULL || gFieldSysPtr->savedata == NULL || gFieldSysPtr->bg_config == NULL)
        return;
    gStage6DRuntimeState.magic = STAGE6D_MAGIC;
    gStage6DRuntimeState.sourceToken = STAGE6D_UI_SOURCE_TOKEN;
    gStage6DRuntimeState.componentCount = STAGE6D_UI_COMPONENT_COUNT;
    gStage6DRuntimeState.bindingCount = STAGE6D_UI_BINDING_COUNT;
    gStage6DRuntimeState.tileCount = STAGE6D_UI_TILE_COUNT;
    Stage6D_UpdateBindings();
    heldKeys = PAD_Read();
    newKeys = heldKeys & ~sStage6DPreviousKeys;
    sStage6DPreviousKeys = heldKeys;
    if (gStage6DRuntimeState.command != gStage6DRuntimeState.acknowledgedCommand) {
        gStage6DRuntimeState.acknowledgedCommand = gStage6DRuntimeState.command;
        if (gStage6DRuntimeState.command == 1)
            Stage6D_Open();
        else if (gStage6DRuntimeState.command == 2)
            Stage6D_Close();
    }
    if (!gStage6DRuntimeState.open) {
        if (newKeys & STAGE6D_UI_TRIGGER_MASK)
            Stage6D_Open();
        return;
    }
    if (newKeys & PAD_KEY_LEFT)
        sStage6DSelection = sStage6DUINavigation[sStage6DSelection].left;
    if (newKeys & PAD_KEY_RIGHT)
        sStage6DSelection = sStage6DUINavigation[sStage6DSelection].right;
    if (newKeys & PAD_BUTTON_A)
        Stage6D_Activate(sStage6DUINavigation[sStage6DSelection].confirmAction);
    if (newKeys & PAD_BUTTON_B)
        Stage6D_Activate(sStage6DUINavigation[sStage6DSelection].cancelAction);
    Stage6D_HandleTouch();
    if (gStage6DRuntimeState.open && sStage6DPreviousSelection != sStage6DSelection)
        Stage6D_RenderSelection();
    gStage6DRuntimeState.selected = sStage6DSelection;
}

#endif
