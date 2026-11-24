import ghidra.app.script.GhidraScript;

/** Seed reviewed 8051 reset/interrupt vectors in a bank-1 CODE view. */
public class PrepareNeoModule extends GhidraScript {
    public void run() throws Exception {
        for (var block : currentProgram.getMemory().getBlocks())
            println("BLOCK " + block.getName() + " " + block.getStart() + " " + block.getEnd());
        int[] vectors = {0,3,11,19,27,35,43,51,59,67,75,83,91,99,107,115,123,131,139};
        for (int vector : vectors) {
            var address = toAddr(vector);
            if ((getByte(address) & 255) != 2) continue;
            disassemble(address);
            if (getFunctionAt(address) == null) createFunction(address, null);
            currentProgram.getSymbolTable().addExternalEntryPoint(address);
        }
        boolean newer = (getByte(toAddr(1)) & 255) == 0x12;
        // Startup explicitly calls these initializers via the compiler's
        // computed-call helper; normal control-flow analysis misses them.
        int init = newer ? 0xa3c6 : 0xceb1;
        disassemble(toAddr(init));
        if (getFunctionAt(toAddr(init)) == null) createFunction(toAddr(init), null);
        if (newer) {
            // Reviewed far-call veneers: LCALL 0e49, LE16 target, bank byte.
            // Seed target entry points without pretending Ghidra models the
            // stack-manipulating helper or dynamically remapped banks.
            for (int i = 0x134d; i < 0x185d - 5; i++) {
                if ((getByte(toAddr(i)) & 255) != 0x12 ||
                    (getByte(toAddr(i+1)) & 255) != 0x0e ||
                    (getByte(toAddr(i+2)) & 255) != 0x49) continue;
                int target = (getByte(toAddr(i+3)) & 255) |
                             ((getByte(toAddr(i+4)) & 255) << 8);
                int bank = getByte(toAddr(i+5)) & 255;
                if (bank > 1 || (target >= 0x8000 ? bank != 1 : bank != 0)) continue;
                println("FAR " + Integer.toHexString(i) + " -> " + Integer.toHexString(target) + " bank " + bank);
                disassemble(toAddr(target));
                if (getFunctionAt(toAddr(target)) == null) createFunction(toAddr(target), null);
                var destination = getFunctionAt(toAddr(target));
                var veneer = getFunctionAt(toAddr(i));
                if (veneer == null) veneer = createFunction(toAddr(i), null);
                if (veneer != null && destination != null && veneer != destination) {
                    veneer.setThunkedFunction(destination);
                    veneer.setNoReturn(false);
                }
            }
        } else {
            // Reviewed old-compiler immediate-DPTR calls through helper 0086.
            for (int i = 0; i < 0xfff8; i++) {
                if ((getByte(toAddr(i)) & 255) != 0x90 ||
                    (getByte(toAddr(i+3)) & 255) != 0x74 ||
                    (getByte(toAddr(i+5)) & 255) != 0x12 ||
                    (getByte(toAddr(i+6)) & 255) != 0 ||
                    (getByte(toAddr(i+7)) & 255) != 0x86) continue;
                int target = ((getByte(toAddr(i+1)) & 255) << 8) | (getByte(toAddr(i+2)) & 255);
                int bank = getByte(toAddr(i+4)) & 255;
                if (bank > 1 || (target >= 0x8000 ? bank != 1 : bank != 0)) continue;
                println("FAR " + Integer.toHexString(i) + " -> " + Integer.toHexString(target) + " bank " + bank);
                disassemble(toAddr(target));
                if (getFunctionAt(toAddr(target)) == null) createFunction(toAddr(target), null);
            }
        }
        // IAR stack/bank helpers confuse generic no-return propagation. A
        // normal LCALL to a veneer returns to its following instruction; the
        // LCALL *inside* a 0e49 veneer instead consumes inline target bytes.
        // Restore only ordinary call fallthroughs, never those inline bytes.
        var functions = currentProgram.getFunctionManager().getFunctions(true);
        while (functions.hasNext()) {
            var f = functions.next();
            f.setNoReturn(false);
        }
        for (int pass = 0; pass < 4; pass++) {
            java.util.ArrayList<ghidra.program.model.address.Address> resumes = new java.util.ArrayList<>();
            var instructions = currentProgram.getListing().getInstructions(true);
            while (instructions.hasNext()) {
                var i = instructions.next();
                if (!i.getMnemonicString().equals("LCALL")) continue;
                var flows = i.getFlows();
                if (newer && flows.length == 1 && flows[0].getOffset() == 0x0e49) continue;
                resumes.add(i.getAddress().add(i.getLength()));
            }
            for (var address : resumes) if (getInstructionAt(address) == null) disassemble(address);
        }
    }
}
