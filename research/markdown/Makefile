OBJ = EditorProbe.o
TARGET = EditorProbe.OS3KApp
include ../../Makefile.common
.PHONY: font
all: font
font:
	$(MAKE) OBJ=FontProbe.o TARGET=FontProbe.OS3KApp FontProbe.OS3KApp
FontProbe.o: ProbeGlyphs.h

.PHONY: live
live:
	$(MAKE) OBJ=LiveMarkdown.o TARGET=LiveMarkdown.OS3KApp LiveMarkdown.OS3KApp
	$(MAKE) OBJ=MarkdownFont.o TARGET=MarkdownFont.OS3KApp MarkdownFont.OS3KApp
LiveMarkdown.o: EditorProbe.c live-markdown.inc
MarkdownFont.o: MarkdownGlyphs.h

.PHONY: hook
hook: live
	$(MAKE) OBJ=BeamerHookProbe.o TARGET=BeamerHookProbe.OS3KApp BeamerHookProbe.OS3KApp
BeamerHookProbe.o: EditorProbe.c
