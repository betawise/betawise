APPLET_DIRS = $(patsubst %/Makefile,%,$(wildcard */Makefile))

# EhBASIC's assembly workspace relocations need a separate fix.
# FileManager is a prototype; native moves and hardware remain unqualified.
DISABLED_APPLETS ?= EhBASIC FileManager
SUBDIRS = $(filter-out $(DISABLED_APPLETS),$(APPLET_DIRS))

CLEAN_SUBDIRS = $(APPLET_DIRS)

include ../Makefile.common

# CI uses the same selection as `all`, ignoring stale disabled applet images.
# Run after building; paths are relative to the repository root.
.PHONY: published-applets
published-applets:
	@$(foreach image,$(wildcard ../fonts/*.OS3KApp),printf '%s\n' 'fonts/$(notdir $(image))';) :
	@$(foreach applet,$(SUBDIRS),$(foreach image,$(wildcard $(applet)/*.OS3KApp),printf '%s\n' 'applets/$(image)';)) :

.PHONY: fonts
all: fonts
fonts:
	+$(MAKE) -C ../fonts all
UCBLogo: fonts
clean: clean-fonts
.PHONY: clean-fonts
clean-fonts:
	+$(MAKE) -C ../fonts clean
