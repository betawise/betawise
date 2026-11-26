OBJ = build/FileManager.o build/Flash.o build/FlashWorker.o
TARGET = build/FileManager.OS3KApp

include ../../Makefile.common

$(OBJ): Flash.h Makefile

build/FlashWorker.o: FlashWorker.S
	$(CC) -m68000 -c $< -o $@
