#include "text_sprites.h"
#include "font_data.h"
#include <string.h>
#include <nds.h>

// ---------------------------------------------------------
// Hybrid text renderer.
//
// MAIN engine (bottom/touch screen): sprites, as before. Menu button
// labels + country name are short — nowhere near the 128-slot ceiling,
// so there's no reason to move this off sprites. Bank A is fully
// consumed by the BG3 map bitmap, and mapBase's hardware range (0-31,
// max 62KB offset) can only ever reach into Bank A anyway — so a BG
// tile layer genuinely isn't usable on this engine without tearing up
// the map bitmap. Sprites sidestep that entirely.
//
// SUB engine (top screen / province info): BG tile layer. Bank C is
// completely unused by anything else, so there's no VRAM conflict
// here. This is also where the actual budget problem was (info panel
// text was competing with flag/portrait sprites for the same 128
// OAM slots) — moving just this engine's text off sprites fixes that
// while leaving the bottom screen alone.
// ---------------------------------------------------------

#define MAX_TEXT_SPR 128

#define SUB_MAP_BASE  0   // tilemap: offset 0KB,  2KB used  (mapBase max reach is 62KB — fine)
#define SUB_TILE_BASE 1   // tile gfx: offset 16KB, ~1.5KB used — well clear of the map above

#define MAP_COLS 32
#define MAP_ROWS 32
#define VIS_ROWS 24
#define BG_CHAR_W 8       // sub-engine tiles are grid-locked to 8px, unlike sprite CHAR_W

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

static int findGlyphIndex(char c)
{
    if (c >= 'a' && c <= 'z') c -= 32;
    for (unsigned int i = 0; i < FONT_GLYPH_COUNT; i++)
        if (FONT_GLYPHS[i].c == c) return i;
    return 0;
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
    // static: DMA can't read a plain stack array — DTCM is invisible to it.
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

        ctx.mapPtr        = (u16*)bgGetMapPtr(ctx.bgId);
        u16* gfxPtr        = (u16*)bgGetGfxPtr(ctx.bgId);

        BG_PALETTE_SUB[0] = RGB15(0, 0, 0);
        BG_PALETTE_SUB[1] = RGB15(31, 31, 31);

        for (unsigned int g = 0; g < FONT_GLYPH_COUNT; g++)
        {
            buildGlyphTile(FONT_GLYPHS[g], tileBuf);

            u16* dst = gfxPtr + g * 16; // 16 halfwords = 32 bytes per 4bpp 8x8 tile
            dmaCopyHalfWords(3, tileBuf, dst, 32);
            while (dmaBusy(3)) ;

            ctx.tileIdx[g] = g;
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
    int len = strlen(str);

    if (engine == TEXT_ENGINE_MAIN)
    {
        for (int i = 0; i < len && ctx.cursor < MAX_TEXT_SPR; i++)
        {
            int glyphIdx = findGlyphIndex(str[i]);
            oamSet(ctx.oam, ctx.cursor, x, y, 0, 0, SpriteSize_8x8, SpriteColorFormat_16Color,
                   ctx.glyphGfx[glyphIdx], -1, false, false, false, false, false);
            x += CHAR_W;
            ctx.cursor++;
        }
    }
    else
    {
        int col = x / BG_CHAR_W;
        int row = y / BG_CHAR_W;
        if (row < 0 || row >= VIS_ROWS) return;

        for (int i = 0; i < len && col + i < MAP_COLS; i++)
        {
            int glyphIdx = findGlyphIndex(str[i]);
            ctx.mapPtr[row * MAP_COLS + (col + i)] = ctx.tileIdx[glyphIdx];
        }
    }
}

void commitText(TextEngine engine)
{
    if (engine == TEXT_ENGINE_MAIN)
        oamUpdate(ctxMain.oam);
    // SUB: no-op, drawText() already wrote straight to VRAM.
}

void debugDrawGlyph1()
{
    // Zoom-renders the 'A' tile from the SUB engine's BG tile storage
    // onto the MAIN engine's bitmap, same debug view as before.
    u16* vram      = (u16*)BG_BMP_RAM(0);
    u16* gfxPtr    = (u16*)bgGetGfxPtr(ctxSub.bgId);
    u8*  tileBytes = (u8*)(gfxPtr + 1 * 16);

    int scale = 10;
    for (int row = 0; row < 8; row++)
    {
        for (int col = 0; col < 8; col += 2)
        {
            u8 byteVal = tileBytes[row * 4 + col / 2];
            u8 px0 = byteVal & 0x0F;
            u8 px1 = (byteVal >> 4) & 0x0F;

            u16 color0 = px0 ? RGB15(31,31,31) : RGB15(0,0,0);
            u16 color1 = px1 ? RGB15(31,31,31) : RGB15(0,0,0);

            for (int dy = 0; dy < scale; dy++)
                for (int dx = 0; dx < scale; dx++)
                {
                    vram[(row*scale+dy)*256 + (col*scale+dx)]     = color0;
                    vram[(row*scale+dy)*256 + ((col+1)*scale+dx)] = color1;
                }
        }
    }
}