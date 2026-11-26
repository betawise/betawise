VERSE_BOOST ?= 0
SEARCH_CLEAR_COMPLETE ?= 0
FAST_NATIVE ?= 0
FAST_BITS ?= 8
BENCH_QUERY ?= -1
SEARCH_INDEX ?= full
ifeq ($(filter $(SEARCH_INDEX),full compact scan none),)
$(error SEARCH_INDEX must be full, compact, scan or none)
endif
DIRECT_DRAW ?= $(if $(filter Streaming,$(READER)),1,0)
STREAM_SEARCH ?= $(if $(filter Streaming,$(READER)),1,0)
CHECKPOINTS ?= $(if $(filter Streaming,$(READER)),1,0)
WORK_PROFILE ?= 0
LCD_ROLL ?= 0
NATIVE_OPEN_TEST ?= 0
NATIVE_PAGE_TEST ?= 0
NATIVE_STREAM ?= 0
DENSE ?= 0
PRUNE ?= $(if $(filter BibleReader Streaming,$(READER)),1,0)
READER ?= BibleReader
OBJ = $(READER).o Decoder.o resource.o
CODEC ?= huffman
ifeq ($(CODEC),huffman)
OBJ = $(READER).o HuffmanDecoder.o resource.o
ifneq ($(filter $(READER),BibleReader Streaming),)
OBJ += Search.o
endif
endif
VERSION ?= KJV
ifneq ($(words $(VERSION)),1)
$(error Select one VERSION)
endif
ifeq ($(filter $(VERSION),KJV NKJV ESV NIV NASB CSB),)
$(error VERSION must be KJV NKJV ESV NIV NASB or CSB)
endif
VERSION_LOWER = $(shell printf %s $(VERSION) | tr A-Z a-z)
ifneq ($(filter $(READER),BibleReader Streaming),)
ifneq ($(CODEC),huffman)
$(error The reader uses huffman; select READER=Benchmark for arithmetic experiments)
endif
NATIVE_NAME = $(if $(filter 7,$(NATIVE_STREAM)),BibleReader-NativePrewrapFull,$(if $(filter 6,$(NATIVE_STREAM)),BibleReader-NativePrewrap,$(if $(filter 5,$(NATIVE_STREAM)),BibleReader-NativeViewport,$(if $(filter 4,$(NATIVE_STREAM)),BibleReader-NativeLookahead,$(if $(filter 1,$(NATIVE_STREAM)),BibleReader-NativeWindow,$(if $(filter 2,$(NATIVE_STREAM)),BibleReader-NativeDemand,$(if $(filter 3,$(NATIVE_STREAM)),BibleReader-NativeBG,BibleReader)))))))
TARGET = $(if $(filter Streaming,$(READER)),BibleReader-Stream,$(NATIVE_NAME))$(if $(filter KJV,$(VERSION)),,-$(VERSION))$(if $(filter full,$(SEARCH_INDEX)),,-$(SEARCH_INDEX)).OS3KApp
DATA_INDEX = $(if $(filter 1 compact scan,$(PRUNE) $(SEARCH_INDEX)),packed-prune,chapter)
DATA_DIR ?= ../../../.research-work/bible-compression/$(if $(filter 1 compact scan,$(PRUNE) $(SEARCH_INDEX)),reader-viewer,reader)/$(VERSION_LOWER)
BIBLE_DATA ?= $(DATA_DIR)/container.bin
BIBLE_SHA256 ?= auto
OBJ := $(filter-out resource.o,$(OBJ)) ReaderResource.o
RAW_ONLY ?= 1
else
TARGET = BibleReader.OS3KApp
RAW_ONLY ?= 0
endif
BIBLE_DATA ?= ../../../.research-work/bible-compression/ascii-huffman/phrase-raw/container.bin
USE_SEEK ?= 1
ifeq ($(CODEC),huffman)
override USE_SEEK = 0
endif
BIBLE_SHA256 ?= f99854601c6edbced143399772f731f6a8b279ec686dc6573cfeceb282712233
ASCII ?= 1
FULL_CACHE ?= 0
include ../../Makefile.common
CPPFLAGS += -DBIBLE_NOINDEX=$(if $(filter none,$(SEARCH_INDEX)),1,0)
CPPFLAGS += -DBIBLE_VERSE_BOOST=$(VERSE_BOOST) -DBIBLE_FAST_BITS=$(FAST_BITS) -DBIBLE_FAST_NATIVE=$(FAST_NATIVE) -DBIBLE_SEARCH_CLEAR_COMPLETE=$(SEARCH_CLEAR_COMPLETE) -DREADER_BENCH_QUERY=$(BENCH_QUERY)
CPPFLAGS += -DBIBLE_CHECKPOINTS=$(CHECKPOINTS) -DSTREAM_DIRECT=$(DIRECT_DRAW) -DSTREAM_SEARCH=$(STREAM_SEARCH)
CPPFLAGS += -DBIBLE_WORK_PROFILE=$(WORK_PROFILE) -DSTREAM_LCD_ROLL=$(LCD_ROLL) -DREADER_OPEN_TEST=$(NATIVE_OPEN_TEST) -DREADER_PAGE_TEST=$(NATIVE_PAGE_TEST) -DNATIVE_STREAM_MODE=$(NATIVE_STREAM)
CPPFLAGS += -DBIBLE_DENSE=$(DENSE) -DBIBLE_PRUNE=$(if $(filter none,$(SEARCH_INDEX)),0,$(PRUNE))
CPPFLAGS += -DBIBLE_USE_SEEK=$(USE_SEEK) -DBIBLE_RAW_ONLY=$(RAW_ONLY)
ifneq ($(filter $(READER),BibleReader Streaming),)
CPPFLAGS += -DBIBLE_VERSION=\"$(VERSION)\" -DBIBLE_APP_NAME=\"$(basename $(TARGET))\"
endif
CPPFLAGS += -DBIBLE_HUFFMAN=$(if $(filter huffman,$(CODEC)),1,0) -DBIBLE_ASCII=$(ASCII) -DBIBLE_FULL_CACHE=$(FULL_CACHE)
ifeq ($(PROFILE),1)
CPPFLAGS += -DREADER_PROFILE=1
endif
ifeq ($(TEST_FONT),1)
CPPFLAGS += -DREADER_TEST_FONT=1
ifneq ($(TEST_FONT_ID),)
CPPFLAGS += -DREADER_TEST_FONT_ID=$(TEST_FONT_ID)
endif
endif
CFLAGS += -Wall -Wextra -Wno-override-init -fstack-usage

