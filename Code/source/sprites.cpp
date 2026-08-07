// sprites.cpp
#include "sprites.h"

static OamState* oamFor(SpriteScreen s) { return s == SPR_MAIN ? &oamMain : &oamSub; }

void initGameSprites(SpriteScreen screen)
{
    oamInit(oamFor(screen), SpriteMapping_1D_32, false);
}

u16* allocSpriteGfx(SpriteScreen screen, SpriteSize size, SpriteColorFormat format)
{
    return oamAllocateGfx(oamFor(screen), size, format);
}

void setSprite(SpriteScreen screen, int oamId, int x, int y,
               SpriteSize size, SpriteColorFormat format, const void* gfx)
{
    oamSet(oamFor(screen), oamId, x, y, 0, -1, size, format,
           gfx, -1, false, false, false, false, false);
}

void hideSprite(SpriteScreen screen, int oamId)
{
    oamClearSprite(oamFor(screen), oamId);
}

void commitSprites(SpriteScreen screen)
{
    oamUpdate(oamFor(screen));
}