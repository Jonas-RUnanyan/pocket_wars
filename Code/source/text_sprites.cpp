#include "text_sprites.h"
#include "font_data.h"
#include <string.h>
#include <nds.h>

#define MAX_TEXT_SPR 128

#define SUB_MAP_BASE  0   
#define SUB_TILE_BASE 1   

#define MAP_COLS 32
#define MAP_ROWS 32
#define VIS_ROWS 24
#define BG_CHAR_W 8   
#define BAR_TILE_BASE     FONT_GLYPH_COUNT  // 4 solid-color tiles placed right after the font glyphs
#define BAR_PAL_FASCISM   2
#define BAR_PAL_DEMOCRACY 3
#define BAR_PAL_COMMUNISM 4
#define BAR_PAL_AUTOCRACY 5

struct TextCtx {
    // --- main engine (sprites) ---
    OamState* oam;
    int       cursor;
    u16*      glyphGfx[FONT_GLYPH_COUNT];

    // --- sub engine (BG tiles) ---
    int  bgId;
    u16* mapPtr;
    u16  tileIdx[FONT_GLYPH_COUNT];
};

static TextCtx ctxMain;
static TextCtx ctxSub;

static TextCtx& ctxFor(TextEngine e) { return e == TEXT_ENGINE_MAIN ? ctxMain : ctxSub; }

// Decodes a single UTF-8 codepoint from a byte stream and advances the pointer
static char16_t decodeUtf8(const char** str)
{
    const u8* p = (const u8*)*str;
    if (!*p) return 0;

    char16_t code = 0;
    if ((*p & 0x80) == 0) {
        code = *p++;
    } else if ((*p & 0xE0) == 0xC0) {
        code = (*p++ & 0x1F) << 6;
        if (*p) code |= (*p++ & 0x3F);
    } else if ((*p & 0xF0) == 0xE0) {
        code = (*p++ & 0x0F) << 12;
        if (*p) code |= (*p++ & 0x3F) << 6;
        if (*p) code |= (*p++ & 0x3F);
    } else {
        p++; // Fallback for unsupported sequences
    }

    *str = (const char*)p;
    return code;
}

// Updated to accept char16_t; removed automatic lowercase transformation ('c -= 32')
static int findGlyphIndex(char16_t c)
{
    for (unsigned int i = 0; i < FONT_GLYPH_COUNT; i++)
        if (FONT_GLYPHS[i].c == c) return i;
    return 0; // Default to space/first glyph if not found
}

static void buildSolidTile(u8 paletteIndex, u8* out)
{
    u8 packed = paletteIndex | (paletteIndex << 4); // same index in both nibbles — whole tile one flat color
    for (int i = 0; i < 32; i++)
        out[i] = packed;
}

static void buildGlyphTile(const Glyph& g, u8* out)
{
    for (int row = 0; row < 8; row++)
    {
        u8 bits = g.rows[row];
        for (int col = 0; col < 8; col += 2)
        {
            u8 px0 = (bits & (0x80 >> col))     ? 1 : 0;
            u8 px1 = (bits & (0x80 >> (col+1))) ? 1 : 0;
            out[row * 4 + col / 2] = px0 | (px1 << 4);
        }
    }
}

void initTextSprites(TextEngine engine)
{
    static u8 tileBuf[32];

    if (engine == TEXT_ENGINE_MAIN)
    {
        TextCtx& ctx = ctxMain;
        ctx.oam    = &oamMain;
        ctx.cursor = 0;

        oamInit(ctx.oam, SpriteMapping_1D_32, false);

        SPRITE_PALETTE[0] = RGB15(0, 0, 0);
        SPRITE_PALETTE[1] = RGB15(31, 31, 31);

        for (unsigned int g = 0; g < FONT_GLYPH_COUNT; g++)
        {
            u16* gfx = oamAllocateGfx(ctx.oam, SpriteSize_8x8, SpriteColorFormat_16Color);
            ctx.glyphGfx[g] = gfx;

            buildGlyphTile(FONT_GLYPHS[g], tileBuf);
            dmaCopyHalfWords(3, tileBuf, gfx, 32);
            while (dmaBusy(3)) ;
        }
    }
    else // TEXT_ENGINE_SUB
    {
        TextCtx& ctx = ctxSub;

        ctx.bgId = bgInitSub(0, BgType_Text4bpp, BgSize_T_256x256, SUB_MAP_BASE, SUB_TILE_BASE);
bgSetScroll(ctx.bgId, 0, 0);
bgUpdate();

        ctx.mapPtr        = (u16*)bgGetMapPtr(ctx.bgId);
        u16* gfxPtr       = (u16*)bgGetGfxPtr(ctx.bgId);

        BG_PALETTE_SUB[0] = RGB15(0, 0, 0);
        BG_PALETTE_SUB[1] = RGB15(31, 31, 31);

        for (unsigned int g = 0; g < FONT_GLYPH_COUNT; g++)
        {
            buildGlyphTile(FONT_GLYPHS[g], tileBuf);

            u16* dst = gfxPtr + g * 16;
            dmaCopyHalfWords(3, tileBuf, dst, 32);
            while (dmaBusy(3)) ;

            ctx.tileIdx[g] = g;
        }
		
		// 4 solid-color tiles for the ideology bar — same tile/palette pipeline
        // as the font glyphs, just past the end of the glyph range. BG_PALETTE_SUB
        // is separate from SPRITE_PALETTE_SUB (which flags use), so no conflict.
        BG_PALETTE_SUB[BAR_PAL_FASCISM]   = RGB15(14, 9, 3);   // brown
        BG_PALETTE_SUB[BAR_PAL_DEMOCRACY] = RGB15(6, 10, 28);  // blue
        BG_PALETTE_SUB[BAR_PAL_COMMUNISM] = RGB15(28, 6, 6);   // red
        BG_PALETTE_SUB[BAR_PAL_AUTOCRACY] = RGB15(16, 16, 16); // grey

		const u8 barPalettes[4] = { BAR_PAL_FASCISM, BAR_PAL_DEMOCRACY, BAR_PAL_COMMUNISM, BAR_PAL_AUTOCRACY };
		for (int i = 0; i < 4; i++)
		{
			buildSolidTile(barPalettes[i], tileBuf);   // reuse the existing static tileBuf, not barTileBuf
			u16* dst = gfxPtr + (BAR_TILE_BASE + i) * 16;
			dmaCopyHalfWords(3, tileBuf, dst, 32);
			while (dmaBusy(3)) ;
		}

        for (int i = 0; i < MAP_COLS * MAP_ROWS; i++)
            ctx.mapPtr[i] = 0;
    }
}

