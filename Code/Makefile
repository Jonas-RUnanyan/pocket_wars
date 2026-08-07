#---------------------------------------------------------------------------------
# BlocksDS Makefile
# Converted from your specific devkitARM Makefile
#---------------------------------------------------------------------------------

#---------------------------------------------------------------------------------
# Check BlocksDS environment
#---------------------------------------------------------------------------------
ifeq ($(strip $(BLOCKSDS)),)
$(error "Please set BLOCKSDS in your environment. export BLOCKSDS=<path to BlocksDS>")
endif

#---------------------------------------------------------------------------------
# Project configuration - matches your original devkitARM setup
#---------------------------------------------------------------------------------

# TARGET: Project name (auto-derived from directory name, just like your original)
NAME := $(shell basename $(CURDIR))

# Game info (shown in DS menu)
GAME_TITLE     := Advanced ARM9 template
GAME_SUBTITLE1 := built with BlocksDS
GAME_SUBTITLE2 := 

#---------------------------------------------------------------------------------
# Directory configuration - EXACTLY matching your devkitARM Makefile
#---------------------------------------------------------------------------------
# Your original:          BlocksDS equivalent:
# BUILD    := build    →  (handled automatically by BlocksDS)
# SOURCES  := source   →  SOURCEDIRS
# INCLUDES := include  →  INCLUDEDIRS  
# DATA     := (empty)  →  BINDIRS
# GRAPHICS := gfx      →  GFXDIRS
# AUDIO    := audio    →  AUDIODIRS

SOURCEDIRS  := source
INCLUDEDIRS := include
BINDIRS     := 
GFXDIRS     := gfx
AUDIODIRS   := audio

#---------------------------------------------------------------------------------
# Optional features from your original Makefile
#---------------------------------------------------------------------------------

# ICON: Leave empty for default, or specify path to icon image
# Your original: ICON :=
ICON :=

# NITRO: NitroFS directory (filesystem accessible at runtime)
# Your original: NITRO :=
# Leave empty if not using NitroFS
NITROFSDIR :=

#---------------------------------------------------------------------------------
# Build options
#---------------------------------------------------------------------------------

# Custom defines (add any -D flags here)
DEFINES :=

# Libraries to link
# BlocksDS automatically links -lnds9
# Add any additional libraries here
LIBS := -lnds9

# Automatically add maxmod library if using audio
# (matches your original AUDIO handling)
# ifneq ($(strip $(AUDIODIRS)),)
# LIBS := -lmm9 $(LIBS)
# DEFINES += -DUSE_MAXMOD
# endif

# Automatically add filesystem libraries if using NitroFS
# (matches your original NITRO handling)
ifneq ($(strip $(NITROFSDIR)),)
LIBS := -lfilesystem -lfat $(LIBS)
endif

#---------------------------------------------------------------------------------
# Include BlocksDS build system
# This replaces all the complex build rules from your original Makefile
# (Everything from line 80+ in your original)
#---------------------------------------------------------------------------------

include $(BLOCKSDS)/sys/default_makefiles/rom_arm9/Makefile

#---------------------------------------------------------------------------------