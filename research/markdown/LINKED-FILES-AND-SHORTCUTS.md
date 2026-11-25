# Linked forms and AlphaWord service shortcuts

Original-code follow-up, 2026-11-21. Scope: the AlphaWord and Neo 3.21 hashes in
`images.json`. Manufacturer binaries are not patched. Instruction addresses
below are offsets in `alphawordplus.os3kapp.bin`, excluding its OS3KApp header.

## Linked files: embedded forms and a separate renderer

The visible effect resembles alternating two text views. Implementation is an
embedded form and a switch between native editor and form-renderer state, rather
than applying hidden/protected flags to the two halves of the ordinary text.

* Main editor state is at AlphaWord A5+12; form state is at A5+70. The linked-view
  byte is A5+137. These offsets are private and version-pinned.
* Main-view Ctrl+L dispatch at 17DC..1846 calls the TextFormInit stub at 12E56
  (A2F0, slot 188), then TextFormHandleMessage at 12E58 (A2F4, slot 189), and
  enables linked-view routing. The next Ctrl+L clears the view byte at ED0..EE0
  and returns to the normal editor path. No bulk B1/B2 visibility rewrite is
  performed by these toggle branches.
* Native text-scanner experiments under `research/syscalls/text` established the
  embedded form envelope `A8 <FORM>...</FORM> 9D` on this Neo. Ordinary plain
  scanning skips it; explicit form expansion appends its converted form output.
  This is a distinct native token, not region bit 01. The AS3000 terminator differs.
* Initial form parsing can normalize content and append FORMDATA, so a first
  initialization should not be described as a guaranteed byte-preserving operation.
* Ordinary body text is read-only, while form controls can be interactive.
  The maintained original-code tests include a TEXT input initialized to hello,
  changed to Q in its generated FORMDATA. The documented linked-file UI also
  permits checking/clearing checkboxes. Do not equate body read-only semantics
  with setting the whole region's native protected bit 02.

The AlphaWord importer/normalizer at 3F8C recognizes FORM pairs, normalizes
newlines to BR, escapes unsupported markup and expands []/[ ]/[x] forms into
native input markup. This is a restricted form dialect, not general HTML.

Primary documentation:
[NEO 1/2 User Manual, linked files pp. 48–50](https://uk.renaissance.com/wp-content/uploads/2010/12/neo-user-manual.pdf).
The manual documents Ctrl+L, read-only body text, form tags and checkbox behavior.
The native syscall evidence, test inputs and exact expected FORMDATA are in
[the text API investigation](../syscalls/text/README.md).

## Ctrl+B and Ctrl+Send

These are hard-coded service requests, not an arbitrary-app hotkey registry:

| Shortcut | Lookup | Request |
| --- | --- | --- |
| Ctrl+B | AppletFindById(A006), Beamer | message 3, param 0: receive |
| Ctrl+Send | AppletFindById(A006), Beamer | message 1, param 0: send current file |
| Command+Send | A026, Wireless File Transfer | wireless send protocol |
| Command+O | A026, Wireless File Transfer | wireless open protocol |

The retained AlphaWord image also looks up A005 (SpellCheck) and A017 (Thesaurus),
with corresponding services reachable through spelling keys and Ctrl+T. Its two
name-prefix lookups are CoWriter and Wireless File Transfer. No configurable
arbitrary-app shortcut setting was identified in this image; the Applets menu is
the general user-facing chooser. These findings do not exhaust every global ROM
keyboard service in other versions.

Ctrl+B's main and linked-view branches call 5992. That function:

1. Calls the A23C AppletFindById stub at 12DFC with ID A006.
2. Saves native editor position via 12E4E (TextEditorSavePosition).
3. Calls the A244 AppletSendMessage stub at 12E00 with `(index, 3, 0, &reply)`.
4. Reconciles/redraws AlphaWord after the call returns. Reply zero takes the
   successful-receive reopen path; nonzero avoids treating the callback as a
   completed receive operation.

The SDK dispatcher adds 01000000, so the recipient sees 01000003. Send's
corresponding request is 01000001. **Its reply is a normal four-byte status**,
not the ten-byte CoWriter control record. Reusing the CoWriter handler ABI here
would overwrite caller storage.

The adjacent two-byte trap stubs confuse Ghidra's function-boundary recovery:
its decompiler sometimes labels a call to 12DFC as FUN_12DFA. The operand sums
and trap opcode establish ID lookup; the name lookup trap is the different A238.
Do not decide this question from decompiler function labels alone.

## Executed hidden Beamer-hook probe

`BeamerHookProbe.c` builds a hidden A006 applet named **Markdown Hook Probe**.
A disposable image contains original AlphaWord, the font, and this probe, with
**no CoWriter companion**. Physical Ctrl+B and Ctrl+Send both reached it with the
messages above and param zero. Source and exact LCD contents remained `source`.
The probe returns reply 1 to avoid claiming a successful IR receive. It sends no
infrared data and implements no Markdown preview.

```sh
python3 betawise/research/markdown/check-editor.py --live --case shortcuts \
  --output /tmp/neo-hook-new
```

This confirms that hidden status and a different display name do not prevent the
ID-based hook. Expected source, exact independent font bitmap, cursor geometry,
three identical cursor-free LCD records, message/parameter and absence of a
CoWriter registration are asserted. It does not certify real Beamer transfers
or a completed preview applet.

An optional A006 shim can synchronously run a viewer or dispatch to applet FF11,
then return to AlphaWord. This avoids taking CoWriter's name-based registration. Concurrent key forwarding with genuine active CoWriter
has not been certified. It conflicts with
real Beamer's ID: both cannot be installed as independent A006 applets. A modal
callback is the immediate demonstrated entry mechanism, not automatic switching
the system's active applet to any arbitrary ID. A production shim needs a defined
return contract, bounded viewer state and tested cancellation/return behavior.
The standard inline build continues to use its CoWriter hook; it has not been
silently changed to replace Beamer.

## Font choice for code

Single-backtick spans and backtick fences can be recognized and kept literal
using the regular face. Syntax recognition consumes no extra font slot. A
visually distinct monospace face does require a slot under the native editor's
four-face mechanism. Reasonable explicit modes are regular/bold/italic/combined
or regular/bold/italic/mono, with a specified combined-emphasis fallback in the
latter. Neither mono mode nor fallback has been implemented in this revision.
A custom preview renderer is not constrained by the native editor's four slots.

No representative usage counts for combined emphasis versus monospace were
established. Their value depends on prose versus technical writing; documentation
of the syntax is not evidence of its population frequency.

The maintained hook package now uses private ID FF14. Only the disposable
compatibility fixture aliases its installed copy to Beamer A006 for the original
AlphaWord lookup; it records both identities and preserves the private package.
