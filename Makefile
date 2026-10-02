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
all: $(B)/mei $(B)/mei-headless $(B)/meiasm $(B)/meic carts

# The system ROM (boot animation + shell), docs/SYSTEM.md
# Akari sources end in .akr (.mls is the older extension and still builds)
SRC_EXT = $(firstword $(foreach e,akr mls,$(if $(wildcard $(1).$(e)),$(1).$(e))))
STDLIB_SRC := $(wildcard stdlib/*.akr stdlib/*.akr)
SYSTEM_ROM := $(if $(call SRC_EXT,system/system),$(B)/system.mei)
all: $(SYSTEM_ROM)
$(B)/system.mei: $(shell find system -type f 2>/dev/null | sed 's/ /\\ /g') $(STDLIB_SRC) $(B)/meic
	$(B)/meic $(call SRC_EXT,system/system) -o $@

# Carts: carts/asm/NAME.s and carts/NAME/NAME.akr build to build/carts/NAME.mei
ASM_CARTS  := $(patsubst carts/asm/%.s,$(B)/carts/%.mei,$(wildcard carts/asm/*.s))
LANG_CARTS := $(foreach d,$(wildcard carts/*/),$(if $(call SRC_EXT,$(d)$(notdir $(d:/=))),$(B)/carts/$(notdir $(d:/=)).mei))
CARTS := $(LANG_CARTS) $(ASM_CARTS)
carts: $(CARTS)

$(B)/carts/%.mei: carts/asm/%.s $(B)/meiasm
	@mkdir -p $(dir $@)
	$(B)/meiasm $< -o $@

define LANG_CART_RULE
$(B)/carts/$(1).mei: $(call SRC_EXT,carts/$(1)/$(1)) $(wildcard carts/$(1)/*) $(STDLIB_SRC) $(B)/meic
	@mkdir -p $(B)/carts
	$(B)/meic $$< -o $$@
endef
$(foreach c,$(LANG_CARTS),$(eval $(call LANG_CART_RULE,$(notdir $(c:.mei=)))))

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

test: $(TESTS) $(B)/meiasm $(B)/meic $(B)/mei-headless
	@set -e; for t in $(TESTS); do echo "== $$t"; ./$$t; done
	@if [ -x tests/run_lang_tests.sh ]; then MEIC=$(B)/meic RUN=$(B)/mei-headless ./tests/run_lang_tests.sh; fi
	@if command -v python3 >/dev/null 2>&1; then echo "== tools/meinet/test_meinet.py"; PYTHONDONTWRITEBYTECODE=1 python3 tools/meinet/test_meinet.py; fi

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
