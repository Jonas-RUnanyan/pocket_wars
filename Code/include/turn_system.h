#ifndef TURN_SYSTEM_H
#define TURN_SYSTEM_H

#include <stdint.h>
#include <stdbool.h>
#include <nds.h>
#include <stdio.h>
#include <unistd.h>
#include "countries.h"

extern unsigned char PLAYER_COUNTRY;  // was #define, now runtime-settable

typedef enum {
    PHASE_INPUT,
} TurnStage;

typedef struct {
    unsigned char current_country;
    int current_turn;
    bool awaiting_orders;
} GameState;

extern GameState CURRENT_TURN;
extern TurnStage CURRENT_STAGE;

void init_turn_system();
void pass_turn(int pressed);
void next_country();
void ai_actions();
void phase_actions();

#endif