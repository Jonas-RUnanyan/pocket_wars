// flags.cpp
#include "flags.h"
#include "sprites.h"
#include <nds.h>

#include "flags_sheet0.h"   // grit output for the sheet you've built so far
#include "flags_sheet1.h"
#include "flags_sheet2.h"
#include "flags_sheet3.h"

#define COUNTRIES_PER_SHEET 8
#define CELL_W_TILES 8      // 64px / 8
#define CELL_H_TILES 4      // 32px / 8
#define SHEET_TILES_PER_ROW 32   // 256px sheet width / 8
#define TILE_BYTES 64             // 8bpp 8x8 tile

struct FlagSheet {
    const unsigned int*   tiles;
    const unsigned short* pal;
};

static const FlagSheet sheets[] = {
    { flags_sheet0Tiles, flags_sheet0SharedPal}, 
	{ flags_sheet1Tiles, flags_sheet1SharedPal},
	{ flags_sheet2Tiles, flags_sheet2SharedPal},
	{ flags_sheet3Tiles, flags_sheet3SharedPal},
    // { flags_sheet1Tiles, flags_sheet1Pal },  // append as sheets are finished
};
#define SHEET_COUNT (int)(sizeof(sheets) / sizeof(sheets[0]))

static u16* flagSlot      = nullptr;
static int  loadedSheet   = -1;
static int  loadedCountry = -1;

void initFlags()
{
    flagSlot = allocSpriteGfx(SPR_SUB, SpriteSize_64x32, SpriteColorFormat_256Color);
}

// A flag's 4 tile-rows aren't contiguous in the sheet's flat tile array —
// other cells' tiles sit between them — so pull it out one tile-row
// (512 bytes) at a time rather than one flat 2KB copy.
static void loadCell(const FlagSheet& sheet, int cellRow, int cellCol)
{
    const u8* base = (const u8*)sheet.tiles;
    int baseTileRow = cellRow * CELL_H_TILES;
    int baseTileCol = cellCol * CELL_W_TILES;

    for (int i = 0; i < CELL_H_TILES; i++)
    {
        int srcOffset = ((baseTileRow + i) * SHEET_TILES_PER_ROW + baseTileCol) * TILE_BYTES;
        u16* dst = flagSlot + (i * CELL_W_TILES * TILE_BYTES) / 2;

        dmaCopyHalfWords(3, base + srcOffset, dst, CELL_W_TILES * TILE_BYTES);
        while (dmaBusy(3)) ;
    }
}

void showFlag(int countryId, int x, int y)
{
    int sheetIdx = countryId / COUNTRIES_PER_SHEET;
    int rowIdx   = countryId % COUNTRIES_PER_SHEET;
    int colIdx   = 0; // base flag only — ideology variants plug in here later

    if (sheetIdx >= SHEET_COUNT) return; // not painted yet, show nothing

    if (sheetIdx != loadedSheet || rowIdx != loadedCountry)
    {
        const FlagSheet& sheet = sheets[sheetIdx];

        if (sheetIdx != loadedSheet)
        {
            dmaCopyHalfWords(3, sheet.pal, SPRITE_PALETTE_SUB, 256 * 2);
            while (dmaBusy(3)) ;
        }

        loadCell(sheet, rowIdx, colIdx);
        loadedSheet   = sheetIdx;
        loadedCountry = rowIdx;
    }

    setSprite(SPR_SUB, 0, x, y, SpriteSize_64x32, SpriteColorFormat_256Color, flagSlot);
    commitSprites(SPR_SUB);
}

void hideFlag()
{
    hideSprite(SPR_SUB, 0);
    commitSprites(SPR_SUB);
}