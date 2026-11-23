SUBDIRS = os3k tests/qemu fonts applets

include Makefile.common

tests/qemu fonts applets: os3k
applets: fonts
