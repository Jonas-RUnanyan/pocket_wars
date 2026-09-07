#include "turn_system.h"
#define DEBUG_PAUSE(frames) for (int _i = 0; _i < (frames); _i++) swiWaitForVBlank()
#include "decisions.h"
#include "province_owners.h"

unsigned char PLAYER_COUNTRY = 0;  // default until country select sets it

GameState CURRENT_TURN;
TurnStage CURRENT_STAGE;
unsigned char turnOrder[COUNTRY_COUNT];

void init_turn_system(){
  for (int i = 0; i < COUNTRY_COUNT; i++)
      turnOrder[i] = i; // identity permutation — position i starts belonging to country i

  CURRENT_STAGE = PHASE_INPUT;
  CURRENT_TURN.current_position = 0;
  CURRENT_TURN.current_turn = 0;
  CURRENT_TURN.awaiting_orders = (currentActingCountry() == PLAYER_COUNTRY);
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

static bool countryActiveForTurns(unsigned char cid)
{
    if (cid >= COUNTRY_COUNT) return false;
    if (!countryExists[cid]) return false;
    for (int p = 0; p < PROVINCE_OWNER_COUNT; p++)
        if (province_owners[p] == cid) return true;
    return false;
}

void next_country() {
  int attempts = 0;
  do {
    if (CURRENT_TURN.current_position == COUNTRY_COUNT-1) {
        phase_actions();
        CURRENT_TURN.current_turn++;
        CURRENT_TURN.current_position = 0;
        CURRENT_STAGE = PHASE_INPUT;
    } else {
        CURRENT_TURN.current_position++;
    }
    attempts++;
  } while (!countryActiveForTurns(currentActingCountry()) &&
           currentActingCountry() != PLAYER_COUNTRY &&
           attempts <= COUNTRY_COUNT);

  CURRENT_TURN.awaiting_orders = (currentActingCountry() == PLAYER_COUNTRY);
}

unsigned char currentActingCountry()
{
    return turnOrder[CURRENT_TURN.current_position];
}

static int findTurnPosition(unsigned char countryId)
{
    for (int i = 0; i < COUNTRY_COUNT; i++)
        if (turnOrder[i] == countryId) return i;
    return -1;
}

void swapTurnOrderPositions(unsigned char countryA, unsigned char countryB)
{
    int posA = findTurnPosition(countryA);
    int posB = findTurnPosition(countryB);
    if (posA < 0 || posB < 0) return; // shouldn't happen — both are always valid country ids
    turnOrder[posA] = countryB;
    turnOrder[posB] = countryA;
}