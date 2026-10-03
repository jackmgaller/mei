# Mei fantasy console. `make` builds everything for the desktop; `make test` runs tests;
# `make web` builds the WebAssembly version into build/web.

CC      ?= cc
CFLAGS  ?= -O2 -g
CFLAGS  += -std=c11 -Wall -Wextra -Wno-unused-parameter -Isrc/core -Isrc/asm -Isrc/lang
SDL_CFLAGS := $(shell pkg-config --cflags sdl3 2>/dev/null)
SDL_LIBS   := $(shell pkg-config --libs sdl3 2>/dev/null)
# Optional: XInput controllers over USB (macOS has no driver for them).
USB_CFLAGS := $(shell pkg-config --cflags libusb-1.0 2>/dev/null)
USB_LIBS   := $(shell pkg-config --libs libusb-1.0 2>/dev/null)
ifneq ($(USB_LIBS),)
PLATFORM_OBJ = $(B)/src/platform/xinput_usb.o
SDL_CFLAGS += -DMEI_XINPUT_USB
endif

B := build

CORE_SRC := $(wildcard src/core/*.c)
ASM_SRC  := $(filter-out src/asm/main.c,$(wildcard src/asm/*.c))
LANG_SRC := $(filter-out src/lang/main.c,$(wildcard src/lang/*.c))

CORE_OBJ := $(CORE_SRC:%.c=$(B)/%.o)
ASM_OBJ  := $(ASM_SRC:%.c=$(B)/%.o)
LANG_OBJ := $(LANG_SRC:%.c=$(B)/%.o)

TEST_SRC := $(wildcard tests/test_*.c)
TESTS    := $(TEST_SRC:tests/%.c=$(B)/tests/%)

.PHONY: all test clean web carts
all: $(B)/mei $(B)/mei-headless $(B)/meiasm $(B)/meic $(B)/mei-asset-probe $(B)/mei-scene-probe carts

# The system ROM (boot animation + shell), docs/SYSTEM.md
# Akari sources end in .akr
SRC_EXT = $(wildcard $(1).akr)
STDLIB_SRC := $(wildcard stdlib/*.akr stdlib/*/*.akr)
SYSTEM_ROM := $(if $(call SRC_EXT,system/system),$(B)/system.mei)
all: $(SYSTEM_ROM)
$(B)/system.mei: $(shell find system -type f 2>/dev/null | sed 's/ /\\ /g') $(STDLIB_SRC) $(B)/meic
	$(B)/meic $(call SRC_EXT,system/system) -o $@

# Carts: carts/asm/NAME.s and carts/NAME/NAME.akr build to build/carts/NAME.mei
ASM_CARTS  := $(patsubst carts/asm/%.s,$(B)/carts/%.mei,$(wildcard carts/asm/*.s))
LANG_CARTS := $(foreach d,$(wildcard carts/*/),$(if $(call SRC_EXT,$(d)$(notdir $(d:/=))),$(B)/carts/$(notdir $(d:/=)).mei))
# Uninstalled carts remain available through their explicit build targets.
UNINSTALLED_CARTS := demo soundlab worldview
CARTS := $(filter-out $(UNINSTALLED_CARTS:%=$(B)/carts/%.mei),$(LANG_CARTS) $(ASM_CARTS))
carts: $(CARTS)

$(B)/carts/%.mei: carts/asm/%.s $(B)/meiasm
	@mkdir -p $(dir $@)
	$(B)/meiasm $< -o $@

# Every file in a cart's folder, in subfolders too, except its tests/ and screenshots/
# (which its test scripts write to); spaces escaped for make.
CART_FILES = $(shell find carts/$(1) \( -path carts/$(1)/tests -o -path carts/$(1)/screenshots \) -prune -o -type f -print 2>/dev/null | sed 's/ /\\ /g')
define LANG_CART_RULE
$(B)/carts/$(1).mei: $(call SRC_EXT,carts/$(1)/$(1)) $(call CART_FILES,$(1)) $(STDLIB_SRC) $(B)/meic
	@mkdir -p $(B)/carts
	$(B)/meic $$< -o $$@ $$(CART_MEIC_FLAGS)
