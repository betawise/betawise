# Betawise local private applet IDs

These are local choices within the registry's unregistered private-use range,
not public assignments or globally unique IDs. Keep distinct IDs for fixtures
that we build/install together. Do not use `0xFFFF`. Historical evidence retains
its original header IDs/hashes; rebuild a fixture to obtain its private ID.

| ID | Local applet / fixture | Source |
| --- | --- | --- |
| `0xFF01` | QEMU applet | [source](../tests/qemu/test.c) |
| `0xFF02` | Incomplete font dialog demo | [source](../research/syscalls/dialog/demo/FontDialogDemo.c) |
| `0xFF03` | Flash probe | [source](../research/flash-b3/FlashProbe.c) |
| `0xFF10` | Markdown editor probe | [source](../research/markdown/EditorProbe.c) |
| `0xFF11` | Live Markdown probe | [source](../research/markdown/EditorProbe.c) |
| `0xFF12` | Bitmap font probe | [source](../research/markdown/FontProbe.c) |
| `0xFF13` | Markdown font | [source](../research/markdown/MarkdownFont.c) |
| `0xFF14` | Beamer hook probe | [source](../research/markdown/EditorProbe.c) |
| `0xFF20` | Bible codec benchmark | [source](../research/bible-reader/prototype/Benchmark.c) |
| `0xFF21` | Archived native Bible reader | [source](../research/bible-reader/prototype/BibleReader.c) |
| `0xFF22` | Archived streaming Bible reader | [source](../research/bible-reader/prototype/Streaming.c) |
| `0xFF23` | Before-native-text-box sidebar prototype | [source](../research/bible-reader/sidebar-prototype/BeforeNativeTextBox.c) |
| `0xFF24` | Before-sidebar prototype | [source](../research/bible-reader/sidebar-prototype/BeforeSidebar.c) |
| `0xFF25` | Formatting speed guest | [source](../research/bible-reader/formatting/speed/BenchGuest.c) |
| `0xFF26` | Soft hyphen probe | [source](../research/bible-reader/soft-hyphen/SoftHyphen.c) |
| `0xFF30` | Century Schoolbook test font | [source](../research/bible-reader/reader-fonts/build.py) |
| `0xFF31` | Helvetica test font | [source](../research/bible-reader/reader-fonts/build.py) |
| `0xFF32` | Times test font | [source](../research/bible-reader/reader-fonts/build.py) |
| `0xFF40` | Manager initial applet 1 | [source](../research/memory-allocation/manager/run.py) |
| `0xFF41` | Manager initial applet 2 | [source](../research/memory-allocation/manager/run.py) |
| `0xFF42` | Manager installed applet 3 | [source](../research/memory-allocation/manager/run.py) |
| `0xFF43` | Manager RAM-loader applet | [source](../research/memory-allocation/manager/run.py) |
| `0xFF44` | Shared-library vector RAM applet | [source](../research/flash-b3/shared-library-init/vector-run.py) |
| `0xFF50` | Lifecycle applet 1 | [source](../research/memory-allocation/lifecycle-probe.lua) |
| `0xFF51` | Lifecycle applet 2 | [source](../research/memory-allocation/lifecycle-probe.lua) |

The Beamer hook's built header is FF14. Its optional compatibility test changes
only the disposable copy to the original Beamer ID A006, because AlphaWord's
original lookup requires that identity; it does not claim/register A006 for us.
Normal Markdown builds use FF10/FF11 and distinct FF12/FF13 font lookups.

Production applets and normal production resources remain in [APPLETS.md](APPLETS.md).
A-line syscall opcodes, file IDs and RAM test markers are separate namespaces.

A fixture that needs an impersonated header directly may mark it with a comment
such as `APPLET_ID_IMPERSONATION: 0xA006`, explaining the tested contract.
The source ID audit exempts that intentional declaration from local assignment
and uniqueness rules. This does not register or claim the impersonated ID.
