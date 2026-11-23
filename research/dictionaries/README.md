# Dictionary and Thesaurus services

Original applets expose three different protocols. Thesaurus is a callable
synonym/antonym service as well as a UI; SpellCheck has its own service; the two
CoWriter dictionary applets supply borrowed data blobs. Their overlapping message
numbers do **not** make them interchangeable providers.

Source identities and SHA-256 hashes are in
[the vendor inventory](../abi-audit/vendor-image-inventory.json). Offsets below
are image-relative, from the original USA Thesaurus and SpellCheck binaries.
Native verification executes the original applet instructions under the Neo ROM
3.21 dispatcher, using disposable RAM and emulator configuration. This qualifies
the service path, not each applet's UI or historical AS3000 ROM compatibility.
The nine final runs passed 160 API cases. See
[the captured run summary](results-summary.json).

## Dispatch and replies

`AppletSendMessage(index, selector, param, reply)` adds bit 24 to the delivered
message. The low selectors below are what callers pass; `Message_e` aliases
include that synthetic bit. The dispatcher preserves the caller's A5 and selects
the provider's A5. Initialize the provider before using its stateful service.
The probes invoke native message `0x18` for initialization.

Thesaurus and SpellCheck write a **four-byte status word**. The CW providers
write **eight bytes** for their data query; allocating a normal four-byte status
variable would corrupt adjacent memory. A successful transport return is separate
from the provider status. See also [the dispatch audit](../syscalls/applet/dispatch-audit.md).

All layouts here are big endian with 32-bit pointers and native **two-byte
alignment**. Do not use a host compiler's default pointer size/alignment. Counts,
capacities, and lengths have different widths and units; negative capacities are
not qualified inputs. Output records and borrowed pointers remain provider data,
not portable serialized objects.

## Thesaurus: selectors 0–6

All six inventoried Small/Large USA and Spanish-to-English binaries use entry
`0x3D8`, dispatcher `0x45C`, and this same request packing. Selector 0 searches
member words, so the returned headword need not equal the query. English `happy`
returns the groups headed by `pleasant` and `cheerful`. Spanish `feliz` returns a
group containing `feliz` and `happy`.

| Selector | Operation | Parameter and four-byte reply |
|---|---|---|
| 0 | Find groups containing a word | 16-byte lookup request; status 1 if complete, 0 if truncated; zero matches is a complete result |
| 1 | Enumerate a group | 6-byte request; status 1 if valid, 0 out of range, leaving output unchanged |
| 2 | Number of groups | Param ignored; signed 16-bit count promoted to status; not a word count or latest search count |
| 3 | Copy group headword | 14-byte request; status 1 complete, 0 truncated; **no NUL appended** |
| 4 | Read word class | Param points directly to a 10-byte entry; signed byte at entry+8 promoted to status |
| 5 | Copy related words | 16-byte request; status 1 complete, 0 truncated; count is **words**, not bytes |
| 6 | Find linked antonym group | 8-byte request; status 1 found, 0 absent; absent link copies the original entry into output |

Selector 0 lookup request:

| Offset | Type | Meaning |
|---|---|---|
| +0 | pointer | Input bytes |
| +4 | signed byte | Input length, qualified range 0–50 |
| +5 | byte | Alignment padding |
| +6 | pointer | Output array of 10-byte entries |
| +10 | signed 16-bit | Capacity in entries |
| +12 | pointer | Output signed 16-bit entry count |

The implementation copies the input to a local buffer and terminates it itself.
Length 51 returns complete/zero matches. Capacity zero for a matching word returns
truncated/zero copied entries. These observations do not establish general
null-pointer safety or validation of malformed records.

Selector 1: signed 16-bit group index at +0, output-entry pointer at +2.
Indices are group ordinals. Neo Small has 5,747 groups; Neo Large has 5,779;
Spanish-to-English has 4,300. The older AS3000 Large image has 5,748 groups
(and its Small image has 5,747), so do not hard-code the Neo Large count for
all Large editions. Selector 2 remains unchanged after a lookup.

Selector 3: entry pointer +0, output character buffer +4, signed byte capacity
+8, padding +9, pointer to output byte length +10. Use a capacity at most 127;
allocate another byte and append your own NUL if needed. A three-byte capacity
copies three bytes, reports length three, returns zero, and leaves the next byte
unchanged.

Selector 5: entry pointer +0, output buffer +4, signed 16-bit byte capacity +8,
pointer to output signed 16-bit **word count** +10, delimiter byte +14, padding
+15. It emits the headword and related terms, with a delimiter after **every**
word, including the last. Delimiter zero gives NUL-separated strings. Truncation
occurs at whole-word boundaries. Capacity zero returns zero status/count and
leaves the buffer unchanged. The list can contain the original query itself.

Selector 6: source-entry pointer +0, destination-entry pointer +4. Check status:
a nonempty output is not evidence that an antonym was found. English examples
include `pleasant` → `disagreeable`, and `cheerful` → `dejected`. The Spanish
`feliz` group has no link and returns an unchanged copy with status zero.

### Entries and underlying groups

