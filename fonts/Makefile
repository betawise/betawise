BDF_DIR = build/bdf
FONT ?= Medium
SIZE_3 = Large
SIZE_4 = Medium
SIZE_5 = Small
SIZE_6 = Tiny
SIZE_NAME_3 = Large
SIZE_NAME_4 = Medium
SIZE_NAME_5 = Small
SIZE_NAME_6 = Tiny
ID_BASE_Serif = 0xAFF0
ID_BASE_Sans = 0xAFF4
ID_BASE_Book = 0xAFF8
ID_BASE_Mono = 0xAFFC

ifneq ($(READER_FAMILY),)
FAMILY = BetaWise$(READER_FAMILY)
BASE = $(FAMILY)-$(SIZE_$(READER_LINES))
FONT_MENU_NAME = $(READER_FAMILY) $(SIZE_NAME_$(READER_LINES))
FONT_NAME = BetaWise $(READER_FAMILY) $(SIZE_NAME_$(READER_LINES))
FONT_LINES = $(READER_LINES)
FONT_INFO = Copyright 1984-1989, 1994 Adobe Systems Incorporated.
FONT_ID = ($(ID_BASE_$(READER_FAMILY)) + $(READER_LINES) - 3)
NORMAL_BDF = $(BDF_DIR)/$(FAMILY)/$(BASE)-Regular.bdf
BOLD_BDF = $(BDF_DIR)/$(FAMILY)/$(BASE)-Bold.bdf
ITALIC_BDF = $(BDF_DIR)/$(FAMILY)/$(BASE)-Italic.bdf
BOLD_ITALIC_BDF = $(BDF_DIR)/$(FAMILY)/$(BASE)-BoldItalic.bdf
MISSING_POLICY = --missing-glyph 0x3f
PRIVATE_BDF = $(BDF_DIR)/$(FAMILY)/private/$(BASE)-SmallCaps.bdf
else
FAMILY = BetaWiseTerminal
BASE = $(FAMILY)-$(FONT)
FONT_MENU_NAME = Terminal $(FONT)
FONT_COLUMNS_Medium = 44
FONT_COLUMNS_Small = 52
FONT_COLUMNS_Tiny = 66
FONT_COLUMNS = $(FONT_COLUMNS_$(FONT))
FONT_NAME = BetaWise Terminal $(FONT)
FONT_LINES_Medium = 8
FONT_LINES_Small = 9
FONT_LINES_Tiny = 10
FONT_LINES = $(FONT_LINES_$(FONT))
FONT_ID = 0xA1F0
FONT_INFO = $(if $(filter Medium,$(FONT)),Public domain; recreated from AS3000 LCD font,Public domain X11 Misc Fixed and BetaWise adaptations)
SOURCE_Medium = glyphs.bdf
SOURCE_Small = glyphs-5x7.bdf
SOURCE_Tiny = glyphs-4x6.bdf
NORMAL_BDF = $(if $(filter Medium,$(FONT)),$(FAMILY)/$(SOURCE_$(FONT)),$(BDF_DIR)/$(FAMILY)/$(SOURCE_$(FONT)))
MISSING_POLICY = --missing-glyph 0x3f
endif

BUILD_DIR = build/$(BASE)
NORMAL_HEADER = $(BUILD_DIR)/glyphs.h
BOLD_HEADER = $(if $(BOLD_BDF),$(BUILD_DIR)/glyphs-bold.h)
ITALIC_HEADER = $(if $(ITALIC_BDF),$(BUILD_DIR)/glyphs-italic.h)
BOLD_ITALIC_HEADER = $(if $(BOLD_ITALIC_BDF),$(BUILD_DIR)/glyphs-bold-italic.h)
PRIVATE_HEADER = $(if $(PRIVATE_BDF),$(BUILD_DIR)/glyphs-private.h)
INT = $(PRIVATE_HEADER) $(NORMAL_HEADER) $(BOLD_HEADER) $(ITALIC_HEADER) $(BOLD_ITALIC_HEADER)
OBJ = $(BUILD_DIR)/FontApplet.o
TARGET = $(BUILD_DIR)/$(BASE).OS3KApp
include ../Makefile.common

