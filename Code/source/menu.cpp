#include "menu.h"
#include "turn_system.h"
#include "countries.h"
#include "text_sprites.h"
#include "political_data.h"
#include "country_display.h"
#include "decisions.h"
#include <stdio.h>
#include <string.h>

#define SCREEN_W 256
#define SCREEN_H 192
#define CHAR_W 8
#undef RGB15
#define BGR15(r,g,b) (0x8000 | ((b) << 10) | ((g) << 5) | (r))

extern bool needsRedraw;  // from main.cpp

GameScreenState currentState = STATE_MAIN_MENU;

int  menuCursor = 0;
bool menuDirty  = true;

int  selectedCountryIdx = 0;
bool countrySelectDirty = true;

PrintConsole* menuConsole;

MenuButton mainMenuButtons[3] = {
    { 48,  50, 160, 28, "New Game", true  },
    { 48,  86, 160, 28, "Continue", false },
    { 48, 122, 160, 28, "Options",  false },
};

MenuButton countryNavButtons[2] = {
    { 20,  90, 40, 40, "<", true },
    { 196, 90, 40, 40, ">", true },
};

MenuButton countryConfirmButton = { 88, 140, 80, 28, "Select", true };

//---------------------------------------------
// CONSOLE INIT — BG0, main engine, Bank B, layered over BG3 bitmap in Bank A
//---------------------------------------------

void initMenuConsole()
{
    menuConsole = consoleInit(NULL, 0, BgType_Text4bpp, BgSize_T_256x256,
                               74, 8, true, true);
}

//---------------------------------------------
// PROCEDURAL BACKGROUND
//---------------------------------------------

void renderMenuBackground()
{
    u16* vram = (u16*)BG_BMP_RAM(0);

    for (int y = 0; y < SCREEN_H; y++)
    {
        u8  shade = 4 + (y * 10) / SCREEN_H;
        u16 color = BGR15(shade, shade, shade + 6);

        for (int x = 0; x < SCREEN_W; x++)
            vram[y * SCREEN_W + x] = color;
    }
}

//---------------------------------------------
// BUTTON DRAWING
//---------------------------------------------

void drawButtonRect(int x, int y, int w, int h, bool selected, bool enabled)
{
    u16* vram = (u16*)BG_BMP_RAM(0);

    u16 fill   = !enabled ? BGR15(6, 6, 6)
               : selected ? BGR15(12, 16, 22)
                           : BGR15(9, 11, 15);
    u16 border = !enabled ? BGR15(9, 9, 9)
               : selected ? BGR15(20, 24, 31)
                           : BGR15(14, 14, 18);

    for (int py = y; py < y + h; py++)
    {
        for (int px = x; px < x + w; px++)
        {
            bool isBorder = (py == y || py == y + h - 1 || px == x || px == x + w - 1);
            vram[py * SCREEN_W + px] = isBorder ? border : fill;
        }
    }
}

//---------------------------------------------
// STATE TRANSITIONS
//---------------------------------------------

void enterMenuState()
{
    currentState = STATE_MAIN_MENU;
    menuCursor   = 0;
    menuDirty    = true;
    videoSetMode(MODE_5_2D | DISPLAY_BG0_ACTIVE | DISPLAY_BG3_ACTIVE | DISPLAY_SPR_ACTIVE);
}
void enterCountrySelectState()
{
    currentState       = STATE_COUNTRY_SELECT;
    selectedCountryIdx  = 0;
    countrySelectDirty  = true;
    videoSetMode(MODE_5_2D | DISPLAY_BG0_ACTIVE | DISPLAY_BG3_ACTIVE | DISPLAY_SPR_ACTIVE);
}

void enterGameState()
{
    currentState = STATE_GAME;
    videoSetMode(MODE_5_2D | DISPLAY_BG3_ACTIVE | DISPLAY_SPR_ACTIVE | DISPLAY_SPR_1D);
    clearText(TEXT_ENGINE_MAIN);
    commitText(TEXT_ENGINE_MAIN);
    init_turn_system();
	initDecisionsSystem();
    needsRedraw = true;
}

//---------------------------------------------
// MAIN MENU
//---------------------------------------------

void drawMenu()
{
    renderMenuBackground();

    for (int i = 0; i < 3; i++)
    {
        MenuButton* b = &mainMenuButtons[i];
        drawButtonRect(b->x, b->y, b->w, b->h, i == menuCursor, b->enabled);
    }

    clearText(TEXT_ENGINE_MAIN);

    drawText(TEXT_ENGINE_MAIN, 70, 20, "POCKET WARS");

    for (int i = 0; i < 3; i++)
    {
        MenuButton* b = &mainMenuButtons[i];
        char label[24];
        strcpy(label, b->label);
        if (!b->enabled) strcat(label, " WIP");

        drawText(TEXT_ENGINE_MAIN, b->x + 20, b->y + (b->h / 2) - 4, label);
    }

    commitText(TEXT_ENGINE_MAIN);
    menuDirty = false;
}

