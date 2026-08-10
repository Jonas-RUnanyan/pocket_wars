#include <nds.h>
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include <malloc.h>
#include "splash.h"
#include "province_data.h"
#include "province_map.h"
#include "countries.h"
#include "province_owners.h"
#include "province_cores.h"
#include "turn_system.h"
#include "menu.h"
#include "text_sprites.h"
#include "sprites.h"
#include "flags.h"
#include "political_data.h"
#include "decisions.h"

#undef RGB15
#define BGR15(r,g,b) (0x8000 | ((b) << 10) | ((g) << 5) | (r))

static const int DMA_CHANNEL = 3;

#define SCREEN_W     256
#define SCREEN_H     192
#define MAP_W        512
#define MAP_H        386

// How many vblanks to skip between redraws while moving.
// 2 = render every 3rd frame (~20fps). Raise for faster feel, lower for smoother.
#define RENDER_SKIP  4

int mapX     = 0;
int mapY     = 0;
int mapScale = 256; // 8.8 fixed, 256 = 1:1

bool showPoliticalMap  = false;

static u16  politicalMapBuffer[SCREEN_W * SCREEN_H];
static bool politicalMapDirty  = true;
static bool politicalWasMoving = false;

static int  renderSkipCounter = 0;
bool needsRedraw       = true;

// Last touched province — persists on screen until next touch
static u16  lastProvinceID   = 0xFFFF;
static bool hasProvinceInfo  = false;

typedef enum {
    MAP_TERRAIN   = 0,
    MAP_POLITICAL = 1,
    MAP_TYPE_COUNT
} MapType;

MapType currentMapType = MAP_TERRAIN;

#define POPUP_LINE_H 12
#define POPUP_H      44   // two lines + padding
#define POPUP_MIN_W  70

static bool          countryPopupOpen  = false;
static int           popupX = 0, popupY = 0;
static int           popupBoxW = POPUP_MIN_W;
static unsigned char popupCountryId = 0xFF;
static char          popupLine1[24] = "";
static char          popupLine2[24] = "";

//---------------------------------------------
// HELPERS
//---------------------------------------------

//checks whether the province "province_id" is a core of the country "country_id"
bool is_core(unsigned short province_id, unsigned char country_id)
{
    for (int i = 0; i < PROVINCE_CORE_COUNT; i++)
        if (province_cores[i].province_id == province_id &&
            province_cores[i].country_id  == country_id)
            return true;
    return false;
}


int get_core_countries(unsigned short province_id, unsigned char* out, int max)
{
    int count = 0;
    for (int i = 0; i < PROVINCE_CORE_COUNT && count < max; i++)
        if (province_cores[i].province_id == province_id)
            out[count++] = province_cores[i].country_id;
    return count;
}

//---------------------------------------------
// VIDEO INIT
//---------------------------------------------

void initVideo()
{
    powerOn(POWER_ALL_2D);
    lcdMainOnBottom(); // Main Engine = Pantalla táctil (abajo), Sub Engine = Pantalla superior (arriba)

    // Configuración VRAM para ENGINE MAIN (Pantalla Táctil - Fondo Bitmap)
    vramSetBankA(VRAM_A_MAIN_BG_0x06000000); 
    vramSetBankB(VRAM_B_MAIN_BG_0x06060000); 

    // Configuración VRAM para ENGINE SUB (Pantalla Superior - Sprites de Texto)
    vramSetBankC(VRAM_C_SUB_BG);              
    vramSetBankD(VRAM_D_SUB_SPRITE);         // Banco D asignado a Sprites del MOTOR SUB
    vramSetBankE(VRAM_E_MAIN_SPRITE);        // NEW — Banco E asignado a Sprites del MOTOR MAIN (texto de menús/botones)

    // MODO MAIN (Abajo): Modo 5 Bitmap activo + Sprites activos (texto de menús/botones)
    videoSetMode(MODE_5_2D | DISPLAY_BG3_ACTIVE | DISPLAY_SPR_ACTIVE | DISPLAY_SPR_1D);

    REG_BG3CNT = BG_BMP16_256x256 | BG_BMP_BASE(0) | BG_PRIORITY(3);
    REG_BG3PA = 256;  REG_BG3PB = 0;
    REG_BG3PC = 0;    REG_BG3PD = 256;
    REG_BG3X  = 0;    REG_BG3Y  = 0;

    // MODO SUB (Arriba): Activar Sprites y mapeo 1D en el Motor Sub
    videoSetModeSub(MODE_5_2D | DISPLAY_BG0_ACTIVE);

    // Inicializar los sprites de la fuente en AMBOS motores
    initTextSprites(TEXT_ENGINE_MAIN);  // NEW — texto de botones/menús (pantalla táctil)
    initTextSprites(TEXT_ENGINE_SUB);   // texto de info de provincia (pantalla superior)
	initGameSprites(SPR_SUB);
	initFlags();
	
}

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
    const u16 unowned = BGR15(0, 1, 3);

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

