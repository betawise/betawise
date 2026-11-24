# Control Panel 1.7 static investigation

Inspected the newly extracted NEO Manager 3.9.3 ControlPanel.OS3KApp and
compared the older local Control Panel. This is static analysis of original
binary instructions and resource tables, not emulator/hardware qualification.
No user settings, flash, or saved sessions were changed; no display inference
was used. All offsets below are **applet-relative file offsets**, not ROM entry
points.

Input identities, the complete newer main-menu string table, and recognized
immediate/indexed syscall references are in [static-evidence.json](static-evidence.json).
Selected annotated instructions are in [disassembly.txt](disassembly.txt).

| Image | Version bytes | Bytes | SHA-256 |
|---|---|---:|---|
| Older `Ghidra/Alphasmart 3000/SmartApplets/ControlPanel.OS3KApp` | `01 00 31` (1.1) | 24264 | `37eb0e316503b1b2071aa5dced1700c69a028a79539f815e1a04c9b4c8fd74c1` |
| NEO Manager 3.9.3 extracted Control Panel | `01 00 37` (1.7) | 27412 | `503e2aaa9ebdb85b7a693d0c75f8e1687da6cef16411cc27d66915cbae28c3f6` |

Both identify as applet `A007`. Newer entry point is `1F30`; older is `1DB8`.

## Multi-user: profile-aware consumer, no recovered enable path

The newer main-menu table at `4D62` has 18 strings (title plus IDs 1–17).
Its constructor at `1A04` considers exactly IDs 1–17 and its action switch at
`1CC0` is bounded to those IDs. Neither that menu nor the AlphaWord submenu
contains a multi-user enable/disable option. The latter offers show marks,
file-password protection, changing an individual password, and resetting file
passwords. **File passwords are not the firmware profile-mode switch.**

Both versions nevertheless query the active profile through `A254`
(`FileGetUserName(0, NULL)`) when constructing the file-password chooser.
In 1.7, `12D0` obtains that service's address; `1312–1328` calls it, explicitly
zero-extends its low byte and passes it as the group to `FileResolveId`
(`A1FC`). The old equivalent address load is `12B6`. This is additional vendor
consumer evidence for the byte-return ABI and profile-aware enumeration.
It does not enable profiles or establish access isolation.

No recognized immediate/indexed reference to `A250` (FilePromptMasterPassword)
was found. Neither image contains an aligned absolute pointer to the known
AS3000/Neo 3.01/Neo 3.21 toggle or selector routine addresses from the
[multi-user investigation](../multi-user/README.md). This search and the menu
inspection do **not** rule out every computed/indirect route. The analyzed
SystemHandleEvents callers forward keyboard-settings/slow-keys/two-button-on
shortcuts or service printer events; no profile enable route was recovered.

The existing multi-user conclusion therefore stands: AS3000 qualification found
the fourth-profile creation mismatch and AlphaWord reopening another profile's
cached file. Control Panel does not supply a demonstrated fix or supported
switching lifecycle. Neo runtime behavior remains unqualified.

## Hidden factory diagnostics

On `MSG_SETFOCUS`, 1.7 calls ScanKeyboard/GetKeyModifiers and tests
`(modifiers & FC00) == C400` at `2068–208C`. With the repository's physical
modifier definitions this is **Ctrl + Command + left Shift**, with Option and
right Shift absent. Caps Lock is masked out. It sets applet RAM byte A5+3,
which gates menu ID 1, Diagnostics, at `1B72–1B82`. The old image has the same
`C400` comparison at `1ED2`. This is a launch/focus-time gate, not a newly
established ordinary key handler. The physical launch gesture has not been run.

The diagnostic constructor at `2C2A` installs function pointers with test names.
It includes A/D calibration, keypad, LED, LCD display, wireless, LCD RAM,
hub circuitry, USB printing, IR printing, and charge cut-off tests, conditioned
on platform/radio detection. Several other named tests are literal
"Not Implemented" stubs: names alone do not establish working diagnostics.
Test summaries can be sent to the clipboard.

