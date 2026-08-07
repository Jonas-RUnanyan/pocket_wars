#include "text_sprites.h"
#include "font_data.h"
#include <string.h>
#include <nds.h> 

#define MAX_TEXT_SPR 128

struct TextCtx {
    OamState* oam;
    int       cursor;
    u16*      glyphGfx[FONT_GLYPH_COUNT];
};

static TextCtx ctxMain;
static TextCtx ctxSub;

static TextCtx& ctxFor(TextEngine e) { return e == TEXT_ENGINE_MAIN ? ctxMain : ctxSub; }
bool DEBUG_glyphAllocOK = true;
struct { u32 marker; u8 tile[32]; } DEBUG_block = { 0xDEADBEEF, {0} };
static int findGlyphIndex(char c)
{
    if (c >= 'a' && c <= 'z') c -= 32;
    for (unsigned int i = 0; i < FONT_GLYPH_COUNT; i++)
        if (FONT_GLYPHS[i].c == c) return i;
    return 0;
}
static u8 tileBuf[32];
void initTextSprites(TextEngine engine)
{
    TextCtx& ctx = ctxFor(engine);
    ctx.oam    = (engine == TEXT_ENGINE_MAIN) ? &oamMain : &oamSub;
    ctx.cursor = 0;

    oamInit(ctx.oam, SpriteMapping_1D_32, false);

    u16* palette = (engine == TEXT_ENGINE_MAIN) ? SPRITE_PALETTE : SPRITE_PALETTE_SUB;
    palette[0] = RGB15(0, 0, 0);
    palette[1] = RGB15(31, 31, 31);

    for (unsigned int g = 0; g < FONT_GLYPH_COUNT; g++)
    {
        u16* gfx = oamAllocateGfx(ctx.oam, SpriteSize_8x8, SpriteColorFormat_16Color);
		if (gfx == NULL) DEBUG_glyphAllocOK = false;   // NEW
		ctx.glyphGfx[g] = gfx;

         // build in RAM first — VRAM doesn't support 8-bit writes safely
        for (int row = 0; row < 8; row++)
        {
            u8 bits = FONT_GLYPHS[g].rows[row];
            for (int col = 0; col < 8; col += 2)
            {
                u8 px0 = (bits & (0x80 >> col))     ? 1 : 0;
                u8 px1 = (bits & (0x80 >> (col+1))) ? 1 : 0;
                tileBuf[row * 4 + col / 2] = px0 | (px1 << 4);
            }
        }
        dmaCopyHalfWords(3, tileBuf, gfx, 32);
    }
}

void clearText(TextEngine engine)
{
    TextCtx& ctx = ctxFor(engine);
    for (int i = 0; i < ctx.cursor; i++)
        oamClearSprite(ctx.oam, i);
    ctx.cursor = 0;
}

void drawText(TextEngine engine, int x, int y, const char* str)
{
    TextCtx& ctx = ctxFor(engine);
    int len = strlen(str);

    for (int i = 0; i < len && ctx.cursor < MAX_TEXT_SPR; i++)
    {
        int glyphIdx = findGlyphIndex(str[i]);

        oamSet(ctx.oam, ctx.cursor, x, y, 0, 0, SpriteSize_8x8, SpriteColorFormat_16Color,
               ctx.glyphGfx[glyphIdx], -1, false, false, false, false, false);

        x += CHAR_W;
        ctx.cursor++;
    }
}

void commitText(TextEngine engine)
{
    TextCtx& ctx = ctxFor(engine);
    oamUpdate(ctx.oam);
}

void debugDrawGlyph1()
{
    u16* vram = (u16*)BG_BMP_RAM(0);
    u8*  tileBytes = (u8*)ctxSub.glyphGfx[1]; // read back the 'A' tile from VRAM
	
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
	memcpy(DEBUG_block.tile, ctxSub.glyphGfx[1], 32);
}