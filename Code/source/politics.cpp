#include "politics.h"

const char* IDEOLOGY_NAMES[] = {
    "FASCISM", "DEMOCRACY", "COMMUNISM", "AUTOCRACY"
};


// Name of whoever's actually ruling under a country's ruling ideology right now.
// Defensive bounds check: COUNTRY_POLITICS_COUNT could drift from COUNTRY_COUNT if
// political_editor.py's export gets out of sync with a later country_filler.py edit
// (e.g. someone adds a country and forgets to re-run the political tool) — checking
// against COUNTRY_POLITICS_COUNT specifically (the actual array size) rather than
// COUNTRY_COUNT avoids reading past the end of country_politics[] if that happens.
const char* get_ruling_leader_name(unsigned char country_id)
{
    if (country_id >= COUNTRY_POLITICS_COUNT) return "UNKNOWN";

    const CountryPolitics* pol = &country_politics_runtime[country_id];
    unsigned char leader_idx = pol->current_leader[pol->ruling_ideology];

    if (leader_idx == LEADER_NONE) return "NO LEADER";
    return leaders[leader_idx].name;
}

unsigned char get_ruling_ideology(unsigned char country_id)
{
    if (country_id >= COUNTRY_POLITICS_COUNT) return IDEOLOGY_AUTOCRACY; // arbitrary but consistent fallback
    return country_politics_runtime[country_id].ruling_ideology;
}