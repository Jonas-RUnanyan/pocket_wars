#ifndef COUNTRIES_H
#define COUNTRIES_H

// ideology_names index order must match Ideology enum in political_data.h
// (Fascism=0, Democracy=1, Communism=2, Autocracy=3)
typedef struct {
    const char*    name;
    const char*    ideology_names[4]; // per-ruling-ideology override, NULL = use base name
    unsigned short color;
    unsigned short capital;
    unsigned char  is_formable; // 1 = dormant at start, no authored politics, inherits on formation
} Country;

#define COUNTRY_COUNT 33
#define NO_CAPITAL    0xFFFF

extern const Country countries[COUNTRY_COUNT];

#endif
