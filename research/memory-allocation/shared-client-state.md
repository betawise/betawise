# Shared-service client identity and native per-slot file state

Binary inspection, 2026-11-23. This follow-up uses the original Neo 3.21
instruction listing, not archived firmware source. No new runtime test or
F-line handler implementation is claimed.

## Native table at 0x0FD2

The table has 32 eight-byte records, indexed by applet slot. It belongs to
the native file subsystem, not an extensible applet-private-data facility.
The reconstructed layout (68000, big endian, two-byte structure alignment) is:

```c
struct NativeAppletFiles {
    FileInfo_t *first;       /* +0: first contiguous 0x48-byte file record */
    uint8_t count;           /* +4: number of records in this applet group */
    uint8_t cached_index;    /* +5: zero-based record index, 0xFF invalid */
    uint16_t cached_id;      /* +6: full native file identity of cached record */
};
```

Instruction evidence in Neo 3.21:

- 439D7C..439D90 initializes pointer/count to zero, index to FF, ID to zero.
  439DFE..439E18 invalidates index/ID on the retained-directory startup path.
- 43AAB2..43ABAE creates a group: writes first pointer at 43AAD2, advances
  records by 48 hex, then writes count, FF index and zero ID at 43AB94..43ABA0.
- FileOpen (43A876) obtains a resolved full ID and record pointer, writes ID
  at 43A8C8 and index=(record-first)/0x48 at 43A8CC..43A8E2.
- Resolver 43C488..43C4BE uses cached index to obtain a record and compares
  its +44 identity with cached ID. 43C52A..43C558 compares requested ID,
  cached ID and record ID before accepting the cached record.
- 43C75E..43C772 returns the selected file group's count byte.
- Group removal 43ABB0..43AD2C relocates following 0x48-byte file records,
  fixes matching group pointers at 43AC7A..43AC96, then clears pointer/count
  and invalidates cached index at 43AD10..43AD18.
- Individual deletion decrements count and clears lookup cache at
  43B2A0..43B2C8. File insertion adjusts group pointers at 43AFDC..43B018.
- Startup applet-slot compaction copies both longs of this eight-byte record
  at 417312..41732C and zeros the vacated final record at 417362..417374.

The full cached ID is not necessarily an applet-local file number: file
resolution also accounts for native user/group encoding. No field is spare.
Older resolver fixtures use 0F42 for AS3000 and 0FD2 for Neo 3.01; this new
field trace specifically qualifies Neo 3.21 and does not claim a fresh
three-ROM execution.

## F-line caller identity

An F-line exception does not itself replace A5. A proposed assembly entry
must save incoming A5 before switching to BetaWise A5 to execute C code.
Registration can record the client's current assigned A5 and applet slot.
An exact incoming-A5 lookup among registered clients identifies a normal
SDK caller without passing a handle or slot on every call. Require a unique,
nonzero registered base; reject unknown or ambiguous matches. Applets with
no distinct A5 allocation need an explicit identity alternative.

Neo 3.21 AppletSendMessage at 439C60 saves 35E2 at 439C72, writes the target
slot at 439CB6, switches A5 via 410094, invokes the callback at 439CF2, restores
A5 and restores 35E2 at 439D00. Thus 35E2 is a useful candidate/check for
normal dispatched calls, but it is target identity after crossing a message
boundary. The file-folder selector 35EC and separately selected identity
context are not substitutes for calling-client identity.

A future F-line implementation can try validated dispatch-slot plus exact
A5 comparison first, then a bounded registered-client search. Do not assume
foreground identity covers nested provider calls or asynchronous callbacks.
Shared-internal recursion needs an explicit rule and per-invocation saved
caller state. Identification must precede switching A5; restore A5 on return.

This is a calling-convention proposal, not protection against malicious
applets. F-line vector installation/chaining, saved-PC handling, register
preservation, callback/reentrancy behavior and reset lifecycle still need
execution tests before adopting the trap ABI. No screen/model oracle is used.

Retention: the compact results-summary.json and topic tables retain outcomes.
Raw captures, generated probe copies and logs named above describe historical
output locations; regenerate them with the documented runner in a fresh
directory and pass that directory to the verifier. They are not repository inputs.
