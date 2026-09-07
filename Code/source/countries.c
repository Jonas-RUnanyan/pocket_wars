#include "countries.h"
#include <stddef.h>


const Country countries[COUNTRY_COUNT] = {
    {"Portugal", {NULL, NULL, NULL, NULL}, 0x8100, 0x0016, 0},
    {"Spain", {NULL, NULL, NULL, NULL}, 0x8F5C, 0x00F0, 0},
    {"France", {NULL, NULL, NULL, NULL}, 0xDE01, 0x004A, 0},
    {"Luxembourg", {NULL, NULL, NULL, NULL}, 0xFFE0, 0x016A, 0},
    {"Belgium", {NULL, NULL, NULL, NULL}, 0x8379, 0x00D0, 0},
    {"Netherlands", {NULL, NULL, NULL, NULL}, 0x821F, 0x0147, 0},
    {"Germany", {"Deutsches Reich", NULL, NULL, "German Empire"}, 0x98C6, 0x012E, 0},
    {"Switzerland", {NULL, NULL, NULL, NULL}, 0xA95E, 0x00C8, 0},
    {"Italy", {NULL, NULL, NULL, NULL}, 0x8200, 0x0076, 0},
    {"Austria", {"State of Austria", NULL, NULL, "Archduchy of Austria"}, 0xDAD6, 0x00EA, 0},
    {"Hungary", {NULL, NULL, NULL, NULL}, 0xE35F, 0x00FD, 0},
    {"Czechoslovakia", {NULL, NULL, NULL, NULL}, 0xCF00, 0x019D, 0},
    {"Yugoslavia", {NULL, NULL, NULL, NULL}, 0xB4E0, 0x0010, 0},
    {"Albania", {NULL, NULL, NULL, NULL}, 0x8C6A, 0x00FE, 0},
    {"Greece", {NULL, NULL, NULL, NULL}, 0xFFF0, 0x0112, 0},
    {"Bulgaria", {NULL, NULL, NULL, NULL}, 0x8340, 0x0113, 0},
    {"Romania", {NULL, NULL, NULL, NULL}, 0xC3FF, 0x010E, 0},
    {"Poland", {NULL, NULL, NULL, NULL}, 0xE21F, 0x0001, 0},
    {"Lithuania", {NULL, NULL, NULL, NULL}, 0x9BF7, 0x0013, 0},
    {"Latvia", {NULL, NULL, NULL, NULL}, 0xFE57, 0x0174, 0},
    {"Estonia", {NULL, NULL, NULL, NULL}, 0xAD40, 0x0179, 0},
    {"Denmark", {NULL, NULL, NULL, NULL}, 0x88C8, 0x00E4, 0},
    {"Sweden", {NULL, NULL, NULL, NULL}, 0xE301, 0x0036, 0},
    {"Norway", {NULL, NULL, NULL, NULL}, 0xB028, 0x0014, 0},
    {"Finland", {NULL, NULL, NULL, NULL}, 0xF7BD, 0x0015, 0},
    {"Russia", {NULL, NULL, "Soviet Union", "Russian Empire"}, 0x800D, 0x008C, 0},
    {"United Kingdom", {NULL, NULL, NULL, NULL}, 0xB417, 0x0025, 0},
    {"Ireland", {NULL, NULL, NULL, NULL}, 0xBFEF, 0x0017, 0},
    {"Turkey", {NULL, NULL, NULL, NULL}, 0xD7F9, 0x0114, 0},
    {"Iraq", {NULL, NULL, NULL, NULL}, 0x81F7, 0x00C5, 0},
    {"Saudi Arabia", {NULL, NULL, NULL, NULL}, 0x80E0, 0x00C6, 0},
    {"Persia", {NULL, NULL, NULL, NULL}, 0x97AF, 0x00BF, 0},
    {"Austria-Hungary", {NULL, "Danubian Confederation", NULL, NULL}, 0xF7BD, 0xFFFF, 1}
};
