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

# Link-only cleanup control; original GOT objects are independent of this flag.
OS3K_CLEANUP ?= 1
OS3K_TST_CLEANUP ?= 1
OS3K_A5_CLEANUP ?= 1
OS3K_ASM_LIVENESS ?= 1
OS3K_ASM_CFG ?= 1
ifneq ($(OS3K_CLEANUP),1)
override OS3K_TST_CLEANUP := 0
override OS3K_A5_CLEANUP := 0
override OS3K_ASM_LIVENESS := 0
endif
export OS3K_CLEANUP OS3K_TST_CLEANUP OS3K_A5_CLEANUP OS3K_ASM_LIVENESS OS3K_ASM_CFG
OS3K_TST_STAMP = $(if $(BUILD),$(BUILD),build)/tst-cleanup-mode
.PHONY: FORCE_OS3K_TST_MODE
$(OS3K_TST_STAMP): FORCE_OS3K_TST_MODE
	@mkdir -p $(@D)
	@printf '%s\n' '$(OS3K_TST_CLEANUP)' | cmp -s - $@ || printf '%s\n' '$(OS3K_TST_CLEANUP)' > $@
ifneq ($(filter %.OS3KApp,$(TARGET)),)
$(filter %.OS3KApp,$(TARGET)): $(OS3K_TST_STAMP) $(OS3K_ROOT)/tools/flag_cleanup.py $(OS3K_ROOT)/tools/bounded_flags.py
endif

# Frame cleanup is link-only too; keep canonical compiler objects unchanged.
OS3K_A5_STAMP = $(if $(BUILD),$(BUILD),build)/a5-cleanup-mode
.PHONY: FORCE_OS3K_A5_MODE
$(OS3K_A5_STAMP): FORCE_OS3K_A5_MODE
	@mkdir -p $(@D)
	@printf '%s\n' '$(OS3K_A5_CLEANUP)' | cmp -s - $@ || printf '%s\n' '$(OS3K_A5_CLEANUP)' > $@
ifneq ($(filter %.OS3KApp,$(TARGET)),)
$(filter %.OS3KApp,$(TARGET)): $(OS3K_A5_STAMP) $(OS3K_ROOT)/tools/a5_cleanup.py
endif

# Scratch substitution uses final rendered BSRs and frame offsets.
OS3K_ASM_STAMP = $(if $(BUILD),$(BUILD),build)/asm-liveness-mode
.PHONY: FORCE_OS3K_ASM_MODE
$(OS3K_ASM_STAMP): FORCE_OS3K_ASM_MODE
	@mkdir -p $(@D)
	@printf '%s\n' '$(OS3K_ASM_LIVENESS):$(OS3K_ASM_CFG)' | cmp -s - $@ || printf '%s\n' '$(OS3K_ASM_LIVENESS):$(OS3K_ASM_CFG)' > $@
ifneq ($(filter %.OS3KApp,$(TARGET)),)
$(filter %.OS3KApp,$(TARGET)): $(OS3K_ASM_STAMP) $(OS3K_ROOT)/tools/asm_liveness.py
endif