//---------------------------------------------
// TOUCH
//---------------------------------------------

bool getTouchedProvince(u16* outID)
{
    if (!(keysDown() & KEY_TOUCH))
        return false;

    touchPosition touch;
    touchRead(&touch);

    int mapPX = mapX + ((touch.px * mapScale) >> 8);
    int mapPY = mapY + ((touch.py * mapScale) >> 8);

    if (mapPX < 0 || mapPX >= MAP_W ||
        mapPY < 0 || mapPY >= MAP_H)
        return false;

    *outID = provinceMap[mapPY * MAP_W + mapPX];
    return true;
}


void onCountryPopupInteract(unsigned char countryId)
{
    if (countryId == PLAYER_COUNTRY)
        enterDecisionsState();
    // else: diplomacy screen for other countries — not built yet
}

void handleCountryPopupTouch()
{
    if (!(keysDown() & KEY_TOUCH))
        return;

    touchPosition touch;
    touchRead(&touch);

    if (countryPopupOpen)
    {
        bool insideButton =
            touch.px >= popupX && touch.px < popupX + popupBoxW &&
            touch.py >= popupY && touch.py < popupY + POPUP_H;

        if (insideButton)
            onCountryPopupInteract(popupCountryId);

        countryPopupOpen = false;
        clearText(TEXT_ENGINE_MAIN);
        commitText(TEXT_ENGINE_MAIN);
        needsRedraw = true;
        return;
    }

    u16 pid;
    if (!getTouchedProvince(&pid) || provinces[pid].is_water)
        return;

    unsigned char oid = province_owners[pid];
    if (oid == 0xFF)
        return;

    lastProvinceID  = pid;
    hasProvinceInfo = true;

    popupCountryId = oid;

    if (oid == PLAYER_COUNTRY)
    {
        snprintf(popupLine1, sizeof(popupLine1), "INTERNAL");
        snprintf(popupLine2, sizeof(popupLine2), "POLITICS");
    }
    else
    {
        snprintf(popupLine1, sizeof(popupLine1), "DIPLO WITH:");
        snprintf(popupLine2, sizeof(popupLine2), "%s", countries[oid].name);
    }

    int w1 = textPixelWidth(popupLine1);
    int w2 = textPixelWidth(popupLine2);
    popupBoxW = (w1 > w2 ? w1 : w2) + 16;   // generous side padding, on purpose
    if (popupBoxW < POPUP_MIN_W)  popupBoxW = POPUP_MIN_W;
    if (popupBoxW > SCREEN_W - 4) popupBoxW = SCREEN_W - 4;

    popupX = touch.px;
    popupY = touch.py;
    if (popupX + popupBoxW > SCREEN_W) popupX = SCREEN_W - popupBoxW;
    if (popupY + POPUP_H   > SCREEN_H) popupY = SCREEN_H - POPUP_H;

    countryPopupOpen = true;
}

