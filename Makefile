# Makefile

ROMNAME = rom.nds
BUILDROM = test.nds

define n


endef

# Check if user cloned git repository correctly first thing to prevent excessive user enquiries
# add an exception for the path to hg-engine that is normally in the docker container
ifneq ($(shell pwd),/hg-engine)
ifneq ($(shell git rev-parse --is-inside-work-tree 2>/dev/null), true)
$(error Current directory is not a git repository. Please follow the instructions in the README: https://github.com/BluRosie/hg-engine)
endif
endif

ifneq ($(shell pwd | grep -i 'onedrive'),)
$(error "Do not put files into OneDrive.  Please clone the repository in a different folder." )
endif

DESIRED_GAMECODE := IPKE
GAMECODE = $(shell dd bs=1 skip=12 count=4 if=$(ROMNAME) status=none)
VALID_GAMECODE = $(shell echo $(GAMECODE) | grep -i -q $(DESIRED_GAMECODE); echo $$?)

ifneq ($(VALID_GAMECODE), 0)
# invalid rom detected based on gamecode.  this primarily catches other-language roms
$(error ROM Code read from $(ROMNAME) ($(GAMECODE)) does not match valid ROM Code ($(DESIRED_GAMECODE)).$(n)Please use a valid US HeartGold ROM.$(n)hg-engine does not work with non-USA ROM files)
endif

MAC = $(shell uname -s | grep -i -q 'darwin'; echo $$?)

ifneq ($(MAC), 0)
# see if on msys2, but only if not on mac because /proc/version doesn't exist there
MSYS2 = $(shell grep -i -q 'msys' /proc/version; echo $$?)
else
MSYS2 = 1
endif

# environment setting
# get rid of devkitpro:  if devkitpro is installed, can still use it.  otherwise, default to arm-none-eabi tools
ifeq ($(shell echo $$DEVKITARM),)
ifeq ($(MSYS2), 0)
PREFIX = /mingw64/bin/arm-none-eabi-
else
PREFIX = arm-none-eabi-
endif
else
# support legacy devkitpro instructions
PREFIX = $(DEVKITARM)/bin/arm-none-eabi-
endif
AS = $(PREFIX)gcc -x assembler-with-cpp
CC = $(PREFIX)gcc
LD = $(PREFIX)ld
OBJCOPY = $(PREFIX)objcopy
PYTHON_NO_VENV = python3
VENV = .venv
PYTHON_VENV_VERSION := $(shell $(PYTHON_NO_VENV) -m ensurepip 2>&1 | grep -i -q 'No module named'; echo $$?)

ifneq ($(PYTHON_VENV_VERSION), 0)
# we can use a virtual environment because ensurepip is packaged with the python install
VENV_ACTIVATE = $(VENV)/bin/activate
PYTHON = . $(VENV_ACTIVATE); $(PYTHON_NO_VENV)
REQUIREMENTS = requirements.txt
else
# there is no need to use a virtual environment because python does not have the requirements installed
PYTHON = $(PYTHON_NO_VENV)
VENV_ACTIVATE =
endif

.PHONY: clean all dumprom move_narc

move_narc clean restore: NOSCAN = 1

NOSCAN ?= 0


default: all

ifneq ($(PYTHON_VENV_VERSION), 0)
# only set up venv if we need to
venv: $(VENV_ACTIVATE)

# divorce this python3 from venv so that it works
$(VENV_ACTIVATE):
	$(PYTHON_NO_VENV) -m venv $(VENV)
ifeq ($(MSYS2), 0)
	$(PYTHON) -m pip install ndspy==4.1.0
else
	$(PYTHON) -m pip install -r $(REQUIREMENTS)
endif

endif

####################### Tools #######################
ADPCMXQ := tools/adpcm-xq
ARMIPS := tools/armips
BLZ := tools/blz
BTX := tools/btx
ENCODEPWIMG := tools/ENCODE_IMG
GFX := tools/nitrogfx
MSGENC := tools/msgenc
MOVEDATAGEN := tools/movedatagen
POKEDEXDATAGEN := tools/pokedexdatagen
SPECIESDATAGEN := tools/speciesdatagen
TRAINERDATAGEN := tools/trainerdatagen
NARCHIVE := $(PYTHON) tools/narcpy.py
NDSTOOL := tools/ndstool
NTRWAVTOOL := $(PYTHON) tools/ntrWavTool.py
O2NARC := tools/o2narc
SDATTOOL := $(PYTHON) tools/SDATTool.py

# Compiler/Assembler/Linker settings
LDFLAGS = rom.ld -T $(C_SUBDIR)/linker.ld
ASFLAGS =  -I$(shell pwd)/asm/include -I$(shell pwd)/include -Wa,-I,$(shell pwd)/asm/include -Wa,-I,$(shell pwd)/include -mthumb -mcpu=arm946e-s -mtune=arm946e-s
CFLAGS =  -I$(shell pwd)/include -mthumb -mno-thumb-interwork -mcpu=arm946e-s -mtune=arm946e-s -mno-long-calls -Wall -Wextra -Wno-builtin-declaration-mismatch -Wno-sequence-point -Wno-address-of-packed-member -Os -fira-loop-pressure -fipa-pta
ARMIPS_FLAGS = -equ DEBUG_BATTLE_SCENARIOS 0

ifeq ($(AUTO_TEST),Y)
    # The ignored battle-runner save is produced by the ordinary Stage 5B QA
    # world.  A clean AUTO_TEST build must therefore include that test-only
    # map/header fixture rather than relying on stale incremental outputs.
    STAGE3E2_HEADER := Y
    STAGE5B_RUNTIME_PROOF := Y
    STAGE5BC_RUNTIME_PROOF := Y
    CFLAGS += -DDEBUG_BATTLE_SCENARIOS -Werror
    ARMIPS_FLAGS = -equ DEBUG_BATTLE_SCENARIOS 1
endif

ifeq ($(STAGE2_MAP),Y)
    CFLAGS += -DDEBUG_AUTO_QUEUE_SCRIPT -DSTAGE2_MAP_TEST -Werror
    ARMIPS_FLAGS = -equ DEBUG_BATTLE_SCENARIOS 1
endif

ifeq ($(STAGE5B_RUNTIME_PROOF),Y)
    CFLAGS += -DSTAGE5B_RUNTIME_PROOF -Werror
endif

ifeq ($(STAGE5BC_RUNTIME_PROOF),Y)
    CFLAGS += -DSTAGE5BC_RUNTIME_PROOF -Werror
    TRAINERDATAGEN_EXTRA_CFLAGS := -DSTAGE5BC_RUNTIME_PROOF
endif

ifeq ($(STAGE5C_EVOLUTION_PROOF),Y)
    CFLAGS += -DSTAGE5C_EVOLUTION_PROOF -Werror
endif

ifeq ($(STAGE5D_REGIONAL_FORM_PROOF),Y)
    CFLAGS += -DSTAGE5D_REGIONAL_FORM_PROOF -Werror
endif

ifeq ($(STAGE5E_MEGA_PROOF),Y)
    CFLAGS += -DSTAGE5E_MEGA_PROOF -Werror
endif

ifeq ($(STAGE5F_DEX_PROOF),Y)
    CFLAGS += -DSTAGE5F_DEX_PROOF -Werror
endif
ifeq ($(STAGE5FS_SCOPE_PROOF),Y)
    CFLAGS += -DSTAGE5FS_SCOPE_PROOF -Werror
endif

ifeq ($(BATTLE_SAVE_PROVISION),Y)
    CFLAGS += -DBATTLE_SAVE_PROVISION -Werror
endif

WORLD_INSTALL_ARGS :=
PROJECT_HEADER_FIXTURE := fixtures/stage3e2_header_expansion_world.json
ifeq ($(STAGE3A_HEIGHT),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage3a_height_proof_map.json --output build/stage3a/generated
endif
ifeq ($(STAGE3B_MULTIMAP),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage3b_multimap_proof_world.json --output build/stage3b/generated
endif
ifeq ($(STAGE3C_REGISTRY),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage3c_symbolic_registry_world.json --output build/stage3c/generated
endif
ifeq ($(STAGE3D_GEOMETRY),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage3d_static_geometry_world.json --output build/stage3d/generated
endif
ifeq ($(STAGE3E1_APPEND),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage3e1_narc_append_world.json --output build/stage3e1/generated
endif
ifeq ($(STAGE3E2_HEADER),Y)
    CFLAGS += -DSTAGE3E2_HEADER_TEST
    WORLD_INSTALL_ARGS := --fixture fixtures/stage3e2_header_expansion_world.json --output build/stage3e2/generated
    PROJECT_HEADER_INCLUDE := include/constants/generated/project_map_headers.h
endif
ifeq ($(STAGE5B_RUNTIME_PROOF),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage5b_victini_world.json --output build/stage5b/generated
endif
ifeq ($(STAGE5BC_RUNTIME_PROOF),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage5bc_victini_shared_world.json --output build/stage5bc/generated
    PROJECT_HEADER_FIXTURE := fixtures/stage5bc_victini_shared_world.json
endif
ifeq ($(STAGE6B_UI_AUDIT),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage6b_ui_reference_world.json --output build/stage6b/generated
    PROJECT_HEADER_FIXTURE := fixtures/stage6b_ui_reference_world.json
endif
ifeq ($(STAGE5C_EVOLUTION_PROOF),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage5b_victini_world.json --output build/stage5c/generated
    PROJECT_HEADER_FIXTURE := fixtures/stage5b_victini_world.json
endif
ifeq ($(STAGE5D_REGIONAL_FORM_PROOF),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage5d_hisuian_world.json --output build/stage5d/generated
    PROJECT_HEADER_FIXTURE := fixtures/stage5d_hisuian_world.json
endif
ifeq ($(STAGE5E_MEGA_PROOF),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage5e_mega_world.json --output build/stage5e/generated
    PROJECT_HEADER_FIXTURE := fixtures/stage5e_mega_world.json
endif
ifeq ($(STAGE5F_DEX_PROOF),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage5b_victini_world.json --output build/stage5f/generated
    PROJECT_HEADER_FIXTURE := fixtures/stage5b_victini_world.json
endif
ifeq ($(STAGE4B_ASSET),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4b_asset_world.json --output build/stage4b/generated
endif
ifeq ($(STAGE4C_TEXTURE),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4c_texture_world.json --output build/stage4c/generated
endif
ifeq ($(STAGE4D_TEXTURES),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4d_scalable_textures_world.json --output build/stage4d/generated
endif
ifeq ($(STAGE4E_TRIANGLES),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4e_triangle_world.json --output build/stage4e/generated
endif
ifeq ($(STAGE4F_GLB),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4f_glb_world.json --output build/stage4f/generated
endif
ifeq ($(STAGE4G_SIMPLIFICATION),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4g_simplified_world.json --output build/stage4g/generated
endif
ifeq ($(STAGE4I_MODEL_CAPACITY),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4i_expanded_geometry_world.json --output build/stage4i/generated
endif
ifeq ($(STAGE4J_APPROX_DECIMATION),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4j_approximate_decimation_world.json --output build/stage4j/generated
endif
ifeq ($(STAGE4K_STATIC_HIERARCHY),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4k_static_hierarchy_world.json --output build/stage4k/generated
endif
ifeq ($(STAGE4L_NORMAL_GENERATION),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4l_normal_generation_world.json --output build/stage4l/generated
endif
ifeq ($(STAGE4M_UV_GENERATION),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4m_uv_generation_world.json --output build/stage4m/generated
endif
ifeq ($(STAGE4N_MATERIAL_SYNTHESIS),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4n_material_synthesis_world.json --output build/stage4n/generated
endif
ifeq ($(STAGE4P_ATTRIBUTE_BOOTSTRAP),Y)
    WORLD_INSTALL_ARGS := --fixture fixtures/stage4p_attribute_bootstrap_world.json --output build/stage4p/generated
endif

####################### Output #######################
C_SUBDIR = src
ASM_SUBDIR = asm
INCLUDE_SUBDIR = include
BUILD := build
BUILD_NARC := $(BUILD)/narc
BASE := base
FILESYS := $(BASE)/root

LINK = $(BUILD)/linked.o
OUTPUT = $(BUILD)/output.bin

INCLUDE_SRCS := $(wildcard $(INCLUDE_SUBDIR)/*.h)

C_SRCS := $(wildcard $(C_SUBDIR)/*.c)
ALL_C_SRCS += $(C_SRCS)
C_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(C_SRCS))

ASM_SRCS := $(wildcard $(ASM_SUBDIR)/*.s)
ALL_ASM_SRCS += $(ASM_SRCS)
ASM_OBJS := $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(ASM_SRCS))
OBJS     := $(C_OBJS) $(ASM_OBJS)

ifeq ($(STAGE3E2_HEADER),Y)
$(PROJECT_HEADER_INCLUDE): $(PROJECT_HEADER_FIXTURE) world/registry.json tools/pokeagent/world.py tools/pokeagent/registry.py tools/pokeagent/cli.py $(VENV_ACTIVATE)
	$(PYTHON) -m tools.pokeagent map headers --fixture $(PROJECT_HEADER_FIXTURE) --output $@

$(OBJS): $(PROJECT_HEADER_INCLUDE)
endif

REQUIRED_DIRECTORIES += $(BASE) $(BUILD) $(BUILD_NARC)


## includes
include data/graphics/pokegra.mk
include data/graphics/itemgra.mk
include data/itemdata/itemdata.mk
include data/codetables.mk
include narcs.mk
include overlays.mk
include dump.mk

####################### Build Tools #######################
MSGENC_SOURCES := $(wildcard tools/source/msgenc/*.cpp) $(wildcard tools/source/msgenc/*.h)
$(MSGENC): tools/source/msgenc/*
	cd tools/source/msgenc ; $(MAKE)
	mv tools/source/msgenc/msgenc tools/msgenc

TOOLS += $(MSGENC)

$(NDSTOOL):
ifeq (,$(wildcard $(NDSTOOL)))
	rm -r -f tools/source/ndstool
	cd tools/source ; git clone https://github.com/devkitPro/ndstool.git
	cd tools/source/ndstool ; git checkout fa6b6d01881363eb2cd6e31d794f51440791f336
	@# do not need to account for subdirectories here because ndstool does not have any .sh in subdirs
	cd tools/source/ndstool ; chmod +x *.sh
	cd tools/source/ndstool ; ./autogen.sh
	cd tools/source/ndstool ; ./configure && $(MAKE)
	mv tools/source/ndstool/ndstool tools/ndstool
	rm -r -f tools/source/ndstool
endif

TOOLS += $(NDSTOOL)

$(ARMIPS):
ifeq (,$(wildcard $(ARMIPS)))
	rm -r -f tools/source/armips
	cd tools/source ; git clone --recursive https://github.com/BluRosie/armips.git
	mkdir -p tools/source/armips/build
	cd tools/source/armips/build; cmake .. -DCMAKE_BUILD_TYPE=Release ..
	cd tools/source/armips/build; $(MAKE)
	mv tools/source/armips/build/armips tools/armips
	rm -r -f tools/source/armips
endif

TOOLS += $(ARMIPS)

$(ADPCMXQ):
ifeq (,$(wildcard $(ADPCMXQ)))
	rm -r -f tools/source/adpcm-xq
	cd tools/source ; git clone https://github.com/dbry/adpcm-xq.git
	cd tools/source/adpcm-xq ; gcc -O2 *.c -o adpcm-xq -lm
	mv tools/source/adpcm-xq/adpcm-xq $(ADPCMXQ)
	rm -r -f tools/source/adpcm-xq
endif

TOOLS += $(ADPCMXQ)

tools/ntrWavTool.py:
ifeq (,$(wildcard tools/ntrWavTool.py))
	rm -r -f tools/source/ntrWavTool
	cd tools/source ; git clone https://github.com/turtleisaac/ntrWavTool.git
	mv tools/source/ntrWavTool/ntrWavTool.py tools/ntrWavTool.py
	rm -r -f tools/source/ntrWavTool
endif

TOOLS += tools/ntrWavTool.py

NITROGFX_SOURCES := $(wildcard tools/source/nitrogfx/*.c) $(wildcard tools/source/nitrogfx/*.h)
$(GFX): $(NITROGFX_SOURCES)
	cd tools/source/nitrogfx ; $(MAKE)
	mv tools/source/nitrogfx/nitrogfx $(GFX)

TOOLS += $(GFX)

$(MOVEDATAGEN): $(wildcard tools/source/movedatagen/*.c) data/Moves.c include/move_data.h include/config.h
	cd tools/source/movedatagen ; $(MAKE)

TOOLS += $(MOVEDATAGEN)

$(POKEDEXDATAGEN): $(wildcard tools/source/pokedexdatagen/*.c) data/PokedexSort.c data/PokedexArea.c include/pokedex_archive_data.h include/constants/pokedex.h
	cd tools/source/pokedexdatagen ; $(MAKE)

TOOLS += $(POKEDEXDATAGEN)

$(SPECIESDATAGEN): $(wildcard tools/source/speciesdatagen/*.c) data/Species.c include/species_data.h include/config.h
	cd tools/source/speciesdatagen ; $(MAKE)

TOOLS += $(SPECIESDATAGEN)

$(TRAINERDATAGEN): $(wildcard tools/source/trainerdatagen/*.c) data/Trainers.c include/trainer_data.h include/constants/trainerclass.h include/constants/pokemon.h
	cd tools/source/trainerdatagen ; $(MAKE) EXTRA_CFLAGS="$(TRAINERDATAGEN_EXTRA_CFLAGS)"

TOOLS += $(TRAINERDATAGEN)

$(O2NARC): $(wildcard tools/source/o2narc/*.cpp) $(wildcard tools/source/o2narc/*.h)
	cd tools/source/o2narc ; $(MAKE)
	mv tools/source/o2narc/o2narc $(O2NARC)

TOOLS += $(O2NARC)

$(ENCODEPWIMG):
	cd tools/source/DECODEIMG ; $(MAKE)
	mv tools/source/DECODEIMG/ENCODE_IMG $(ENCODEPWIMG)

TOOLS += $(ENCODEPWIMG)

$(BTX):
	cd tools/source/btx ; $(MAKE)
	mv tools/source/btx/btx $(BTX)

TOOLS += $(BTX)

####################### Build #######################
$(BUILD)/rom_gen.ld:$(LINK) $(OUTPUT) rom.ld
	cp rom.ld $(BUILD)/rom_gen.ld
	$(PYTHON) scripts/generate_ld.py $(BUILD)/rom_gen.ld $(LINK)

# create output folders if they do not exist
$(CODE_BUILD_DIRS):
	mkdir -p $@

# generate .d dependency files that are included as part of compiling if it does not exist
define SRC_OBJ_INC_DEFINE
# this generates the objects as part of generating the dependency list which will just be massive files of rules
$1: $2 $(LEARNSETS_HEADER) $(BATTLETESTS_HEADER) | $(dir $1)
	$(CC) -MMD -MF $(basename $1).d $(CFLAGS) -c $2 -o $1
	@#printf "\t$(CC) $(CFLAGS) -c $2 -o $1" >> $(basename $1).d

-include $(basename $1).d
endef

ifneq (1,$(NOSCAN))
$(foreach src, $(ALL_C_SRCS), $(eval $(call SRC_OBJ_INC_DEFINE,$(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o, $(src)),$(src))))
endif

define ASM_OBJ_INC_DEFINE
# these should have similar dependency scanning, but we do not currently use them in a way conducive to it
$1: $2 | $(dir $1)
	$(AS) $(ASFLAGS) -c $2 -o $1
endef

ifneq (1,$(NOSCAN))
$(foreach src, $(ALL_ASM_SRCS), $(eval $(call ASM_OBJ_INC_DEFINE,$(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o, $(src)),$(src))))
endif

$(LINK):$(OBJS)
	$(LD) $(LDFLAGS) -o $@ $(OBJS)

$(OUTPUT):$(LINK)
	$(OBJCOPY) -O binary $< $@

# only reextract from the rom if the romname is newer than the extracted arm9.bin
$(BASE)/arm9.bin: $(ROMNAME) $(NDSTOOL) $(VENV_ACTIVATE)
	rm -rf $(BASE)
	@mkdir -p $(REQUIRED_DIRECTORIES)
	$(NDSTOOL) -x $(ROMNAME) -9 $(BASE)/arm9.bin -7 $(BASE)/arm7.bin -y9 $(BASE)/overarm9.bin -y7 $(BASE)/overarm7.bin -d $(FILESYS) -y $(BASE)/overlay -t $(BASE)/banner.bin -h $(BASE)/header.bin
	$(NARCHIVE) extract $(FILESYS)/a/0/2/8 -o $(BUILD)/a028/ -nf

all: $(OUTPUT) $(OVERLAY_OUTPUTS) $(TOOLS) $(BASE)/arm9.bin
	@# find and delete macOS and windows files
	find . \( -name "*.DS_Store" -o -name "*:Zone.Identifier" \) -delete
	$(PYTHON) scripts/make.py $(CFLAGS)
# TODO: find a convenient way to not have this be a separate $(MAKE)
	$(MAKE) move_narc
	$(ARMIPS) armips/global.s $(ARMIPS_FLAGS)
	$(NARCHIVE) create $(FILESYS)/a/0/2/8 $(BUILD)/a028/ -nf
ifneq ($(filter Y,$(STAGE2_MAP) $(AUTO_TEST)),)
	$(PYTHON) -m tools.pokeagent map install $(WORLD_INSTALL_ARGS)
endif
	@echo "Making ROM..."
	$(NDSTOOL) -c $(BUILDROM) -9 $(BASE)/arm9.bin -7 $(BASE)/arm7.bin -y9 $(BASE)/overarm9.bin -y7 $(BASE)/overarm7.bin -d $(FILESYS) -y $(BASE)/overlay -t $(BASE)/banner.bin -h $(BASE)/header.bin
	@echo "Done.  See output $(BUILDROM)."


####################### Restore clean base ################
NEWFILE = romOld-`date +%d%b%y`.nds
CLEANROM = romClean.nds
restore:
	mv $(ROMNAME) $(NEWFILE)
	cp $(CLEANROM) $(ROMNAME)

####################### Restore and build ################
restore_build: | restore all

####################### Clean #######################
clean:
	rm -rf $(BUILD) $(BASE) $(BUILD)/rom_gen.ld $(BUILD)/rom_gen_battle.ld
	rm -rf armips/include/generated include/constants/generated data/generated
	@echo "Build artifacts removed."

clean_tools:
	rm -rf $(TOOLS) $(VENV)

.PHONY: stage2-proof
stage2-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y

.PHONY: stage3a-height-proof
stage3a-height-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3A_HEIGHT=Y

.PHONY: stage3b-multimap-proof
stage3b-multimap-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3B_MULTIMAP=Y

.PHONY: stage3c-registry-proof
stage3c-registry-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3C_REGISTRY=Y

.PHONY: stage3d-geometry-proof
stage3d-geometry-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3D_GEOMETRY=Y

.PHONY: stage3e1-narc-append-proof
stage3e1-narc-append-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E1_APPEND=Y

.PHONY: stage3e2-header-expansion-proof
stage3e2-header-expansion-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y

.PHONY: stage5b-runtime-proof
stage5b-runtime-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5B_RUNTIME_PROOF=Y

.PHONY: stage5bc-shared-runtime-proof
stage5bc-shared-runtime-proof:
	$(MAKE) -C tools/source/trainerdatagen clean
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5B_RUNTIME_PROOF=Y STAGE5BC_RUNTIME_PROOF=Y
	$(MAKE) -C tools/source/trainerdatagen clean

.PHONY: stage6b-ui-reference
stage6b-ui-reference:
	$(MAKE) -C tools/source/trainerdatagen clean
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5B_RUNTIME_PROOF=Y STAGE5BC_RUNTIME_PROOF=Y STAGE6B_UI_AUDIT=Y
	$(MAKE) -C tools/source/trainerdatagen clean

.PHONY: stage5c-evolution-proof
stage5c-evolution-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5C_EVOLUTION_PROOF=Y

.PHONY: stage5d-regional-form-proof
stage5d-regional-form-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5D_REGIONAL_FORM_PROOF=Y

.PHONY: stage5e-mega-proof
stage5e-mega-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5E_MEGA_PROOF=Y

.PHONY: stage5f-dex-proof
stage5f-dex-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5F_DEX_PROOF=Y

.PHONY: stage5fs-dex-boundary-proof
stage5fs-dex-boundary-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE3E2_HEADER=Y STAGE5F_DEX_PROOF=Y STAGE5FS_SCOPE_PROOF=Y

.PHONY: stage5f-roster-readiness
stage5f-roster-readiness:
	. .venv/bin/activate; python3 -m tools.pokeagent.roster_inventory --output docs/data/hgengine_roster_inventory.json --revision $$(git rev-parse HEAD)
	. .venv/bin/activate; python3 -m tools.pokeagent.roster_readiness --output build/reports/stage5f-dex-archive-validation.json
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage5a_roster_inventory tests.test_pokeagent_stage5f_roster_readiness

.PHONY: stage6a-presentation
stage6a-presentation:
	. .venv/bin/activate; python3 -m tools.pokeagent.stage6a_visuals
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage6a_presentation

.PHONY: stage6b-ui-audit
stage6b-ui-audit:
	. .venv/bin/activate; python3 -m tools.pokeagent.ui_audit
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage6b_ui_audit

.PHONY: battle-test-save
battle-test-save:
	. .venv/bin/activate; python3 -m tools.pokeagent qa run \
		qa/scenarios/stage5b_victini_runtime.json --build --timeout 600
	. .venv/bin/activate; python3 -m tools.pokeagent.battle_save \
		--dsv build/qa/stage5b_victini_runtime/desmume-config/desmume/test.dsv \
		--output test.sav

.PHONY: stage4b-asset-proof
stage4b-asset-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4B_ASSET=Y

.PHONY: stage4c-texture-proof
stage4c-texture-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4C_TEXTURE=Y

.PHONY: stage4d-texture-scaling-proof
stage4d-texture-scaling-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4D_TEXTURES=Y

.PHONY: stage4e-triangle-proof
stage4e-triangle-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4E_TRIANGLES=Y

.PHONY: stage4f-glb-proof
stage4f-glb-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4F_GLB=Y

.PHONY: stage4g-simplification-proof
stage4g-simplification-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4G_SIMPLIFICATION=Y

.PHONY: stage4i-model-capacity-proof
stage4i-model-capacity-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4I_MODEL_CAPACITY=Y

.PHONY: stage4j-approx-decimation-proof
stage4j-approx-decimation-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4J_APPROX_DECIMATION=Y

.PHONY: stage4k-static-hierarchy-proof
stage4k-static-hierarchy-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4K_STATIC_HIERARCHY=Y

.PHONY: stage4l-normal-generation-proof
stage4l-normal-generation-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4L_NORMAL_GENERATION=Y

.PHONY: stage4m-uv-generation-proof
stage4m-uv-generation-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4M_UV_GENERATION=Y

.PHONY: stage4n-material-synthesis-proof
stage4n-material-synthesis-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4N_MATERIAL_SYNTHESIS=Y

.PHONY: stage4o-geometry-predecimation-proof
stage4o-geometry-predecimation-proof:
	rm -rf build/stage4o
	. .venv/bin/activate; python3 -m tools.pokeagent asset geometry-reduce assets/manifests/stage4o_dense_geometry_shrine.json --output build/stage4o --json
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage4o_geometry_reduce

.PHONY: stage4p-attribute-bootstrap-proof
stage4p-attribute-bootstrap-proof:
	$(MAKE) clean
	$(MAKE) STAGE2_MAP=Y STAGE4P_ATTRIBUTE_BOOTSTRAP=Y

.PHONY: stage4q-generated-topology-proof
stage4q-generated-topology-proof:
	. .venv/bin/activate; python3 -m tools.pokeagent asset topology-sanitize assets/manifests/stage4q_generated_topology.json --output build/stage4q --json
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage4q_topology

.PHONY: stage4r-tiny-face-proof
stage4r-tiny-face-proof:
	. .venv/bin/activate; python3 -m tools.pokeagent asset tinyface-sanitize assets/manifests/stage4r_target_null.json --output build/stage4r --json
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage4r_tinyface

.PHONY: stage4s-real-generated-asset-proof
stage4s-real-generated-asset-proof:
	. .venv/bin/activate; python3 -m tools.pokeagent asset generated-pipeline assets/manifests/stage4s_real_generated_shrine.json --output build/stage4s --json; test $$? -eq 1
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage4s_generated_pipeline

.PHONY: stage4t-generator-topology-proof
stage4t-generator-topology-proof:
	. .venv/bin/activate; python3 -m tools.pokeagent asset generator-topology assets/manifests/stage4t_triposr_topology_sweep.json --output build/stage4t/proof --json; test $$? -eq 1
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage4t_generator_topology

.PHONY: stage5a-roster-audit
stage5a-roster-audit:
	. .venv/bin/activate; python3 -m tools.pokeagent.roster_inventory --output docs/data/hgengine_roster_inventory.json --revision $$(git rev-parse HEAD)
	. .venv/bin/activate; python3 -m unittest -v tests.test_pokeagent_stage5a_roster_inventory

ALL_CODE_OBJS := $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.o,$(ALL_C_SRCS)) \
 $(patsubst $(ASM_SUBDIR)/%.s,$(BUILD)/%.o,$(ALL_ASM_SRCS)) \
 $(patsubst $(C_SUBDIR)/%.c,$(BUILD)/%.d,$(ALL_C_SRCS))

clean_code:
	rm -f $(ALL_CODE_OBJS) $(LINKED_OUTPUTS) $(OUTPUT) $(OVERLAY_OUTPUTS) $(BUILD)/rom_gen.ld $(BUILD)/rom_gen_battle.ld

####################### Final ROM Build #######################
CODE_ADDON_ARTIFACTS := $(wildcard $(BUILD)/a028/9_*) $(wildcard $(BUILD)/a028/8_1*) $(wildcard build/$(BUILD)/8_2*) $(BUILD)/a028/8_07 $(BUILD)/a028/8_08 $(BUILD)/a028/8_09
CODE_ADDON_ARTIFACTS := $(filter-out $(BUILD)/a028/8_1 $(BUILD)/a028/8_2 $(BUILD)/a028/8_3 $(BUILD)/a028/8_4 $(BUILD)/a028/8_5 $(BUILD)/a028/8_6, $(CODE_ADDON_ARTIFACTS))

move_narc: $(NARC_FILES)
	@echo "battle hud layout:"
	cp $(BATTLEHUD_NARC) $(BATTLEHUD_TARGET)

	@echo "move data:"
	cp $(MOVEDATA_NARC) $(MOVEDATA_TARGET)

	@echo "move particles:"
	cp $(MOVEPARTICLES_NARC) $(MOVEPARTICLES_TARGET)

	@echo "item data files:"
	cp $(ITEMDATA_NARC) $(ITEMDATA_TARGET)

	@echo "mon sprite data:"
	cp $(POKEGRA_NARC) $(POKEGRA_TARGET)
	cp $(POKEGRA_NARC) $(PBR_POKEGRA_TARGET)

	@echo "opening demo files:"
	cp $(OPENDEMO_NARC) $(OPENDEMO_TARGET)

	@echo "mon personal data:"
	cp $(MONDATA_NARC) $(MONDATA_TARGET)

	@echo "sprite offsets:"
	cp $(SPRITEOFFSETS_NARC) $(SPRITEOFFSETS_TARGET)

	@echo "mon height offsets (a005):"
	cp $(HEIGHT_NARC) $(HEIGHT_TARGET)

	@echo "dex area data:"
	cp $(DEXAREA_NARC) $(DEXAREA_TARGET)

	@echo "pokedex sort lists:"
	cp $(DEXSORT_NARC) $(DEXSORT_TARGET)

	@echo "evolution data:"
	cp $(EVOS_NARC) $(EVOS_TARGET)

	@echo "regional dex order:"
	cp $(REGIONALDEX_NARC) $(REGIONALDEX_TARGET)

	@echo "trainer data:"
	cp $(TRAINERDATA_NARC) $(TRAINERDATA_TARGET)
	cp $(TRAINERDATA_NARC_2) $(TRAINERDATA_TARGET_2)

	@echo "trainer text:"
	cp $(TRAINERTEXT_NARC) $(TRAINERTEXT_TARGET)
	cp $(TRAINERTEXT_NARC_2) $(TRAINERTEXT_TARGET_2)

	@echo "footprints:"
	cp $(FOOTPRINTS_NARC) $(FOOTPRINTS_TARGET)

	@echo "move anims:"
	cp $(MOVEANIM_NARC) $(MOVEANIM_TARGET)

	@echo "move sub animations:"
	cp $(MOVESUBANIM_NARC) $(MOVESUBANIM_TARGET)

	@echo "move battle scripts:"
	cp $(MOVE_SEQ_NARC) $(MOVE_SEQ_TARGET)

	@echo "move battle scripts:"
	cp $(BATTLE_EFF_NARC) $(BATTLE_EFF_TARGET)

	@echo "battle sub effects:"
	cp $(BATTLE_SUB_NARC) $(BATTLE_SUB_TARGET)

	@echo "bag gfx:"
	cp $(BAGGFX_NARC) $(BAGGFX_TARGET)

	@echo "item gfx:"
	cp $(ITEMGFX_NARC) $(ITEMGFX_TARGET)

	@echo "dex gfx for fairy:"
	cp $(DEXGFX_NARC) $(DEXGFX_TARGET)

	@echo "battle gfx for fairy:"
	cp $(BATTLEGFX_NARC) $(BATTLEGFX_TARGET)

	@echo "otherpoke gfx for fairy:"
	cp $(OTHERPOKE_NARC) $(OTHERPOKE_TARGET)

	@echo "pokemon icons:"
	cp $(ICONGFX_NARC) $(ICONGFX_TARGET)

	@echo "wild encounters:"
	cp $(ENCOUNTER_NARC) $(ENCOUNTER_TARGET)

	@echo "safari zone encounters:"
	cp $(SAFARI_ENCOUNTER_NARC) $(SAFARI_ENCOUNTER_TARGET)

	@echo "pokemon overworlds:"
	cp $(OVERWORLDS_NARC) $(OVERWORLDS_TARGET)

	@echo "pokemon overworld data:"
	cp $(OVERWORLD_DATA_NARC) $(OVERWORLD_DATA_TARGET)

	@echo "move an updated gs_sound_data.sdat:"
	cp $(SDAT_BUILD) $(SDAT_TARGET)

	@echo "text data:"
	cp $(MSGDATA_NARC) $(MSGDATA_TARGET)

	@echo "ball spa files:"
	cp $(BALL_SPA_NARC) $(BALL_SPA_TARGET)

	@echo "pokewalker sprites:"
	cp $(PW_POKEGRA_NARC) $(PW_POKEGRA_TARGET)

	@echo "pokewalker icons:"
	cp $(PW_POKEICON_NARC) $(PW_POKEICON_TARGET)

	@echo "font:"
	if [ $$(grep -i -c "//#define IMPLEMENT_TRANSPARENT_TEXTBOXES" $(INCLUDE_SUBDIR)/config.h) -eq 0 ]; then cp $(FONT_NARC) $(FONT_TARGET); fi

	@echo "textbox:"
	if [ $$(grep -i -c "//#define IMPLEMENT_TRANSPARENT_TEXTBOXES" $(INCLUDE_SUBDIR)/config.h) -eq 0 ]; then cp $(TEXTBOX_NARC) $(TEXTBOX_TARGET); fi

	@echo "scripts:"
	cp $(SCR_SEQ_NARC) $(SCR_SEQ_TARGET)

	@echo "headbutt trees:"
	cp $(HEADBUTT_NARC) $(HEADBUTT_TARGET)

	@echo "trainer gfx:"
	cp $(TRAINER_GFX_NARC) $(TRAINER_GFX_TARGET)

	@echo "trainer back gfx:"
	cp $(TRAINER_GFX_BACK_NARC) $(TRAINER_GFX_BACK_TARGET)

	@echo "levelup learnset:"
	cp $(LEVELUPLEARNSET_NARC) $(LEVELUPLEARNSET_TARGET)

	@echo "egg moves:"
	cp $(EGGLEARNSET_NARC) $(EGGLEARNSET_TARGET)



	@echo "baby mons:"
	cp $(BABYMONS_BIN) $(BABYMONS_TARGET)

	@if test -s build/a028/8_00; then \
		rm -rf build/a028/8_0 build/a028/8_1 build/a028/8_2 build/a028/8_3 build/a028/8_4 build/a028/8_5 build/a028/8_6 build/a028/8_7 build/a028/8_8 build/a028/8_9; \
	fi
	@if test -s build/a028/8_7; then \
		rm -rf build/a028/8_7 build/a028/8_8 build/a028/8_9; \
	fi
	@rm -rf $(CODE_ADDON_ARTIFACTS)

	@echo "hidden ability table:"
	cp $(HIDDEN_ABILITY_TABLE_BIN) $(HIDDEN_ABILITY_TABLE_TARGET)

	@echo "base experience table:"
	cp $(BASE_EXPERIENCE_TABLE_BIN) $(BASE_EXPERIENCE_TABLE_TARGET)

	@echo "icon palette table:"
	cp $(ICON_PALETTE_TABLE_BIN) $(ICON_PALETTE_TABLE_TARGET)

	@echo "species to ow female table:"
	cp $(SPECIES_TO_OW_FEMALE_BIN) $(SPECIES_TO_OW_FEMALE_TARGET)

	@echo "form data table:"
	cp $(POKEFORMDATATBL_BIN) $(POKEFORMDATATBL_TARGET)

	@echo "form to species mapping table:"
	cp $(FORMTOSPECIES_BIN) $(FORMTOSPECIES_TARGET)

	@echo "form reversion mapping table:"
	cp $(FORMREVERSION_BIN) $(FORMREVERSION_TARGET)

	@echo "machine moves:"
	cp $(MACHINELEARNSET_BIN) $(MACHINELEARNSET_TARGET)

	@echo "tutor moves:"
	cp $(TUTORLEARNSET_BIN) $(TUTORLEARNSET_TARGET)

	@echo "battle tests:"
	cp $(BATTLETESTS_BIN) $(BATTLETESTS_TARGET)

	@echo "background gfx ids:"
	cp $(BACKGROUND_GFX_IDS_BIN) $(BACKGROUND_GFX_IDS_TARGET)

	@echo "hidden item params:"
	cp $(HIDDEN_ITEM_PARAMS_BIN) $(HIDDEN_ITEM_PARAMS_TARGET)

update_machine_moves: $(VENV_ACTIVATE)
	$(PYTHON) scripts/update_machine_moves.py --descriptions --sprites
	@echo "Updated item descriptions and sprites. Double check formatting"


# needed to keep the $(SDAT_OBJ_DIR)/WAVE_ARC_PV%/00.swav from being detected as an intermediate file
.SECONDARY:

####################### Debug #######################
print-% : ; $(info $* is a $(flavor $*) variable set to [$($*)]) @true
