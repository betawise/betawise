# Private font face: message 7

`MSG_FONT_GET_PRIVATE = 0x01000007` follows the normal font-getter ABI: param
points to writable `const FontHeader_t *` storage, and the provider writes a
stable descriptor or NULL. Status is zero. The font uses the version-1 shared
`os3k/charsets/neo-smallcaps.json` encoding (three letter styles plus superior
digits), and has the same cell height as the four body faces. It is not an
additional native editor style bit. A viewer explicitly installs/uses it.

All 16 AFF0–AFFF reader providers return the private descriptor. BetaWise
Terminal returns NULL. A caller initializes its result to NULL before querying
another font provider and uses its normal fallback when no private face is
returned. The query may be sent with low code 7 through AppletSendMessage,
which supplies the synthetic high flag just as for the standard queries.

## Existing provider compatibility

`probe-font-extension.py OUTPUT` inventories every C0FFEEAD font-flagged
.OS3KApp under the workspace Ghidra tree and executes each distinct original
binary on m68000 QEMU. It invokes the actual entry offset with a separate A5
RAM area, valid writable parameter/status pointers, and surrounding canaries.
Both NULL and 12345678 output sentinels are tested.

**26 files, 21 distinct binaries:** every provider writes NULL and status zero
for 01000007, with intact canaries. This includes the five vendor sizes across
archived releases and all eleven NeoFonts community providers. Results are in
[font-extension-providers.json](font-extension-providers.json), with paths and
per-binary outcomes. Stock dispatch checks 1, 2 and 6 and explicitly clears
pointer output for other synthetic queries. Its common descriptor initialization
can still run before that default branch.

This is evidence for the inventoried external providers, not an assertion about
unknown future applets or ROM built-in descriptors without provider callbacks.
Initializing the output remains necessary. Status alone is not a capability
flag: unsupported and supported queries both return status zero.

An initial fixture linked host libc, whose startup instructions were unsuitable
for a 68000-only QEMU CPU and caused emulator failures before reaching the
handlers. The passing fixture uses a freestanding assembly entry/write syscall,
with no libc. Both runs remain in `.research-work/font-extension-probe*`.
