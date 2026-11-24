# Neo USB interrupt callback and focus ownership

This follow-up narrows the earlier [ownership investigation](ownership.md). A disposable m68k prototype now passes callback replacement, interrupt-driven mass-storage reads, and focus/kill-focus restoration in MAME. These are Neo 3.21 findings, not a cross-ROM API contract or physical-device qualification.

## Callback mechanism

| Neo 3.21 address | Observed contract |
|---|---|
| `420006` | Maps a recognized source mask to a callback-table index. `00100000` maps to index 7. |
| `420104(mask, fn)` | Registers a callback only in an empty slot; returns zero on success, `-203` if already occupied. |
| `4200a6(mask)` | Clears an occupied slot; returns zero on success, `-202` if empty. |
| `420164(mask)` | Unmasks the recognized CPU interrupt source. |
| `4201f6(mask)` | Masks it and clears selected pending state. |
| `4203c4` | Real level-5 interrupt wrapper: checks ISR bit 20, calls the function in `48b6` with no arguments, restores registers and executes RTE. |
| `41ff82` | Stock callback: selects older backend `41eb8e` or later backend `45239a`. |
| `45239a` | Later host-controller handler: reads/acknowledges HC interrupt status at D4, inspects HC enable D6 and processes host completions. It does not provide a peripheral SETUP callback. |

The four registration/masking targets above are absent from the 285-entry public syscall table. They are private ROM routines. The callback table is initialized at `489a`; slot 7 is `48b6`. The prototype reads that slot to save the existing handler, then uses the ROM routines to remove/register/restore it. It does not silently overwrite an occupied slot or replace the CPU exception vector.

The callback uses an ordinary C RTS return, not RTE; the ROM wrapper owns the exception frame. The prototype ISR uses only caller-clobbered registers, reads and acknowledges device interrupt status, and ORs events into a volatile queue. Foreground code removes queued events in a short critical section and processes USB outside the ISR. Absolute globals avoid depending on the interrupted applet's A5. Arbitrary callbacks with another ABI or A5-dependent data require an adapter.

## Execution evidence

The replaceable experiment is at workspace `.research-work/neo-msc-focus`; its README has exact commands and limitations. `runs/events-v5/results.json` is PASS. The runner hash-checks main ROM `32fe55bb50c1b58326bd303f14973b8402ddf8bf6662b210e4d5e9f931c7e6c0` and uses disposable RAM/flash/NVRAM without evaluating screens.

A controlled baseline enables peripheral VBUS interrupts and injects attachment with the stock callback registered. It observes repeated entry through the real ROM level-5 wrapper and stock callback, while device IRQ bit 80 remains pending. The harness disables/acknowledges that deliberately unserviced event. Early boot has not necessarily registered the stock handler yet, so the C bootstrap registers `41ff82` through the actual ROM registration routine if the slot is empty. This is a controlled callback fixture, not an assertion that early native boot enables peripheral interrupts.

The custom handler then passes two SetFocus/KillFocus cycles, USB enumeration with bulk max packet eight, GET_MAX_LUN, SCSI inquiry/readiness/capacity, and exact five-sector reads covering boot/FAT/root/README.TXT. Both kill-focus events occur while attached and configured. The custom personality disconnects and the stock callback is restored; refocusing works. Counters show 731 real wrapper/handler entries, SR IPL five in the handler and zero in the foreground, 278 selected ROM event-pump calls, and no ROM USB peripheral dispatcher or keyboard-loop execution during ownership.

This proves that replacing the registered callback is useful for the emulated shared interrupt source, even though the stock callback handles host-controller work. It does **not** prove complete physical PCB routing. The emulator explicitly ORs host and device interrupt conditions onto this source. Its ISP1763 connection/EP0/halt models are simplified; see the experiment README before using the driver as a silicon register reference.

## Focus policy and ROM polling

SetFocus briefly masks the source, saves the old callback and controller enables, disconnects the current personality, replaces the callback, initializes endpoints, then reconnects and unmasks the source. USB interrupts remain enabled while focused. KillFocus disconnects, disables/acknowledges our events, removes our callback and restores the saved callback/masks. It leaves the peripheral disconnected: resuming an old host configuration would require re-enumeration and native controller initialization, not just restoring a pointer.

IRQ replacement does not prevent explicit ROM polling. The applet must also exclude the external-connection workflow: `SystemHandleEvents` at `418794` checks **mask bit 2, value 4**, and calls `417d0e`. Earlier wording “bit 4” meant the mask value, not bit number four. While owning USB, clear `mask & 4` and audit other APIs that pump USB internally. The prototype exercises mask 8 with no-key FF, preserving that separation. It is not a universal safe-syscall whitelist.

