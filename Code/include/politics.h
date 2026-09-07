#ifndef POLITICS_H
#define POLITICS_H
#include "political_data.h"
#include "decisions.h"

// Ideology enum order must match political_editor.py's IDEOLOGIES list exactly —
// it's what the generated Ideology enum in political_data.h is indexed against.
extern const char* IDEOLOGY_NAMES[];

const char* get_ruling_leader_name(unsigned char country_id);

unsigned char get_ruling_ideology(unsigned char country_id);

#endif