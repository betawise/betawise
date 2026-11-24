import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

/** Static evidence export; run only in a disposable receiver-analysis project. */
public class DumpReceiver extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("output directory required");
        java.io.File out = new java.io.File(args[0]);
        out.mkdirs();
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        try (PrintWriter c = new PrintWriter(new java.io.File(out, "receiver-decompiled.c"));
             PrintWriter asm = new PrintWriter(new java.io.File(out, "receiver-disassembly.txt"))) {
            var funcs = currentProgram.getFunctionManager().getFunctions(true);
            int count = 0;
            while (funcs.hasNext() && !monitor.isCancelled()) {
                Function f = funcs.next();
                c.println("\n/* FUNCTION " + f.getEntryPoint() + " " + f.getName() + " */");
                var result = dec.decompileFunction(f, 5, monitor);
                if (result.decompileCompleted()) c.println(result.getDecompiledFunction().getC());
                else c.println("/* DECOMPILATION FAILED: " + result.getErrorMessage() + " */");
                asm.println("\nFUNCTION " + f.getEntryPoint() + " " + f.getName());
                var ins = currentProgram.getListing().getInstructions(f.getBody(), true);
                while (ins.hasNext()) {
                    var i = ins.next();
                    asm.println(i.getAddress() + " " + i);
                }
                count++;
            }
            println("Exported " + count + " functions");
        } finally { dec.dispose(); }
    }
}
