#include "turn_system.h"
#define DEBUG_PAUSE(frames) for (int _i = 0; _i < (frames); _i++) swiWaitForVBlank()
#include "decisions.h"

unsigned char PLAYER_COUNTRY = 0;  // default until country select sets it

GameState CURRENT_TURN;
TurnStage CURRENT_STAGE;

void init_turn_system(){
  CURRENT_STAGE = PHASE_INPUT;
  CURRENT_TURN.current_country = 0;
  CURRENT_TURN.current_turn = 0;
  CURRENT_TURN.awaiting_orders = (CURRENT_TURN.current_country == PLAYER_COUNTRY);
  initDecisionsSystem();
}

void ai_actions() {
    // blank for now
	DEBUG_PAUSE(10);
}

void pass_turn(int pressed) {
    if (CURRENT_TURN.awaiting_orders) {
        if (pressed & KEY_START)
            next_country();
    } else {
        ai_actions();
        next_country();
    }
}

void calculate_movement(){
  printf("CURRENT PHASE: %s\n","MOVEMENT");
  DEBUG_PAUSE(60);
}
void calculate_combat(){
  printf("CURRENT PHASE: %s\n","COMBAT");
  DEBUG_PAUSE(60);
}
void calculate_resources(){
  printf("CURRENT PHASE: %s\n","RESOURCES");
  DEBUG_PAUSE(60);
}
void calculate_events(){
  printf("CURRENT PHASE: %s\n","EVENTS");
  DEBUG_PAUSE(60);
}

void phase_actions(){/*
  printf("CURRENT PHASE: %s\n","1");
  calculate_movement();
  printf("CURRENT PHASE: %s\n","2");
  calculate_combat();
  printf("CURRENT PHASE: %s\n","3");
  calculate_resources();
  printf("CURRENT PHASE: %s\n","4");
  calculate_events();*/
}

void next_country() {
  if (CURRENT_TURN.current_country == COUNTRY_COUNT-1) {
    phase_actions();
    CURRENT_TURN.current_turn++;
    CURRENT_TURN.current_country = 0;
    CURRENT_STAGE = PHASE_INPUT;
  } else {
    CURRENT_TURN.current_country++;
  }

  CURRENT_TURN.awaiting_orders = (CURRENT_TURN.current_country == PLAYER_COUNTRY);
}