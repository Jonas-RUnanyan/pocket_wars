#ifndef FORMABLE_CORES_H
#define FORMABLE_CORES_H

#include "province_cores.h" // reuses ProvinceCore

#define FORMABLE_CORE_COUNT 40

// Inert until the referenced country is actually formed (decisions.cpp applies
// these automatically inside the FORM_NATION effect) — NOT checked by is_core().
extern const ProvinceCore formable_cores[FORMABLE_CORE_COUNT];

#endif
