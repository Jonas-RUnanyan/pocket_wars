#ifndef DISPLAY_H
#define DISPLAY_H

#include <nds.h>

// 1. Move dimensions & color macros here
#define SCREEN_W     256
#define SCREEN_H     192
#define MAP_W        512
#define MAP_H        386

#undef RGB15
#define BGR15(r,g,b) (0x8000 | ((b) << 10) | ((g) << 5) | (r))

// 2. Move enum definition here so MapType is recognized
typedef enum {
    MAP_TERRAIN   = 0,
    MAP_POLITICAL = 1,
    MAP_TYPE_COUNT
} MapType;

// 3. Declare shared variables (NO initializers like = 0 here!)
extern int mapX;
extern int mapY;
extern int mapScale;

extern bool showPoliticalMap;
extern bool needsRedraw;
extern MapType currentMapType;

extern u16  lastProvinceID;
extern bool hasProvinceInfo;

// 4. Function Prototypes
void blitTerrainViewport();
void generatePoliticalMap();
void blitPoliticalViewport();
void cycleMapType(int direction);
void updateCamera(int keys, int pressed);

#endif // DISPLAY_H