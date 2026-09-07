#ifndef POLITICAL_DATA_H
#define POLITICAL_DATA_H

typedef enum {
    IDEOLOGY_FASCISM = 0,
    IDEOLOGY_DEMOCRACY = 1,
    IDEOLOGY_COMMUNISM = 2,
    IDEOLOGY_AUTOCRACY = 3
} Ideology;

#define IDEOLOGY_COUNT 4

#define LEADER_NONE 0xFF

typedef struct {
    const char*   name;
    unsigned char country_id;
    unsigned char ideology;
    unsigned char portrait_id; // stable leader reference key
} Leader;

#define LEADER_COUNT 138

extern const Leader leaders[LEADER_COUNT];

typedef struct {
    unsigned char ideology_support[IDEOLOGY_COUNT];
    unsigned char ruling_ideology;
    unsigned char stability;
    unsigned char current_leader[IDEOLOGY_COUNT];
} CountryPolitics;

#define COUNTRY_POLITICS_COUNT 33

extern const CountryPolitics country_politics[COUNTRY_POLITICS_COUNT];

#endif