void drawCountryPopup()
{
    if (!countryPopupOpen) return;

    u16* vram  = (u16*)BG_BMP_RAM(0);
    u16 fill   = BGR15(9, 11, 15);
    u16 border = BGR15(20, 24, 31);

    for (int py = popupY; py < popupY + POPUP_H; py++)
        for (int px = popupX; px < popupX + popupBoxW; px++)
        {
            bool isBorder = (py == popupY || py == popupY + POPUP_H - 1 ||
                              px == popupX || px == popupX + popupBoxW - 1);
            vram[py * SCREEN_W + px] = isBorder ? border : fill;
        }

    clearText(TEXT_ENGINE_MAIN);
    drawText(TEXT_ENGINE_MAIN, popupX + 8, popupY + 6, popupLine1);
    drawText(TEXT_ENGINE_MAIN, popupX + 8, popupY + 6 + POPUP_LINE_H, popupLine2);
    commitText(TEXT_ENGINE_MAIN);
}


// Ideology enum order must match political_editor.py's IDEOLOGIES list exactly —
// it's what the generated Ideology enum in political_data.h is indexed against.
static const char* IDEOLOGY_NAMES[IDEOLOGY_COUNT] = {
    "FASCISM", "DEMOCRACY", "COMMUNISM", "AUTOCRACY"
};

// Name of whoever's actually ruling under a country's ruling ideology right now.
// Defensive bounds check: COUNTRY_POLITICS_COUNT could drift from COUNTRY_COUNT if
// political_editor.py's export gets out of sync with a later country_filler.py edit
// (e.g. someone adds a country and forgets to re-run the political tool) — checking
// against COUNTRY_POLITICS_COUNT specifically (the actual array size) rather than
// COUNTRY_COUNT avoids reading past the end of country_politics[] if that happens.
const char* get_ruling_leader_name(unsigned char country_id)
{
    if (country_id >= COUNTRY_POLITICS_COUNT) return "UNKNOWN";

    const CountryPolitics* pol = &country_politics_runtime[country_id];
    unsigned char leader_idx = pol->current_leader[pol->ruling_ideology];

    if (leader_idx == LEADER_NONE) return "NO LEADER";
    return leaders[leader_idx].name;
}

unsigned char get_ruling_ideology(unsigned char country_id)
{
    if (country_id >= COUNTRY_POLITICS_COUNT) return IDEOLOGY_AUTOCRACY; // arbitrary but consistent fallback
    return country_politics_runtime[country_id].ruling_ideology;
}

//---------------------------------------------
// SUB SCREEN — province info using Sprites
//---------------------------------------------