endef
$(foreach c,$(LANG_CARTS),$(eval $(call LANG_CART_RULE,$(notdir $(c:.mei=)))))

# Carts that use worlds (docs/WORLDKIT.md, "Using a world in a cart"). carts/NAME/worlds.txt
# lists World Kit recipes, one repository path per line (# starts a comment). Each recipe is
# built once into $(B)/worlds/<its folder>/ (the World Checker runs, report-only, and prints a
# summary); tools/world_cart.py writes the sources it read to build.d, so editing any of them
# rebuilds it. The cart's worlds and their games' GAME.game.akr are linked into
# $(B)/cart-worlds/NAME/, which meic searches for imports (-I).
WORLD_CARTS := $(foreach c,$(LANG_CARTS),$(if $(wildcard carts/$(notdir $(c:.mei=))/worlds.txt),$(notdir $(c:.mei=))))
CART_WORLDS = $(strip $(shell sed -e 's/\#.*//' carts/$(1)/worlds.txt))
WORLD_BUILT = $(B)/worlds/$(patsubst %/,%,$(dir $(1)))/build.json
WORLD_RECIPES := $(sort $(foreach c,$(WORLD_CARTS),$(call CART_WORLDS,$(c))))
WORLD_KIT := $(wildcard tools/mei_world.py tools/world_cart.py tools/worldkit/*.py tools/kitcore/*.py tools/assetkit/*.py)
define WORLD_RULE
$(call WORLD_BUILT,$(1)): $(1) $(WORLD_KIT) | $(B)/meic $(B)/mei-headless $(B)/mei-asset-probe $(B)/mei-scene-probe
	PYTHONDONTWRITEBYTECODE=1 python3 tools/world_cart.py build $(1) $(B)
endef
define WORLD_CART_RULE
$(B)/carts/$(1).mei: CART_MEIC_FLAGS = -I $(B)/cart-worlds/$(1)
$(B)/carts/$(1).mei: $(B)/cart-worlds/$(1)/worlds.json
$(B)/cart-worlds/$(1)/worlds.json: carts/$(1)/worlds.txt tools/world_cart.py $(foreach w,$(call CART_WORLDS,$(1)),$(call WORLD_BUILT,$(w)))
	PYTHONDONTWRITEBYTECODE=1 python3 tools/world_cart.py link $(B)/cart-worlds/$(1) $(B) $(call CART_WORLDS,$(1))
endef
$(foreach w,$(WORLD_RECIPES),$(eval $(call WORLD_RULE,$(w))))
$(foreach c,$(WORLD_CARTS),$(eval $(call WORLD_CART_RULE,$(c))))
-include $(foreach w,$(WORLD_RECIPES),$(dir $(call WORLD_BUILT,$(w)))build.d)

# Part of test-carts: World Viewer's scripted run, then the rules above (tests/world_carts.sh).
.PHONY: test-world-carts
test-world-carts: $(B)/carts/worldview.mei
	MEIC=$(B)/meic RUN=$(B)/mei-headless WORLDS=$(B)/cart-worlds/worldview carts/worldview/tests/check.sh
	B=$(B) PYTHONDONTWRITEBYTECODE=1 tests/world_carts.sh
test-carts: test-world-carts

$(B)/%.o: %.c $(wildcard src/*/*.h)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -c $< -o $@

$(B)/libmeicore.a: $(CORE_OBJ)
	@rm -f $@; ar rcs $@ $^

$(B)/libmeiasm.a: $(ASM_OBJ)
	@rm -f $@; ar rcs $@ $^

$(B)/libmeilang.a: $(LANG_OBJ)
	@rm -f $@; ar rcs $@ $^

$(B)/src/platform/sdl_main.o: src/platform/sdl_main.c $(wildcard src/*/*.h)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(SDL_CFLAGS) -c $< -o $@

$(B)/src/platform/xinput_usb.o: src/platform/xinput_usb.c $(wildcard src/*/*.h)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $(USB_CFLAGS) -c $< -o $@

