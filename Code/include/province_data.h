#ifndef PROVINCE_DATA_H
#define PROVINCE_DATA_H

#define PROVINCE_COUNT 775

typedef struct {
    const char*    name;
    unsigned int   color;
    unsigned char  owner;
    unsigned char  is_water;
    unsigned short center_x;
    unsigned short center_y;
} Province;

extern Province provinces[PROVINCE_COUNT];

#endif
