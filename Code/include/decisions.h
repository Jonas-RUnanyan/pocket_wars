#ifndef DECISIONS_H
#define DECISIONS_H

#include <nds.h>
#include "decisions_data.h"
#include "political_data.h"
#include "countries.h"

// Mutable runtime copy of political state. country_politics[] (political_data.h)
// stays const — it's the authored starting point. This is what decisions read
// and write, and what all game UI should display from now on.
extern CountryPolitics country_politics_runtime[COUNTRY_POLITICS_COUNT];

// has ANY country ever taken decision i (global, for DECISION_TAKEN condition)
extern bool decision_taken[DECISION_COUNT];

void initDecisionsSystem();  // call once per new game — copies authored state in, clears trackers

bool evaluateConditionProgram(unsigned short offset, unsigned short length, unsigned char countryId);
bool isDecisionVisible(int decisionIdx, unsigned char countryId);
bool isDecisionAvailable(int decisionIdx, unsigned char countryId);
void takeDecision(int decisionIdx, unsigned char countryId);

// Internal Politics screen (bottom screen: list + take button, top screen: detail)
void enterDecisionsState();
void updateDecisionsState(int keys, int pressed);

#endif