bible.bin Navigation.h &: prepare.py $(BIBLE_DATA)
	python3 prepare.py "$(BIBLE_DATA)" . "$(BIBLE_SHA256)"
resource.o: resource.asm bible.bin seek.bin
BibleReader.o Streaming.o Benchmark.o: Navigation.h Decoder.h HuffmanDecoder.h
BibleReader.o: NativeFeed.h NativePrewrap.h SearchBench.h SearchModesBench.h
Decoder.o: Decoder.h
HuffmanDecoder.o: Decoder.h HuffmanDecoder.h

native-check:
	$(HOST_CC) -DBIBLE_HUFFMAN=$(if $(filter huffman,$(CODEC)),1,0) -O2 -Wall -Wextra $(if $(filter huffman,$(CODEC)),HuffmanDecoder.c,Decoder.c) native_check.c -o /tmp/bible-native-check
	/tmp/bible-native-check bible.bin /tmp/bible-native-output.bin

HOST_CC ?= cc

seek.bin: bible.bin Decoder.c Decoder.h seek_prepare.c
ifeq ($(CODEC),huffman)
	python3 -c 'from pathlib import Path; Path("seek.bin").write_bytes(b"")'
else
	$(HOST_CC) -O2 -Wall -Wextra Decoder.c seek_prepare.c -o seek_prepare
	./seek_prepare bible.bin seek.bin
endif

