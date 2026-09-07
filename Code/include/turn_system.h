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
    unsigned char current_position;  // index into turnOrder[] — a FIXED rotation slot, never reassigned
    int current_turn;
    bool awaiting_orders;
} GameState;

extern GameState CURRENT_TURN;
extern TurnStage CURRENT_STAGE;
extern unsigned char turnOrder[COUNTRY_COUNT];

void init_turn_system();
void pass_turn(int pressed);
void next_country();
void ai_actions();
void phase_actions();
unsigned char currentActingCountry();                                   // turnOrder[CURRENT_TURN.current_position]
void swapTurnOrderPositions(unsigned char countryA, unsigned char countryB);

#endif