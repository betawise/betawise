APPLET_DIRS = $(patsubst %/Makefile,%,$(wildcard */Makefile))

# EhBASIC's assembly workspace relocations need a separate fix.
# FileManager is a prototype; native moves and hardware remain unqualified.
DISABLED_APPLETS ?= EhBASIC FileManager
SUBDIRS = $(filter-out $(DISABLED_APPLETS),$(APPLET_DIRS))

CLEAN_SUBDIRS = $(APPLET_DIRS)

include ../Makefile.common

# CI uses the same selection as `all`, ignoring stale disabled applet images.
# Run after building; paths are relative to the repository root.
# BibleWise defaults to KJV only, even when optional translation builds exist.
.PHONY: published-applets
published-applets:
	@bash -c 'shopt -s globstar nullglob; \
	  for image in ../fonts/build/**/*.OS3KApp; do printf "%s\n" "$${image#../}"; done; \
	  for applet in $(SUBDIRS); do \
	    for image in "$$applet"/build/**/*.OS3KApp; do \
	      case "$$image" in \
	        MicroPython/*) [[ "$$image" == MicroPython/build/MicroPython-*.OS3KApp ]] || continue ;; \
	        BibleWise/*) [[ "$$image" == BibleWise/build/KJV/BibleWise.OS3KApp ]] || continue ;; \
	      esac; \
	      printf "applets/%s\n" "$$image"; \
	    done; \
	  done'


.PHONY: fonts
all: fonts
fonts:
	+$(MAKE) -C ../fonts all
UCBLogo: fonts
clean: clean-fonts
.PHONY: clean-fonts
clean-fonts:
	+$(MAKE) -C ../fonts clean
