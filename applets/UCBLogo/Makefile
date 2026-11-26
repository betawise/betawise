UPSTREAM ?= upstream
CORE = coms error eval files graphics init intern libloc lists logodata math mem paren parse print wrksp nographics
PORT_OBJ = build/applet.o build/runtime.o build/softmath.o $(addprefix build/,$(addsuffix .o,$(CORE)))

OBJ = $(PORT_OBJ)
TARGET = build/UCBLogo.OS3KApp
INT = build/prepared
include ../../Makefile.common

CFLAGS += -Ibuild -include build/config.h -DHAVE_CONFIG_H
CFLAGS += -fno-short-enums -fno-builtin -U_FORTIFY_SOURCE

build/prepared: prepare.py port_config.h port_stdio.h $(TOP)/Makefile.common
	python3 prepare.py "$(UPSTREAM)" build
	touch $@

build/%.o: build/prepared $(OS3K_HEADERS)
	$(CC) $(CPPFLAGS) $(CFLAGS) -include port_stdio.h -c build/$*.c -o $@

build/applet.o build/runtime.o build/softmath.o: build/%.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

build/applet.o build/runtime.o build/softmath.o: build/prepared
build/applet.o: ../../os3k/os3k_display_internal.h

$(TARGET): Makefile

HEAP_KIB ?= 64
PROFILE_GC ?= 0
build/runtime.o: Makefile
build/runtime.o: CPPFLAGS += -DLOGO_HEAP_KIB=$(HEAP_KIB) $(if $(filter 1,$(PROFILE_GC)),-DLOGO_PROFILE_GC)
