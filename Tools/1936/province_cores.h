#ifndef PROVINCE_CORES_H
#define PROVINCE_CORES_H

typedef struct {
    unsigned short province_id;
    unsigned char  country_id;
} ProvinceCore;

#define PROVINCE_CORE_COUNT 414

extern const ProvinceCore province_cores[PROVINCE_CORE_COUNT];

#endif
