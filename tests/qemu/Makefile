OBJ = build/test.o build/externs.o
TARGET = build/test.OS3KApp

include ../../Makefile.common

.PHONY: check
check:
	python3 test_elf_reader.py
	python3 ../check-applet-ids.py
	+CROSS_COMPILE="$(CROSS_COMPILE)" ./build.sh

	+CROSS_COMPILE="$(CROSS_COMPILE)" python3 abi-bridges.py

	+CROSS_COMPILE="$(CROSS_COMPILE)" python3 applet-flags.py

	+CROSS_COMPILE="$(CROSS_COMPILE)" python3 setjmp.py

	+CROSS_COMPILE="$(CROSS_COMPILE)" python3 relative-fixups.py
