#ifndef TEXT_SPRITES_H
#define TEXT_SPRITES_H

#include <nds.h>

enum TextEngine { TEXT_ENGINE_MAIN, TEXT_ENGINE_SUB };

void initTextSprites(TextEngine engine);
void clearText(TextEngine engine);
void drawText(TextEngine engine, int x, int y, const char* str);
void commitText(TextEngine engine);
int textPixelWidth(const char* s);
// Draws a small horizontal bar, widthTiles tiles wide (widthTiles*8 px), 1 tile
// tall, split into 4 proportional colored segments. SUB ENGINE ONLY — built from
// the same BG-tile infrastructure as sub-engine text, not available on the
// sprite-based main engine. `support` must be 4 values in the same order as
// political_data.h's Ideology enum: [FASCISM, DEMOCRACY, COMMUNISM, AUTOCRACY].
void drawIdeologyBar(int x, int y, int widthTiles, const unsigned char support[4]);
void debugPokeTile(int row, int col, int tileIndex);
int debugReadTile(int row, int col);
int debugReadTileByte(int tileIndex, int byteOffset);
#endif