void printProvinceInfo(u16 pid)
{
    if (pid >= PROVINCE_COUNT) return;

    char buf[64];
    int curY = 8;

    snprintf(buf, sizeof(buf), "TURN: %s (%d)", countries[CURRENT_TURN.current_country].name, CURRENT_TURN.current_country);
    drawText(TEXT_ENGINE_SUB, 8, curY, buf);
    curY += 14;

    unsigned char oid = province_owners[pid];

    // --- Shown in BOTH views ---
    if (oid == 0xFF)
    {
        drawText(TEXT_ENGINE_SUB, 8, curY, "OWNER: NONE");
        hideFlag();
        curY += 14;
    }
    else
    {
        const Country* owner = &countries[oid];
        snprintf(buf, sizeof(buf), "OWNER: %s", owner->name);
        drawText(TEXT_ENGINE_SUB, 8, curY, buf);
        showFlag(oid, get_ruling_ideology(oid), 180, 8);
        curY += 14;
    }

    if (currentMapType == MAP_TERRAIN)
    {
        // --- Province view: name, id, cores ---
        drawText(TEXT_ENGINE_SUB, 8, curY, provinces[pid].name);
        curY += 10;

        snprintf(buf, sizeof(buf), "ID: %d", pid);
        drawText(TEXT_ENGINE_SUB, 8, curY, buf);
        curY += 12;

        if (oid != 0xFF)
        {
            drawText(TEXT_ENGINE_SUB, 8, curY, is_core(pid, oid) ? "(CORE)" : "(OCCUPIED)");
            curY += 12;
        }

        unsigned char cores[32];
        int n = get_core_countries(pid, cores, 32);
        if (n > 0)
        {
            drawText(TEXT_ENGINE_SUB, 8, curY, "CORES:");
            curY += 10;
            for (int i = 0; i < n && i < 4; i++)
            {
                const Country* c = &countries[cores[i]];
                snprintf(buf, sizeof(buf), " - %s", c->name);
                drawText(TEXT_ENGINE_SUB, 12, curY, buf);
                curY += 10;
            }
        }

        if (provinces[pid].is_water)
            drawText(TEXT_ENGINE_SUB, 8, curY, "[WATER]");
    }
    else // MAP_POLITICAL
    {
        // --- Country view: leader, stability, politics ---
        if (oid != 0xFF && oid < COUNTRY_POLITICS_COUNT)
        {
            const CountryPolitics* pol = &country_politics_runtime[oid]; 

            snprintf(buf, sizeof(buf), "IDEOLOGY: %s", IDEOLOGY_NAMES[pol->ruling_ideology]);
            drawText(TEXT_ENGINE_SUB, 8, curY, buf);
            curY += 10;

            snprintf(buf, sizeof(buf), "LEADER: %s", get_ruling_leader_name(oid));
            drawText(TEXT_ENGINE_SUB, 8, curY, buf);
            curY += 10;

            snprintf(buf, sizeof(buf), "STABILITY: %d%%", pol->stability);
            drawText(TEXT_ENGINE_SUB, 8, curY, buf);
            curY += 12;

            drawText(TEXT_ENGINE_SUB, 8, curY, "SUPPORT:");
            curY += 10;
            drawIdeologyBar(8, curY, 16, pol->ideology_support); // 16 tiles = 128px wide
        }
        else if (oid == 0xFF)
        {
            drawText(TEXT_ENGINE_SUB, 8, curY, "NO POLITICAL DATA");
        }
    }
}




//---------------------------------------------
// MAIN
//---------------------------------------------

int main(void)
{
    initVideo();
    initMenuConsole();
    enterMenuState();

    while (1)
    {
        swiWaitForVBlank();
        scanKeys();
        int keys    = keysHeld();
        int pressed = keysDown();

        switch (currentState)
        {
            case STATE_MAIN_MENU:
                updateMenu(pressed);
                break;

            case STATE_COUNTRY_SELECT:
                updateCountrySelect(pressed);
                break;

            case STATE_GAME:
                updateCamera(keys, pressed);

                if (CURRENT_TURN.awaiting_orders)
				{
					if (currentMapType == MAP_POLITICAL)
					{
						handleCountryPopupTouch();
					}
					else
					{
						u16 pid;
						if (getTouchedProvince(&pid))
						{
							lastProvinceID  = pid;
							hasProvinceInfo = true;
/*
							if (provinces[pid].is_water == 0)
							{
								province_owners[pid] = CURRENT_TURN.current_country;
								needsRedraw = true;
							}*/
						}
					}
				}

                pass_turn(pressed);

                if (needsRedraw)
                {
                    if (showPoliticalMap)
                        blitPoliticalViewport();
                    else
                        blitTerrainViewport();
                    needsRedraw = false;
                }
				drawCountryPopup();

                // Renderizar información utilizando tus Sprites (pantalla superior / motor SUB)
                clearText(TEXT_ENGINE_SUB);
                if (hasProvinceInfo)
                {
                    printProvinceInfo(lastProvinceID);
                }
                commitText(TEXT_ENGINE_SUB);
                break;
			case STATE_DECISIONS:
				updateDecisionsState(keys, pressed);   // was: updateDecisionsState(pressed)
				break;
        }
    }
}

