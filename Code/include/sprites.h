// sprites.h
#ifndef SPRITES_H
#define SPRITES_H
#include <nds.h>

enum SpriteScreen { SPR_MAIN, SPR_SUB };

// Call once per engine you use this on. NOTE: main-engine OAM is already
// initialized by initTextSprites(TEXT_ENGINE_MAIN) in text_sprites.cpp —
// do NOT call initGameSprites(SPR_MAIN) too, oamInit() would reset it and
// wipe out the menu/button text sprites. Sub engine is fully free (its
// old sprite-based text was replaced by the BG tile renderer), so this is
// currently only meant to be called for SPR_SUB.
void initGameSprites(SpriteScreen screen);

u16* allocSpriteGfx(SpriteScreen screen, SpriteSize size, SpriteColorFormat format);

void setSprite(SpriteScreen screen, int oamId, int x, int y,
               SpriteSize size, SpriteColorFormat format, const void* gfx);
void hideSprite(SpriteScreen screen, int oamId);
void commitSprites(SpriteScreen screen);

#endif