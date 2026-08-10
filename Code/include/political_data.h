#ifndef POLITICAL_DATA_H
#define POLITICAL_DATA_H

// Keep in sync with IDEOLOGIES[] in political_editor.py
typedef enum {
    IDEOLOGY_FASCISM = 0,
    IDEOLOGY_DEMOCRACY = 1,
    IDEOLOGY_COMMUNISM = 2,
    IDEOLOGY_AUTOCRACY = 3
} Ideology;

#define IDEOLOGY_COUNT 4

#define LEADER_NONE 0xFF // sentinel: no leader currently active for this ideology slot

typedef struct {
    const char*   name;
    unsigned char country_id;   // which country this leader belongs to
    unsigned char ideology;     // which ideology they represent
    unsigned char portrait_id;  // stable across re-exports — NOT this leader's index below,
                                // which can shift as the roster changes
} Leader;

#define LEADER_COUNT 138

extern const Leader leaders[LEADER_COUNT];

typedef struct {
    unsigned char ideology_support[IDEOLOGY_COUNT]; // percentages, should sum to 100
    unsigned char ruling_ideology;                  // index into Ideology — not necessarily the most popular
    unsigned char stability;                        // 0-100
    unsigned char current_leader[IDEOLOGY_COUNT];   // index into leaders[], or LEADER_NONE
} CountryPolitics;

#define COUNTRY_POLITICS_COUNT 32

extern const CountryPolitics country_politics[COUNTRY_POLITICS_COUNT];

#endif