The harness invokes the applet's actual `ProcessMessage` body with focus messages; it does not test native installation or navigation through the applet picker. Acquisition failure rollback, physical endpoint initialization, reset/stall/toggle compliance, safe firmware personality restoration and installed-app lifecycle remain production work.

## Eight-byte descriptors

Yes: a full-speed bulk endpoint may advertise eight-byte packets even when the hardware supports 64 or more. Advertise the chosen endpoint maximum and configure its FIFO/endpoint state consistently. A full eight-byte packet then continues a transfer; a short packet is fewer than eight bytes. This is why the AS3000 experiment worked. Advertising 64 while intentionally emitting eight-byte chunks would make each chunk short to the host.

A high-speed bulk endpoint requires a different configuration (512-byte maximum), so force/use full speed for this eight-byte design. Merely setting bcdUSB to 0110 does not control PHY negotiation. The ISP1763A datasheet documents FORCEFS at TEST_MODE 84h bit 4. The current Neo model does not implement that register. EP0 has fixed 64-byte hardware buffers on this chip; buffer capacity and the packets our control engine chooses to send are separate concerns.

References: [ISP1763A datasheet, sections 9.3, 11.2 and 11.6](https://www.st.com/resource/en/datasheet/isp1763a.pdf), [Arm USB transfer-type documentation](https://arm-software.github.io/MDK-Middleware/main/USB/USB_Concepts.html).

## Can Applets switch applications in native USB keyboard mode?

The traced ordinary path does not run the normal Applets-key dispatcher. Keyboard loop `41ca36` snapshots the foreground entry/A5 and, at `41d1ea`, passes zero to `GetKey` at `423068`. That function invokes `SystemHandleEvents(8, key)` only when its argument is nonzero (`42309e`–`4230b4`). Therefore the keyboard loop deliberately skips system hotkey handling and delivers native keys to the foreground applet as `3001e/3001f` (or busy/suspended variants). Its idle path scans the keyboard, but does not invoke the ordinary applet-switch dispatcher either.

This supports “the usual Applets key does not navigate to another applet while this loop is active,” not “all applet switching is impossible.” A custom callback could explicitly invoke lifecycle/UI services. Shipped-app special behavior and every other ROM are not dynamically qualified by this experiment. On detach, the loop sends `3000c` and returns to the outer workflow.

If a storage applet owns the callback and excludes the ROM connection poll before attachment, the OS need not generate `MSG_USB_PLUG` at all; the prototype records none. Nevertheless, a short acquisition/quiesce step remains necessary for already-present VBUS, pending events, another active personality, or code that explicitly switches applications. It need not involve the stock `300xx` message loop.

## AS3000 correction and direct slot replacement

The earlier mass-storage and Linux VHCI runs target AS3000/PDIUSBD11. The focus-ownership run described above targets Neo/ISP1763; it is not AS3000 focus-ownership execution evidence. This target change was not made sufficiently explicit during the discussion.

A follow-up static trace of AS3000 3.01 (`.research-work/usb-ownership/evidence/as3000.dis`) finds the equivalent mechanism:

| Item | AS3000 3.01 | Neo 3.21 |
|---|---|---|
| Callback table base | `4222` | `489a` |
| Mask `00100000` table index | 1 | 7 |
| IRQ5 callback slot | `4226` | `48b6` |
| Source-to-index helper | `4cd058` | `420006` |
| Remove callback | `4cd0d0` | `4200a6` |
| Register callback | `4cd12e` | `420104` |
| Level-5 ROM wrapper | `4cd342` | `4203c4` |

Both registration/removal routines map/validate the source, save SR and raise its interrupt mask, check the slot's occupancy, write/clear the one pointer, restore SR and return a status. They do not initialize the USB controller, allocate per-handler storage, change A5, or unmask the CPU source. AS3000 wrapper `4cd342` checks ISR bit 20 and calls the pointer at `4226` with ordinary JSR, then restores registers and RTEs.

Consequently a qualified direct pointer exchange under a short CPU critical section can replace both private ROM registration calls. Save the previous pointer, install ours without an intermediate NULL slot, and restore the saved pointer on release (after disconnecting/stopping our USB sources). The original SR must be restored exactly; peripheral/CPU source masks remain separate ownership state. This still requires finding and verifying the correct RAM slot and interrupt ABI for each supported ROM. These AS3000 addresses and helper equivalence are static findings; AS3000 focus/interrupt-driven storage has not yet been run.