$(B)/mei: $(B)/src/platform/sdl_main.o $(B)/src/platform/sysboot.o $(B)/src/platform/bcnet.o $(PLATFORM_OBJ) $(B)/libmeicore.a
	$(CC) $^ $(SDL_LIBS) $(USB_LIBS) -o $@

$(B)/mei-headless: $(B)/src/platform/headless.o $(B)/src/platform/sysboot.o $(B)/libmeicore.a
	$(CC) $^ -o $@

$(B)/meiasm: $(B)/src/asm/main.o $(B)/libmeiasm.a $(B)/libmeicore.a
	$(CC) $^ -o $@

$(B)/meic: $(B)/src/lang/main.o $(B)/libmeilang.a $(B)/libmeiasm.a $(B)/libmeicore.a
	$(CC) $^ -o $@

TEST_LIBS := $(if $(LANG_OBJ),$(B)/libmeilang.a) $(if $(ASM_OBJ),$(B)/libmeiasm.a) $(B)/libmeicore.a

$(B)/tests/%: tests/%.c $(TEST_LIBS)
	@mkdir -p $(dir $@)
	$(CC) $(CFLAGS) $< $(TEST_LIBS) -o $@
$(B)/tests/test_audio: tests/adpcm_vectors.h   # ADPCM reference vectors (tools/gen_adpcm_vectors.py)

test: $(TESTS) $(B)/meiasm $(B)/meic $(B)/mei-headless $(B)/mei-asset-probe $(B)/mei-scene-probe
	@set -e; for t in $(TESTS); do echo "== $$t"; ./$$t; done
	@if [ -x tests/run_lang_tests.sh ]; then MEIC=$(B)/meic RUN=$(B)/mei-headless ./tests/run_lang_tests.sh; fi
	@if command -v python3 >/dev/null 2>&1; then echo "== tools/meinet/test_meinet.py"; PYTHONDONTWRITEBYTECODE=1 python3 tools/meinet/test_meinet.py; fi
	@if command -v python3 >/dev/null 2>&1; then MEIC=$(B)/meic RUN=$(B)/mei-headless PROBE=$(B)/mei-asset-probe PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_assetkit.py; fi
	@if command -v python3 >/dev/null 2>&1; then echo "== tests/test_worldpack.py"; MEIC=$(B)/meic RUN=$(B)/mei-headless PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_worldpack.py; fi
	@if command -v python3 >/dev/null 2>&1; then echo "== tests/test_worldkit.py"; MEIC=$(B)/meic RUN=$(B)/mei-headless PROBE=$(B)/mei-asset-probe PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_worldkit.py; fi
	@if command -v python3 >/dev/null 2>&1; then echo "== tests/test_mochi.py"; MEIC=$(B)/meic RUN=$(B)/mei-headless PROBE=$(B)/mei-asset-probe PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_mochi.py; fi
	@if command -v python3 >/dev/null 2>&1; then echo "== tests/test_worldverify.py"; MEIC=$(B)/meic RUN=$(B)/mei-headless SCENE_PROBE=$(B)/mei-scene-probe PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_worldverify.py; fi
	@if command -v python3 >/dev/null 2>&1 && python3 -c 'import numpy, PIL' 2>/dev/null; then echo "== tests/reference_renderer: stress scene, subdivision"; mkdir -p $(B)/reference_renderer; { $(RR_RUN) $(RR)/gen_scene.py && $(RR_RUN) $(RR)/oracle.py && $(RR_RUN) $(RR)/geometry_check.py; } > $(B)/reference_renderer/test.log 2>&1 || { tail -5 $(B)/reference_renderer/test.log; echo "FAILED: see $(B)/reference_renderer/test.log"; exit 1; }; fi
	@if command -v python3 >/dev/null 2>&1; then echo "== tools/check_generated.sh"; PYTHONDONTWRITEBYTECODE=1 ./tools/check_generated.sh; fi

