VERSION ?= KJV
TESTING ?= 0
ifeq ($(filter $(VERSION),KJV NKJV ESV NIV NASB CSB),)
$(error VERSION must be KJV, NKJV, ESV, NIV, NASB or CSB)
endif
ifneq ($(words $(VERSION)),1)
$(error Select one VERSION)
endif

# Alternative codecs, viewers and indexes live in research/bible-reader/prototype.
LEGACY_OPTIONS = READER CODEC SEARCH_INDEX DENSE PRUNE FAST_BITS FAST_NATIVE VERSE_BOOST \
                 NATIVE_STREAM PROFILE TEST_FONT NATIVE_OPEN_TEST NATIVE_PAGE_TEST \
                 RAW_ONLY USE_SEEK CHECKPOINTS WORK_PROFILE LCD_ROLL STREAM_SEARCH ITALICS_PROTOTYPE
ifneq ($(strip $(foreach option,$(LEGACY_OPTIONS),$(if $(filter command line,$(origin $(option))),$(option)))),)
$(error Research build options are no longer supported here; see research/bible-reader)
endif

VERSION_LOWER = $(shell printf %s $(VERSION) | tr A-Z a-z)
APP_NAME = BibleWise$(if $(filter KJV,$(VERSION)),,-$(VERSION))
DATA_DIR = build/data/$(VERSION_LOWER)
BUILD_DIR = build/$(VERSION)$(if $(filter 1,$(TESTING)),-test$(if $(TEST_FONT_ID),-$(TEST_FONT_ID))$(if $(filter 1,$(TEST_SYSTEM_FONT_PICKER)),-system-picker))
TARGET = $(BUILD_DIR)/$(APP_NAME).OS3KApp
OBJ = $(addprefix $(BUILD_DIR)/,BibleWise.o Decoder.o Search.o Formatting.o Resources.o)

include ../../Makefile.common
# Dependency includes below must not change Makefile.common's SDK root.
TOP := $(TOP)

CPPFLAGS += -I$(DATA_DIR) -Ibuild/generated
CPPFLAGS += -DBIBLE_APP_NAME=\"$(APP_NAME)\" -DBIBLE_VERSION=\"$(VERSION)\"
CPPFLAGS += -DBIBLEWISE_TEST=$(TESTING)
CPPFLAGS += -DBIBLE_CONTAINER_PATH=\"$(DATA_DIR)/container.bin\"
CPPFLAGS += -DBIBLE_INDEX_PATH=\"$(DATA_DIR)/search.bin\"
CPPFLAGS += -DBIBLE_VERSES_PATH=\"$(DATA_DIR)/verses.bin\"
CPPFLAGS += -DBIBLE_SUMMARIES_PATH=\"$(DATA_DIR)/pruning.bin\"
ifeq ($(TESTING),1)
ifeq ($(TEST_SYSTEM_FONT_PICKER),1)
CPPFLAGS += -DBIBLEWISE_TEST_SYSTEM_FONT_PICKER=1
endif
ifneq ($(TEST_FONT_ID),)
CPPFLAGS += -DBIBLEWISE_TEST_FONT_ID=$(TEST_FONT_ID)
endif
endif
CFLAGS += -Wall -Wextra -Wno-override-init -MMD -MP -fstack-usage
ifneq ($(LINK_MAP),)
LDFLAGS += -Map="$(LINK_MAP)"
endif

DATA_FILES = $(addprefix $(DATA_DIR)/,container.bin search.bin verses.bin pruning.bin source.json search-source.json results.json Navigation.h)
BUILDER_FILES = format_data.py build_data.py convert_source.py compress_text.py build_index.py
SOURCE_FILES = upstream/data/books.json upstream/data/kjv/kjv.json upstream/data/$(VERSION_LOWER)/$(VERSION_LOWER).json

$(DATA_FILES) &: $(BUILDER_FILES) $(SOURCE_FILES)
	python3 build_data.py --version $(VERSION_LOWER) --output $(DATA_DIR)

build/generated/Superscript.h: generate_superscript.py ../../research/fonts/superscript-3x5.json
	python3 $< --output $@

$(BUILD_DIR)/%.o: %.c $(OS3K_HEADERS) $(DATA_FILES) build/generated/Superscript.h
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/Resources.o: Resources.S $(DATA_FILES)
	@mkdir -p $(BUILD_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

-include $(OBJ:.o=.d)
