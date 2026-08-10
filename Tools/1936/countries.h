#ifndef COUNTRIES_H
#define COUNTRIES_H

typedef struct {
    const char*    name;
    unsigned short color;
    unsigned short capital;
} Country;

#define COUNTRY_COUNT 33
#define NO_CAPITAL    0xFFFF

extern const Country countries[COUNTRY_COUNT];

#endif