ifneq ($(filter $(READER),BibleReader Streaming),)
ifeq ($(PREBUILT_DATA),)
$(DATA_DIR)/container.bin $(DATA_DIR)/search.bin $(DATA_DIR)/verses.bin $(DATA_DIR)/pruning.bin &: build_data.py ../../research/bible-reader/packed_index.py ../../research/bible-reader/build_huffman.py ../../research/bible-reader/device_ascii.py upstream/data/$(VERSION_LOWER)/$(VERSION_LOWER).json upstream/data/books.json
	python3 build_data.py --version $(VERSION_LOWER) --search-index $(DATA_INDEX) --output $(DATA_DIR) --reuse
endif
search.bin verses.bin pruning.bin &: search_options.py $(DATA_DIR)/search.bin $(DATA_DIR)/verses.bin $(DATA_DIR)/pruning.bin
	python3 search_options.py "$(DATA_DIR)" "$(SEARCH_INDEX)" search.bin
	cp $(DATA_DIR)/verses.bin verses.bin
	python3 -c 'from pathlib import Path; p=Path("$(DATA_DIR)/pruning.bin"); Path("pruning.bin").write_bytes(p.read_bytes() if p.exists() and "$(SEARCH_INDEX)"!="none" else b"")'
wide.bin: bible.bin wide_huffman.py .build-profile
	python3 wide_huffman.py bible.bin $(FAST_BITS) $@
verse-boost.bin: bible.bin search.bin verse_boost.py .build-profile
	python3 verse_boost.py "$(DATA_DIR)" $(VERSE_BOOST) $@
ReaderResource.o: ReaderResource.asm bible.bin search.bin verses.bin pruning.bin wide.bin verse-boost.bin
../../fonts/build/BetaWiseTerminal-Medium/glyphs.h: ../../fonts/fontgen.py ../../fonts/BetaWiseTerminal/glyphs.bdf
	+$(MAKE) -C ../../fonts build/BetaWiseTerminal-Medium/glyphs.h
BibleReader.o Streaming.o: Search.h NativeFeed.h Superscript.h ../../fonts/build/BetaWiseTerminal-Medium/glyphs.h
Search.o: Search.h SearchMatch.h VerseBoost.h NoIndex.h Decoder.h HuffmanDecoder.h
endif

.PHONY: profile-force
.build-profile: profile-force profile.py
	python3 profile.py $@ "$(READER)" "$(CODEC)" "$(VERSION)" "$(ASCII)" "$(RAW_ONLY)" "$(TEST_FONT)" "$(TEST_FONT_ID)" "$(FULL_CACHE)" "$(PROFILE)" "$(USE_SEEK)" "$(BIBLE_DATA)" "$(BIBLE_SHA256)" "$(DENSE)" "$(PRUNE)" "$(DATA_DIR)" "$(DIRECT_DRAW)" "$(STREAM_SEARCH)" "$(CHECKPOINTS)" "$(WORK_PROFILE)" "$(LCD_ROLL)" "$(NATIVE_OPEN_TEST)" "$(NATIVE_PAGE_TEST)" "$(NATIVE_STREAM)" "$(SEARCH_INDEX)" "$(FAST_BITS)" "$(BENCH_QUERY)" "$(FAST_NATIVE)" "$(SEARCH_CLEAR_COMPLETE)" "$(VERSE_BOOST)"
$(OBJ): .build-profile
bible.bin Navigation.h: .build-profile
ifneq ($(filter $(READER),BibleReader Streaming),)
search.bin verses.bin pruning.bin: .build-profile
endif

ifneq ($(LINK_MAP),)
LDFLAGS += -Map="$(LINK_MAP)"
endif

.PHONY: maintenance-inputs
maintenance-inputs: Navigation.h
	@test -n "$(METRICS_DIR)"
	@mkdir -p "$(METRICS_DIR)"
	@for source in $(READER).c HuffmanDecoder.c Search.c; do $(CC) $(CPPFLAGS) $(CFLAGS) -E "$$source" -o "$(METRICS_DIR)/$${source%.c}.i" || exit; done

Superscript.h: generate_superscript.py
	python3 $<
