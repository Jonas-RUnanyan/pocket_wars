#ifndef MENU_H
#define MENU_H

#include <nds.h>
#include "text_sprites.h"

typedef enum {
    STATE_MAIN_MENU,
    STATE_COUNTRY_SELECT,
    STATE_GAME,
    STATE_DECISIONS,   // NEW
} GameScreenState;

typedef struct {
    int x, y, w, h;
    const char* label;
    bool enabled;
} MenuButton;

extern GameScreenState currentState;

extern MenuButton mainMenuButtons[3];
extern MenuButton countryNavButtons[2];
extern MenuButton countryConfirmButton;
extern PrintConsole* menuConsole;

void initMenuConsole();
void enterMenuState();
void enterCountrySelectState();
void enterGameState();

void updateMenu(int pressed);
void updateCountrySelect(int pressed);

void drawMenu();
void drawCountrySelect();
void drawButtonRect(int x, int y, int w, int h, bool selected, bool enabled);
void renderMenuBackground();

#endif