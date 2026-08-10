// Test: Stage 5B - Victini resolves on both battle sides
#include "../battle_tests.h"

BEGIN_TEST {
    .battleType = BATTLE_TYPE_TRAINER,
    .weather = FIELD_CONDITION_NONE,
    .fieldCondition = 0,
    .terrain = TERRAIN_NONE,
    .playerParty = { {
        .species = SPECIES_VICTINI,
        .level = 20,
        .form = 0,
        .ability = ABILITY_VICTORY_STAR,
        .item = ITEM_NONE,
        .moves = { MOVE_INCINERATE, MOVE_NONE, MOVE_NONE, MOVE_NONE },
        .hp = FULL_HP,
    } },
    .enemyParty = { {
        .species = SPECIES_VICTINI,
        .level = 20,
        .form = 0,
        .ability = ABILITY_VICTORY_STAR,
        .item = ITEM_NONE,
        .moves = { MOVE_FOCUS_ENERGY, MOVE_NONE, MOVE_NONE, MOVE_NONE },
        .hp = FULL_HP,
    } },
    .playerScript = { {
        { ACTION_MOVE_SLOT_1, BATTLER_ENEMY_FIRST },
        { ACTION_NONE, 0 },
    } },
    .enemyScript = { {
        { ACTION_MOVE_SLOT_1, BATTLER_PLAYER_FIRST },
        { ACTION_NONE, 0 },
    } },
    .expectations = {
        { .expectationType = EXPECTATION_TYPE_MESSAGE, .expectationValue.message = "The opposing Victini is getting pumped!" },
        { .expectationType = EXPECTATION_TYPE_MESSAGE, .expectationValue.message = "Victini used Incinerate!" },
    },
} END_TEST
