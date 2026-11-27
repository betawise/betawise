# Legacy RELATIVE_CALLS remains an alias for existing experiment commands.
OS3K_FIXUPS ?= $(if $(filter undefined,$(origin RELATIVE_CALLS)),1,$(RELATIVE_CALLS))
# Automatic bounded order evaluation and one-stage packaging. Set to 0 to
# retain the previous iterative fixups and two relocation-sizing stages.
OS3K_INTERNAL_ORDERS ?= $(OS3K_FIXUPS)
export OS3K_FIXUPS OS3K_INTERNAL_ORDERS CROSS_COMPILE
OS3K_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
OS3K_COMPILER_STAMP = $(if $(BUILD),$(BUILD),build)/os3k-compile-mode

.PHONY: FORCE_OS3K_COMPILER_MODE
$(OS3K_COMPILER_STAMP): FORCE_OS3K_COMPILER_MODE
	@python3 "$(OS3K_ROOT)/tools/compiler_mode.py" "$@" "$(OS3K_FIXUPS)" "$(CROSS_COMPILE)"