void clearText(TextEngine engine)
{
    TextCtx& ctx = ctxFor(engine);

    if (engine == TEXT_ENGINE_MAIN)
    {
        for (int i = 0; i < ctx.cursor; i++)
            oamClearSprite(ctx.oam, i);
        ctx.cursor = 0;
    }
    else
    {
        for (int i = 0; i < MAP_COLS * MAP_ROWS; i++)
            ctx.mapPtr[i] = 0;
    }
}

void drawText(TextEngine engine, int x, int y, const char* str)
{
    TextCtx& ctx = ctxFor(engine);

    if (engine == TEXT_ENGINE_MAIN)
    {
        const char* ptr = str;
        while (*ptr && ctx.cursor < MAX_TEXT_SPR)
        {
            char16_t code = decodeUtf8(&ptr);
            int glyphIdx = findGlyphIndex(code);

            oamSet(ctx.oam, ctx.cursor, x, y, 0, 0, SpriteSize_8x8, SpriteColorFormat_16Color,
                   ctx.glyphGfx[glyphIdx], -1, false, false, false, false, false);
            x += FONT_GLYPHS[glyphIdx].width;
            ctx.cursor++;
        }
    }
    else
    {
        int col = x / BG_CHAR_W;
        int row = y / BG_CHAR_W;
        if (row < 0 || row >= VIS_ROWS) return;

        const char* ptr = str;
        int offset = 0;
        while (*ptr && (col + offset) < MAP_COLS)
        {
            char16_t code = decodeUtf8(&ptr);
            int glyphIdx = findGlyphIndex(code);

            ctx.mapPtr[row * MAP_COLS + (col + offset)] = ctx.tileIdx[glyphIdx];
            offset++;
        }
    }
}

void commitText(TextEngine engine)
{
    if (engine == TEXT_ENGINE_MAIN)
        oamUpdate(ctxMain.oam);
}

int textPixelWidth(const char* s)
{
    int len = strlen(s);
    if (len == 0) return 0;
    return (len - 1) * CHAR_W + 8;
}

void drawIdeologyBar(int x, int y, int widthTiles, const unsigned char support[4])
{
    int col = x / BG_CHAR_W;
    int row = y / BG_CHAR_W;
    if (row < 0 || row >= VIS_ROWS) return;
    if (widthTiles <= 0) return;
    if (widthTiles > MAP_COLS) widthTiles = MAP_COLS;

    int total = support[0] + support[1] + support[2] + support[3];
    if (total <= 0) total = 1; // guard against bad/empty data

    // Largest-remainder rounding — 4 independently-rounded percentages could
    // overshoot or undershoot widthTiles; this guarantees they sum to it exactly.
    int tiles[4], remainder[4], assigned = 0;
    for (int i = 0; i < 4; i++)
    {
        int scaled   = support[i] * widthTiles;
        tiles[i]     = scaled / total;
        remainder[i] = scaled % total;
        assigned    += tiles[i];
    }
    while (assigned < widthTiles)
    {
        int best = 0;
        for (int i = 1; i < 4; i++)
            if (remainder[i] > remainder[best]) best = i;
        tiles[best]++;
        remainder[best] = -1;
        assigned++;
    }

    int c = col;
    for (int i = 0; i < 4; i++)
        for (int t = 0; t < tiles[i] && c < MAP_COLS; t++, c++)
            ctxSub.mapPtr[row * MAP_COLS + c] = BAR_TILE_BASE + i;
}

void debugPokeTile(int row, int col, int tileIndex)
{
    ctxSub.mapPtr[row * MAP_COLS + col] = tileIndex;
}

int debugReadTile(int row, int col)
{
    return ctxSub.mapPtr[row * MAP_COLS + col];
}

int debugReadTileByte(int tileIndex, int byteOffset)
{
    u8* gfxPtr = (u8*)bgGetGfxPtr(ctxSub.bgId);
    return gfxPtr[tileIndex * 32 + byteOffset];
}