# Generated files (stdlib faces and data tables, the reverb table, ADPCM test vectors) match
# what their generators make now.
.PHONY: check-generated
check-generated:
	PYTHONDONTWRITEBYTECODE=1 ./tools/check_generated.sh

# Agent asset recipes, binary exports and six-view renders through the real GPU.
.PHONY: test-world
test-world: $(B)/meic $(B)/mei-headless $(B)/mei-asset-probe
	MEIC=$(B)/meic RUN=$(B)/mei-headless PROBE=$(B)/mei-asset-probe PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_worldkit.py -v
	MEIC=$(B)/meic RUN=$(B)/mei-headless PROBE=$(B)/mei-asset-probe PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_mochi.py -v

# The carts' self-checking scenarios (carts/*/tests/check.sh), through tools/cart_scenario.sh.
.PHONY: test-carts
test-carts: $(B)/meic $(B)/mei-headless
	MEIC=$(B)/meic RUN=$(B)/mei-headless carts/weather/tests/check.sh
	MEIC=$(B)/meic RUN=$(B)/mei-headless carts/lantern/tests/check.sh

# The Reference Renderer (tests/reference_renderer/README.md): Mei's output against an
# independent renderer in Python (NumPy, Pillow). Its carts, probes, images and reports are
# built into $(B)/reference_renderer/. rendercheck-motion runs the checks over time.
RR     := tests/reference_renderer
RR_RUN := MEI_BUILD=$(B) PYTHONDONTWRITEBYTECODE=1 python3
.PHONY: rendercheck rendercheck-motion
rendercheck: $(B)/meic $(B)/mei-headless $(B)/libmeicore.a
	$(RR_RUN) $(RR)/gen_scene.py
	$(RR_RUN) $(RR)/oracle.py
	$(RR_RUN) $(RR)/geometry_check.py
	$(RR_RUN) $(RR)/fuzz.py
	$(RR_RUN) $(RR)/planes_check.py --cases 64
rendercheck-motion: $(B)/meic $(B)/mei-headless $(B)/libmeicore.a
	$(RR_RUN) $(RR)/motion_check.py --frames 128
	$(RR_RUN) $(RR)/texture_check.py
	$(RR_RUN) $(RR)/plane_motion_check.py

.PHONY: test-assets
test-assets: $(B)/meic $(B)/mei-headless $(B)/mei-asset-probe
	MEIC=$(B)/meic RUN=$(B)/mei-headless PROBE=$(B)/mei-asset-probe PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_assetkit.py -v

$(B)/mei-asset-probe: tools/assetkit_probe.c $(B)/libmeicore.a
	$(CC) $(CFLAGS) $^ -o $@

# The World Checker's probe (docs/WORLDCHECKER.md).
$(B)/mei-scene-probe: tools/worldkit/scene_probe.c $(B)/libmeicore.a
	$(CC) $(CFLAGS) $^ -o $@

clean:
	rm -rf $(B)

# ---- WebAssembly build (Emscripten + its SDL3 port) ----
WEB := $(B)/web
WEB_CARTS ?= $(CARTS)
EMFLAGS := --use-port=sdl3 -O3 -std=c11 -Isrc/core -sALLOW_MEMORY_GROWTH=1 \
	-sEXPORTED_FUNCTIONS=_main,_malloc,_free,_web_load_cart,_web_reset,_web_catalogue_add,_web_boot_system,_web_home \
	-sEXPORTED_RUNTIME_METHODS=HEAPU8,stringToNewUTF8

web: $(WEB)/index.html $(CARTS) $(SYSTEM_ROM)
	python3 tools/web_carts.py $(WEB)/carts $(WEB_CARTS)
	$(if $(SYSTEM_ROM),cp $(SYSTEM_ROM) $(WEB)/system.mei)

$(WEB)/index.html: $(CORE_SRC) $(wildcard src/core/*.h) src/platform/sdl_main.c src/platform/sysboot.c web/shell.html
	@mkdir -p $(WEB)
	emcc $(EMFLAGS) $(CORE_SRC) src/platform/sdl_main.c src/platform/sysboot.c --shell-file web/shell.html -o $@
