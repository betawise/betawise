# USB ownership and a cross-ROM shutdown candidate

**Later execution evidence:** [focus ownership](focus-ownership.md) now tests callback replacement and focus-scoped mass storage in the Neo emulator. The static scope and historical limitations below describe this earlier pass.

This is a bounded static follow-up to [native USB](native-usb.md). It does not
claim an exclusive-ownership API has been found or executed. In particular,
controller shutdown and disabling all future ROM USB servicing are different
contracts. No physical cable, screen or user-saved RAM was used in this audit.

## What the EhBASIC observation supports

On Neo 3.21, `SystemHandleEvents` (`A25C`, target `418794`) reaches the external
connection workflow through mask bit 4 and helper `417d0e`. A detected USB
connection enters keyboard loop `41ca36`, which emits the applet's `300xx`
messages. That loop polls controller status through `41fe4a` and explicitly
calls device dispatcher `440064`. The status check can read and consume chip
state, not just inspect an applet message queue.

Thus no event-loop call is consistent with no attachment UI/app callbacks.
It does not prove no electrical interrupt, no CPU interrupt, or a queued
`30001` waiting for an application. At the traced sites those applet messages
are synchronous calls generated after entering the native workflow.
Other event handlers and API-internal event pumping must still be audited;
excluding bit 4 is not certified here as a global USB ownership lock.

The ROM also registers `41ff82` as a callback for CPU interrupt source mask
`00100000` (`41db04`–`41db1c`). That callback dispatches to the old/new USB host
backends (`41eb8e` / `45239a`); the newer backend reads/acknowledges host-controller
interrupt register `d4`. This is an independent servicing path, though not proof
that every device-controller event reaches the same ROM code.

## The useful signature

A full 46-byte wrapper, with only relocated call/global operands masked, matches
exactly once in **each inventoried Neo main ROM**:

| ROM | Shutdown wrapper | Controller backend | USB state words cleared |
|---|---|---|---|
| Neo 3.01 | `005e7db4` | `005e792e` | `5960`, `595e` |
| Neo 3.21 | `0044044e` | `0041fb5e` | `13d04`, `13d02` |
| AS3000 3.01 | **No match** | Different implementation; not qualified | — |

The structure is:

```asm
move.l d7,-(sp)
jsr controller_shutdown
jsr save_sr_and_mask
move.w d0,d7
clr.w usb_state_word_1
clr.w usb_state_word_2
moveq #0,d0
move.w d7,d0
move.l d0,-(sp)
jsr restore_sr
addq.l #4,sp
move.l (sp)+,d7
rts
```

The interrupt masking protects the state-word updates and then **restores** the
previous SR. It does not leave all CPU interrupts disabled.

Neo 3.01 directly invokes its older controller shutdown. Neo 3.21's backend
selects one of two implementations from hardware revision state. In the newer
backend, `45183c` calls `41fa3c` (its selected implementation `4516a4` clears bit
3 of controller Mode register `0c`), then resets/reconfigures controller state.
It also invokes board GPIO/power handling; do not describe the entire routine
as merely “disable interrupts.” The older backend writes its own controller
commands and changes GPIO. These paths deserve hardware-specific qualification.

The wrapper **does not visibly** remove the callback registered by `420104`,
mask its CPU source using `4201f6`, or change the public event-handler dispatch.
After a new driver re-enables the controller, that existing software ownership
has not automatically disappeared. It is a useful initial quiesce/reset
candidate, not a permanent “OS hands USB to this applet” operation.

## How a qualified takeover would use it

The intended contract should be explicit: acquire USB, run our driver, then
release it to the ROM. A proposed implementation would:

1. Enter a short critical section and save the relevant interrupt routing/masks
   and controller ownership state.
2. Quiesce/reset using a positively identified ROM wrapper, if its behavior is
   qualified for that ROM/hardware combination.
3. Keep ROM USB interrupt servicing excluded while our driver owns the chip.
   For a polling driver, keep the relevant chip interrupt sources disabled;
   for an interrupt driver, establish exclusive routing before enabling them.
4. Exclude native USB event-loop entry and API paths that internally service USB.
5. On release, disconnect our personality, quiesce our transfers, and restore the
   ROM's routing/state through a separately qualified recovery path.

On Neo 3.21, private `4201f6(mask)` sets bits in CPU IMR `fffff304` and clears
pending bits; `420164(mask)` clears IMR bits. Both recognize source `00100000`.
They are candidate building blocks, not a validated paired acquire/release API.
Masking CPU interrupts alone cannot prevent a later explicit ROM polling call.
Conversely, leaving the applet event loop does not unregister a CPU callback.

A reusable resolver must fail closed on no/ambiguous match and validate the
callee graph, ROM bounds, hardware backend and effects. A unique byte pattern
is useful discovery evidence, not sufficient behavioral certification. A small
set of verified signatures per ROM family is preferable to a broad “universal”
pattern or a guessed fallback address.

## Reproduction and remaining acceptance work

From workspace root:

```sh
python3 betawise/research/usb/find-usb-shutdown.py
```

The scanner hash-checks all three shared-inventory main ROM images, matches the
complete wrapper shape, and validates adjacent state words, paired SR helpers
and callee bounds. It finds one candidate in each Neo main ROM and none in
AS3000. Small ROM and unprovided firmware releases are not covered.

Raw disassemblies, hash-checked signature results and fresh Neo 3.21 Ghidra
inspection are preserved in workspace `.research-work/usb-ownership/evidence`.
The existing main-ROM inventory supplies input paths/hashes.

To call this **solid exclusive ownership**, the next tests must observe both
controller accesses and ROM callback entry while an EhBASIC-style applet is
running: attach, detach, reset and transfer events; no event pump versus selected
OS calls; mask/reset/takeover; and restoration. Use disposable state, exact
register/RAM assertions and bounded predicates. Each supported ROM/controller
combination needs execution coverage. No such takeover test was run in this
bounded static pass, and the candidate is not exported as a public API.
