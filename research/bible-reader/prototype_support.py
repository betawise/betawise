"""Restore the frozen experimental reader without reviving options in production."""

import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[2]
SNAPSHOT = HERE / "prototype"
DEFAULT_OUTPUT = WORKSPACE / ".research-work/bible-compression/prototype-private-workspace"


def link_directory(link, target):
    if link.exists() or link.is_symlink():
        if link.resolve() != target.resolve():
            raise ValueError(f"Existing workspace link points elsewhere: {link}")
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target.resolve(), target_is_directory=target.is_dir())


def restore_workspace(output=DEFAULT_OUTPUT):
    """Preserve historical paths while sharing SDK, firmware and pinned source data.

    Builds write only to the restored applet directory; normal production files
    are never replaced. Generated historical payloads remain in .research-work.
    """
    output = Path(output).resolve()
    manifest = json.loads((SNAPSHOT / "snapshot.json").read_text())
    app = output / "betawise/applets/BibleReader"
    app.mkdir(parents=True, exist_ok=True)
    for entry in manifest["files"]:
        source = SNAPSHOT / entry["path"]
        destination = app / entry["path"]
        if not destination.exists():
            shutil.copy2(source, destination)
        elif destination.read_bytes() != source.read_bytes():
            raise ValueError(f"Choose another output; restored source was edited: {destination}")
    # Keep the old border helper out of today's SDK while preserving the frozen
    # streaming source. GNUmakefile wraps, rather than edits, its original Makefile.
    shutil.copy2(HERE / "LegacyGraphics.h", app / "LegacyGraphics.h")
    (app / "GNUmakefile").write_text(
        'include Makefile\nifeq ($(READER),Streaming)\n'
        'CPPFLAGS += -include $(CURDIR)/LegacyGraphics.h\nendif\n')
    for name in ["os3k", "fonts", "research", "Makefile.common"]:
        link_directory(output / "betawise" / name, WORKSPACE / "betawise" / name)
    for name in ["Ghidra", "mame", ".research-work"]:
        link_directory(output / name, WORKSPACE / name)
    upstream = WORKSPACE / "betawise/applets/BibleReader/upstream"
    if not upstream.exists():
        upstream = WORKSPACE / "betawise/applets/BibleWise/upstream"
    link_directory(app / "upstream", upstream)

    tests = output / "betawise/tests/mame/asneo"
    tests.mkdir(parents=True, exist_ok=True)
    canonical = WORKSPACE / "betawise/tests/mame/asneo"
    for source in canonical.glob("*"):
        destination = tests / source.name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
        elif source.is_dir() and source.name != "__pycache__":
            link_directory(destination, source)
    # Frozen applet-specific harnesses replace the current production-only ones.
    for source in (SNAPSHOT / "tests").iterdir():
        shutil.copy2(source, tests / source.name)
    return output


def prototype_app():
    return restore_workspace() / "betawise/applets/BibleReader"


def prototype_test(name):
    return restore_workspace() / "betawise/tests/mame/asneo" / name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(restore_workspace(args.output))


if __name__ == "__main__":
    main()
