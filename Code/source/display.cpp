#include <nds.h>
#include "display.h"
#include "province_map.h"
#include "province_owners.h"
#include "countries.h"
#include "splash.h"


// How many vblanks to skip between redraws while moving.
// 2 = render every 3rd frame (~20fps). Raise for faster feel, lower for smoother.
#define RENDER_SKIP  4

static const int DMA_CHANNEL = 3;



int mapX     = 0;
int mapY     = 0;
int mapScale = 256; // 8.8 fixed, 256 = 1:1

bool showPoliticalMap  = false;

bool needsRedraw       = true;
MapType currentMapType = MAP_TERRAIN;

u16  lastProvinceID   = 0xFFFF; bool hasProvinceInfo  = false;

u16  politicalMapBuffer[SCREEN_W * SCREEN_H];
bool politicalMapDirty  = true;
bool politicalWasMoving = false;

static int  renderSkipCounter = 0;





//---------------------------------------------
// TERRAIN VIEWPORT BLIT
//---------------------------------------------

void blitTerrainViewport()
{
    u16*       vram = (u16*)BG_BMP_RAM(0);
    const u16* src  = (const u16*)splashBitmap;

    int stepX     = mapScale;
    int stepY     = mapScale;
    int startMapX = mapX << 8;
    int fixedMapY = mapY << 8;

    for (int sy = 0; sy < SCREEN_H; sy++)
    {
        int mapPY = fixedMapY >> 8;

        if (mapPY < 0 || mapPY >= MAP_H)
        {
            memset(vram + sy * SCREEN_W, 0, SCREEN_W * 2);
            fixedMapY += stepY;
            continue;
        }

        // Fast path: 1:1 scale and full row in bounds — one DMA per row
        if (mapScale == 256 && mapX >= 0 && mapX + SCREEN_W <= MAP_W)
        {
            dmaCopyHalfWords(DMA_CHANNEL,
                src + mapPY * MAP_W + mapX,
                vram + sy * SCREEN_W,
                SCREEN_W * 2);
        }
        else
        {
            int   fixedMapX = startMapX;
            u16*  dst_row   = vram + sy * SCREEN_W;

            for (int sx = 0; sx < SCREEN_W; sx++)
            {
                int mapPX = fixedMapX >> 8;
                dst_row[sx] = (mapPX >= 0 && mapPX < MAP_W)
                    ? src[mapPY * MAP_W + mapPX]
                    : (u16)0x8000;
                fixedMapX += stepX;
            }
        }

        fixedMapY += stepY;
    }
}

//---------------------------------------------
// POLITICAL MAP — generate into RAM buffer, blit when ready
//---------------------------------------------

void generatePoliticalMap()
{
    int stepX     = mapScale;
    int stepY     = mapScale;
    int startMapX = mapX << 8;
    int fixedMapY = mapY << 8;

    for (int sy = 0; sy < SCREEN_H; sy++)
    {
        int  mapPY    = fixedMapY >> 8;
        int  fixedMapX = startMapX;
        u16* dst_row  = politicalMapBuffer + sy * SCREEN_W;

        for (int sx = 0; sx < SCREEN_W; sx++)
        {
            int  mapPX = fixedMapX >> 8;
            u16  color = 0x8000;

            if (mapPX >= 0 && mapPX < MAP_W &&
                mapPY >= 0 && mapPY < MAP_H)
            {
                u16 pid = provinceMap[mapPY * MAP_W + mapPX];

                if (pid < PROVINCE_OWNER_COUNT)
                {
                    unsigned char oid = province_owners[pid];
                    if (oid == 0xFF)
                    {
                        color = BGR15(0, 8 + (mapPX + (mapPY*7)%5) % 16 / 4, 20 + (mapPX + (mapPY*13)%7) % 16 / 2);
                    }
                    else
                    {
                        const Country* c = &countries[oid];
                        color = c ? c->color : BGR15(0, 8 + (mapPX + (mapPY*7)%5) % 16 / 4, 20 + (mapPX + (mapPY*13)%7) % 16 / 2);
                    }
                }
                else
                {
                    color = BGR15(0, 8 + (mapPX + (mapPY*7)%5) % 16 / 4, 20 + (mapPX + (mapPY*13)%7) % 16 / 2);
                }
            }

            dst_row[sx]  = color;
            fixedMapX   += stepX;
        }

        fixedMapY += stepY;
    }

    politicalMapDirty = false;
}

void blitPoliticalViewport()
{
    if (politicalMapDirty)
        generatePoliticalMap();

    dmaCopyHalfWords(DMA_CHANNEL,
        politicalMapBuffer,
        (u16*)BG_BMP_RAM(0),
        SCREEN_W * SCREEN_H * 2);
}

//---------------------------------------------
// TOGGLE MAP MODE
//---------------------------------------------

void cycleMapType(int direction)
{
    currentMapType     = (MapType)(((int)currentMapType + direction + MAP_TYPE_COUNT) % MAP_TYPE_COUNT);
    showPoliticalMap   = (currentMapType == MAP_POLITICAL);  // keeps existing blit logic elsewhere unchanged
    politicalMapDirty  = true;
    needsRedraw        = true;
}

//---------------------------------------------
// CAMERA + FRAME SKIP
//---------------------------------------------

void updateCamera(int keys, int pressed)
{

    if (pressed & KEY_L) cycleMapType(-1);
	if (pressed & KEY_R) cycleMapType(+1);

    bool moved = false;

    int panSpeed = (mapScale >> 8);
    if (panSpeed < 1) panSpeed = 1;

    if (keys & KEY_LEFT)  { mapX -= panSpeed; moved = true; }
    if (keys & KEY_RIGHT) { mapX += panSpeed; moved = true; }
    if (keys & KEY_UP)    { mapY -= panSpeed; moved = true; }
    if (keys & KEY_DOWN)  { mapY += panSpeed; moved = true; }
    if (keys & KEY_A)     { mapScale -= 4;    moved = true; }
    if (keys & KEY_B)     { mapScale += 4;    moved = true; }

    if (mapScale < 64)   mapScale = 64;
    if (mapScale > 1024) mapScale = 1024;

    // Clamp to map bounds
    if (mapX < 0) mapX = 0;
    if (mapY < 0) mapY = 0;
    int visW = (SCREEN_W * mapScale) >> 8;
    int visH = (SCREEN_H * mapScale) >> 8;
    if (visW > MAP_W) visW = MAP_W;
    if (visH > MAP_H) visH = MAP_H;
    if (mapX + visW > MAP_W) mapX = MAP_W - visW;
    if (mapY + visH > MAP_H) mapY = MAP_H - visH;

    if (moved)
    {
        renderSkipCounter++;
        if (renderSkipCounter > RENDER_SKIP)
        {
            renderSkipCounter = 0;
            needsRedraw       = true;
            if (showPoliticalMap)
                politicalMapDirty = true;
        }
    }
    else
    {
        // Camera just stopped — force one final clean redraw
        if (politicalWasMoving)
        {
            politicalMapDirty = true;
            needsRedraw       = true;
        }
        renderSkipCounter = 0;
    }

    politicalWasMoving = moved;
}