## Better meanings for known system selectors

These are new **caller explanations**, not newly discovered syscall opcodes.
The binary includes a large consecutive syscall-stub bank: finding an A-line
word in that bank alone does not mean Control Panel uses it. The JSON lists
recognized references separately and does not claim an exhaustive call graph.

| Service | Concrete Control Panel evidence |
|---|---|
| `A2B8`, selector `0900` | Gates Search For Networks, About NEO 2, Wireless Security (`1B86–1BD8`) and Test Wireless (`2D46–2D94`). This is radio detection/capability usage, distinct from GetHardwareRevision. |
| `A2B8`, selector `0B00` | Search For Networks invokes it before installing a WirelessBeginAssociation callback (`1DE0–1E0A`). Supports the existing asynchronous connection-flow interpretation. |
| `A2B8`, selector `0C00` | Wireless Security passes its 13-byte NUL-terminated input buffer (`2292–22A2`). The UI says Enter Encryption Key / 0 to Disable. This establishes a wireless-security-key use for the formerly opaque block. It does not establish cipher, key decoding, radio acknowledgement, or successful association. |
| `A2B8`, selector `A000` | Factory LCD procedure passes a signed trim after checking erased flash bytes `4003F4/5`, then restores normal contrast to 43 (`36B4–3780`). With marker `Y`, it displays the signed stored trim (`378A–37B6`). This gives direct vendor intent for the existing ROM-derived contrast-bias interpretation. Persistence remains untested here. |
| `A134`, selectors 41/42 | A/D diagnostic reads existing calibration, runs calibration and rereads it (`3134`, `32C2`, `32D6`). Consistent with existing battery research; no new public ABI needed. |

One possible vendor UI defect: the security input helper at `2494` checks
characters against the literal **`abcde1234567890`** at `4BD2`. There is no `f`
or uppercase letter in that literal. The path translates input and uses
FindStringChar before appending it (`2472–24C6`). This deserves a deterministic
native-key test before claiming exactly which keys the shipped UI accepts;
it is not a basis for asserting the radio's actual key format.

## Hardware clues useful to emulator work

The LCD RAM diagnostic at `3B2E` directly programs **both** controller windows:
`01008000/1` and `01000000/1`. It iterates eight pages with commands `B0|page`,
`10`, `00`, writes 132 incrementing bytes per page per controller, then
resets addressing and performs a dummy data read before comparing 132 bytes.
The byte pattern continues across pages/controllers with byte wrap. It counts
mismatches and returns diagnostic status 2 or 3. This independently supports
dual 132-column controllers, page addressing, and pipelined/dummy-read behavior.
It is a strong candidate for a disposable-state deterministic emulator test;
no live pass is claimed here.

The LCD display diagnostic additionally tests full black/blank and stripe
patterns. Its trim setup repeats the `C400` modifier gate at `36A2–36AE`.
The wireless factory test at `3D4C` sends the NUL-terminated name
`NEO 2 Factory Test` using packet type `0300` and argument 3, then polls
WirelessReceivePacket. This is useful protocol caller evidence, not proof that
an arbitrary access point or emulator radio can satisfy the factory protocol.

## Rechecking the static evidence

GNU binutils can disassemble either source directly without installing it:

```sh
m68k-linux-gnu-objdump -D -b binary -m m68k:68000 /path/to/ControlPanel.OS3KApp
```

The vendor compiler uses `movea.l #displacement,An` followed by a full-extension
PC-indexed call/address load with displacement -2. For the adjacent sequences
recorded here, target = indexed instruction offset + immediate displacement.
The instruction's PC base and -2 cancel; do not use the end of the instruction
as the base. Syscall names were cross-checked with `abi-audit/slots.tsv`.
Data and the embedded stub bank must not be mistaken for executing code.
Future execution checks must use disposable flash/RAM and the workspace's
deterministic LCD rules; no Neo menu font was validated by this static work.