$(OBJ): FontApplet.c $(INT) $(OS3K_HEADERS) Makefile
	$(CC) $(CPPFLAGS) $(CFLAGS) -I. -DFONT_NAME='"$(FONT_NAME)"' \
	  -DFONT_MENU_NAME='"$(FONT_MENU_NAME)"' \
	  $(if $(FONT_COLUMNS),-DFONT_COLUMNS=$(FONT_COLUMNS)) \
	  -DFONT_ID='$(FONT_ID)' -DFONT_LINES=$(FONT_LINES) -DFONT_INFO='"$(FONT_INFO)"' \
	  -DFONT_GLYPHS='"$(NORMAL_HEADER)"' \
	  $(if $(BOLD_HEADER),-DFONT_BOLD_GLYPHS='"$(BOLD_HEADER)"') \
	  $(if $(ITALIC_HEADER),-DFONT_ITALIC_GLYPHS='"$(ITALIC_HEADER)"') \
	  $(if $(BOLD_ITALIC_HEADER),-DFONT_BOLD_ITALIC_GLYPHS='"$(BOLD_ITALIC_HEADER)"') \
	  $(if $(PRIVATE_HEADER),-DFONT_PRIVATE_GLYPHS='"$(PRIVATE_HEADER)"') \
	  -c $< -o $@

$(NORMAL_HEADER): $(NORMAL_BDF) fontgen.py Makefile
	mkdir -p $(@D)
	python3 fontgen.py $< $@ $(MISSING_POLICY)
ifneq ($(BOLD_HEADER),)
$(BOLD_HEADER): $(BOLD_BDF) fontgen.py Makefile
	mkdir -p $(@D)
	python3 fontgen.py $< $@ $(MISSING_POLICY) --symbol-prefix BOLD_
endif
ifneq ($(ITALIC_HEADER),)
$(ITALIC_HEADER): $(ITALIC_BDF) fontgen.py Makefile
	mkdir -p $(@D)
	python3 fontgen.py $< $@ $(MISSING_POLICY) --symbol-prefix ITALIC_
endif
ifneq ($(BOLD_ITALIC_HEADER),)
$(BOLD_ITALIC_HEADER): $(BOLD_ITALIC_BDF) fontgen.py Makefile
	mkdir -p $(@D)
	python3 fontgen.py $< $@ $(MISSING_POLICY) --symbol-prefix BOLD_ITALIC_
endif

ifneq ($(PRIVATE_HEADER),)
$(PRIVATE_HEADER): $(PRIVATE_BDF) fontgen.py Makefile
	mkdir -p $(@D)
	python3 fontgen.py $< $@ --missing-glyph blank --symbol-prefix PRIVATE_
endif

clean: clean-generated
.PHONY: clean-generated
clean-generated:
	$(RM) -r build $(wildcard *.OS3KApp)

ifeq ($(READER_FAMILY),)
ifeq ($(FONT),Medium)
READER_JOBS = $(foreach family,Serif Sans Book Mono,$(foreach lines,3 4 5 6,reader-$(family)-$(lines)))
.PHONY: readers $(READER_JOBS) Small Tiny
all: readers Small Tiny
readers: $(READER_JOBS)
$(READER_JOBS): | bdfs
	+$(MAKE) READER_FAMILY=$(word 2,$(subst -, ,$@)) READER_LINES=$(word 3,$(subst -, ,$@)) all
Small Tiny: | bdfs
	+$(MAKE) FONT=$@ all
endif
endif

# One grouped generation prevents parallel family jobs from racing the recipe.
GENERATED_BDFS = $(foreach family,Serif Sans Book Mono,\
  $(foreach lines,3 4 5 6,\
    $(foreach style,Regular Bold Italic BoldItalic,\
      $(BDF_DIR)/BetaWise$(family)/BetaWise$(family)-$(SIZE_$(lines))-$(style).bdf) \
    $(BDF_DIR)/BetaWise$(family)/private/BetaWise$(family)-$(SIZE_$(lines))-SmallCaps.bdf)) \
  $(addprefix $(BDF_DIR)/BetaWiseTerminal/,glyphs.bdf glyphs-5x7.bdf glyphs-4x6.bdf)
BDF_INPUTS = Makefile fontgen.py BetaWiseTerminal/glyphs.bdf \
  $(wildcard ../research/fonts/build*.py ../research/fonts/*characters.json ../research/fonts/superscript-3x5.json) \
  $(wildcard ../os3k/charsets/*.py ../os3k/charsets/*.json ../os3k/charsets/*.txt) \
  $(wildcard upstream/75dpi/*.bdf upstream/100dpi/*.bdf upstream/misc/*.bdf) \
  upstream/75dpi/Makefile.am upstream/100dpi/Makefile.am upstream/misc/Makefile.am
.PHONY: bdfs
bdfs: $(GENERATED_BDFS) $(BDF_DIR)/generation-report.json
$(GENERATED_BDFS) $(BDF_DIR)/generation-report.json &: $(BDF_INPUTS)
	cd .. && python3 research/fonts/build_fonts.py --output fonts/$(BDF_DIR)