void updateMenu(int pressed)
{
    int prevCursor = menuCursor;

    if (pressed & KEY_UP)   menuCursor = (menuCursor + 2) % 3;
    if (pressed & KEY_DOWN) menuCursor = (menuCursor + 1) % 3;

    if (menuCursor != prevCursor)
        menuDirty = true;

    bool confirm = (pressed & KEY_A);

    if (pressed & KEY_TOUCH)
    {
        touchPosition touch;
        touchRead(&touch);

        for (int i = 0; i < 3; i++)
        {
            MenuButton* b = &mainMenuButtons[i];
            if (touch.px >= b->x && touch.px < b->x + b->w &&
                touch.py >= b->y && touch.py < b->y + b->h)
            {
                menuCursor = i;
                confirm = true;
                menuDirty = true;
            }
        }
    }

    if (confirm && mainMenuButtons[menuCursor].enabled)
    {
        if (menuCursor == 0)
            enterCountrySelectState();
    }

    if (menuDirty)
        drawMenu();
}

//---------------------------------------------
// COUNTRY SELECT
//---------------------------------------------

void drawCountrySelect()
{
    renderMenuBackground();

    drawButtonRect(countryNavButtons[0].x, countryNavButtons[0].y,
                   countryNavButtons[0].w, countryNavButtons[0].h, false, true);
    drawButtonRect(countryNavButtons[1].x, countryNavButtons[1].y,
                   countryNavButtons[1].w, countryNavButtons[1].h, false, true);
    drawButtonRect(countryConfirmButton.x, countryConfirmButton.y,
                   countryConfirmButton.w, countryConfirmButton.h, false, true);

    clearText(TEXT_ENGINE_MAIN);

    drawText(TEXT_ENGINE_MAIN, 50, 15, "SELECT COUNTRY");
    drawText(TEXT_ENGINE_MAIN, 196, 105, ">");
    drawText(TEXT_ENGINE_MAIN, 36, 105, "<");

    int nameLen = strlen(getCountryDisplayName(selectedCountryIdx, country_politics[selectedCountryIdx].ruling_ideology));
    int nameX = 128 - (nameLen * CHAR_W) / 2;
    drawText(TEXT_ENGINE_MAIN, nameX, 105, getCountryDisplayName(selectedCountryIdx, country_politics[selectedCountryIdx].ruling_ideology));

    drawText(TEXT_ENGINE_MAIN, countryConfirmButton.x + 12, countryConfirmButton.y + 10, "SELECT");

    commitText(TEXT_ENGINE_MAIN);
    countrySelectDirty = false;
}

static int nextSelectableCountry(int start, int direction)
{
    int idx = start;
    for (int i = 0; i < COUNTRY_COUNT; i++)
    {
        idx = (idx + direction + COUNTRY_COUNT) % COUNTRY_COUNT;
        if (!countries[idx].is_formable) return idx;
    }
    return start;
}

void updateCountrySelect(int pressed)
{
    int prevIdx = selectedCountryIdx;
    bool confirm = false;

    if (pressed & KEY_LEFT)
        selectedCountryIdx = nextSelectableCountry(selectedCountryIdx, -1);
    if (pressed & KEY_RIGHT)
        selectedCountryIdx = nextSelectableCountry(selectedCountryIdx, +1);
    if (pressed & KEY_A)
        confirm = true;
    if (pressed & KEY_B)
    {
        enterMenuState();
        return;
    }

    if (pressed & KEY_TOUCH)
    {
        touchPosition touch;
        touchRead(&touch);

        MenuButton* left  = &countryNavButtons[0];
        MenuButton* right = &countryNavButtons[1];

        if (touch.px >= left->x && touch.px < left->x + left->w &&
            touch.py >= left->y && touch.py < left->y + left->h)
        {
            selectedCountryIdx = nextSelectableCountry(selectedCountryIdx, -1);
        }
        else if (touch.px >= right->x && touch.px < right->x + right->w &&
                 touch.py >= right->y && touch.py < right->y + right->h)
        {
            selectedCountryIdx = nextSelectableCountry(selectedCountryIdx, +1);
        }
        else if (touch.px >= countryConfirmButton.x && touch.px < countryConfirmButton.x + countryConfirmButton.w &&
                 touch.py >= countryConfirmButton.y && touch.py < countryConfirmButton.y + countryConfirmButton.h)
        {
            confirm = true;
        }
    }

    if (selectedCountryIdx != prevIdx)
        countrySelectDirty = true;

    if (confirm)
    {
        PLAYER_COUNTRY = selectedCountryIdx;
        enterGameState();
        return;
    }

    if (countrySelectDirty)
        drawCountrySelect();
}