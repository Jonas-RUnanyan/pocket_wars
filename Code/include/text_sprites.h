#ifndef TEXT_SPRITES_H
#define TEXT_SPRITES_H

#include <nds.h>
#define CHAR_W 6

enum TextEngine { TEXT_ENGINE_MAIN, TEXT_ENGINE_SUB };

void initTextSprites(TextEngine engine);
void clearText(TextEngine engine);
void drawText(TextEngine engine, int x, int y, const char* str);
void commitText(TextEngine engine);
void debugDrawGlyph1();
#endif