import ghidra.app.script.GhidraScript;
import ghidra.app.util.PseudoDisassembler;
import java.io.PrintWriter;

/** Raw, explicitly bounded instruction views; does not guess function prototypes. */
public class InspectNeoModule extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) throw new IllegalArgumentException("output file, start:end ...");
        var decoder = new PseudoDisassembler(currentProgram);
        try (var out = new PrintWriter(args[0])) {
            for (int n=1; n<args.length; n++) {
                String[] range = args[n].split(":");
                long start = Long.parseLong(range[0],16), end = Long.parseLong(range[1],16);
                out.println("RANGE " + args[n] + " (linear view; embedded data is not executable evidence)");
                while (start < end && !monitor.isCancelled()) {
                    var a = toAddr(start);
                    var ins = decoder.disassemble(a);
                    if (ins == null) throw new IllegalStateException("undecodable " + a);
                    out.println(a + " " + ins);
                    start += ins.getLength();
                }
            }
        }
    }
}