A copied entry contains uint32 group-stream byte offset at +0, uint32 headword ID
at +4 (a zero-extended 16-bit ID), and signed byte word class at +8. Byte +9 is
padding/uninitialized data: do not interpret or compare it. Pass entries back to
the same live provider. Class 2 occurs for the adjective examples above; a full
numeric part-of-speech mapping has not been qualified.

Internally a group is BE16 headword ID, class byte, BE16 antonym ID, byte number
of additional terms, then that many BE16 word IDs: stride `6 + 2*n`. Headword ID
zero terminates the stream; antonym ID zero means no link. Selector 5 emits the
headword as well as those additional IDs. These IDs are dictionary-local, not
character codes or pronunciation data.

`check-group-streams.py` independently walks the original bytes using the
stream offsets recorded by the native probes and verifies all six group counts.
Both Spanish-to-English streams have zero linked-antonym fields; the English
streams contain 3,821 linked groups, or 3,834 in Neo Large. These are counts of
links/groups, not distinct words or antonym pairs.

Static paths: selector 0 `0x94` → member lookup `0x3BDE`; selector 1 `0x1A0` →
stream walk `0x3884`; count `0x3920`; headword wrapper `0x1F2`; class `0x3DCC`;
related terms `0x363C`; antonyms `0x372E`. Antonym lookup reads the group field
at +3, rather than advancing to the next enumeration entry.

## CW_MainDictionary and CW_Topics

Applet IDs are `0x9000` and `0x9001`. Selector 1 writes `image+0x106` through the
parameter pointer, and writes `{ uint32_t status=0; void *data; }` to the reply.
The blobs start with `@AlphaROM@` and `@TopicROM@` respectively. This is a borrowed
blob pointer API, not a public word-search, synonym, or pronunciation API.

Both entry points are `0x94`. CoWriter's consumer at `0x13D78` finds each applet
by ID, sends selector 1, and consumes the **second reply field**, independently
corroborating the eight-byte result. The providers need four bytes of applet RAM.
Unsupported selector 2 clears the first status word and leaves param and the
second reply field unchanged; zero status alone cannot identify supported calls.
The proprietary blob format and phonetic content remain unqualified.

## SpellCheck: selectors 1–7, not 0–6

The USA entry is `0x33B2`, handler `0x35D2`, jump table `0x360E`. Its seven-way
table subtracts **one** from the selector before indexing. The earlier broad
message inventory's 0–6 range was incorrect.

Every request is five 32-bit fields: input length +0, input pointer +4, output
byte capacity +8, output byte length +12, output pointer +16. Reply is four bytes.

| Selector | Decoded behavior | Qualification |
|---|---|---|
| 1 | Check input; one output result byte | Native `cat` → `00`, `qzxqzx` → `FF`; status 0, length 1. Full result-byte codebook unresolved |
| 2 | Suggestion-related operation returning a pointer-sized value, length 4 | Static only; exploratory native call timed out, so ownership and valid calling state remain unresolved |
| 3 | Interactive check when enabled; disabled returns byte `0C` | Only disabled branch runtime qualified; status 0, length 1 |
| 4 | Side-effecting action at `0x3DDE`; status `0D`, length 0 | Static only; purpose unresolved; do not expose as a named user operation |
| 5 | Enable interactive processing | Native verified, status 0 |
| 6 | Disable interactive processing | Native verified, status 0 |
| 7 | Read enable flag | One byte 0/1, status 0, length 1 |

Unsupported selector 0 returns status 1/length 0. Static capacity checks return
status 2/length 0 if insufficient (one byte for 1/3/7, four bytes for 2).
Neither a SpellCheck suggestion pointer nor a Thesaurus group entry is a CW
blob pointer. No tested service supplies pronunciation or rhyme matches.

## Reproduce and inspect evidence

Run from the workspace root, with locally inventoried vendor images and built
`mame/neodiag` available:

```sh
python3 betawise/research/dictionaries/check-group-streams.py
python3 betawise/research/dictionaries/run-probe.py /tmp/thesaurus-probe
python3 betawise/research/dictionaries/run-probe.py /tmp/spanish-probe --image 'Ghidra/Alphasmart 3000/SmartApplets/ThesaurusSpanishtoEng.OS3KApp' --word feliz
```

Use a **new output directory** for each run. The runner verifies image hashes,
uses disposable flash/config/NVRAM and RAM-injected applets, then preserves
`manifest.json`, `results.json`, the generated Lua, and `mame.log`. Bounded
instruction-return predicates replace timing sleeps. Assertions cover caller A5,
stack, RAM and reply guards, output boundaries, explicit expected headwords and
operation-specific edge results. There is no screen/model test oracle.

Local raw evidence is under `.research-work/dictionary-thesaurus/`, including
Ghidra logs and native runs. Failed exploratory runs are retained: `small-probe`
used an unsuitable boot predicate; `small-probe-native` lacked a dispatcher return
frame; `spell-small-api` timed out in selector 2. `small-opposites` reused an
antonym buffer and is superseded by runs with separate output records. These are
not positive qualification results. Original vendor binaries and generated
corpus data are not redistributed in this directory.

See [rhyming dictionary feasibility](rhyming-dictionary.md) for the separate
pronunciation-index experiment and its limits.
