// Read-only copied ROM project. Explicit helper addresses, no guessed SDK types.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
public class InspectReaderPath extends GhidraScript {
 public void run() throws Exception {
  DecompInterface d=new DecompInterface();
  try {d.openProgram(currentProgram);
   for(String s:getScriptArgs()) {long a=Long.parseLong(s,16);var addr=toAddr(a);
    var f=getFunctionAt(addr);if(f==null){disassemble(addr);f=createFunction(addr,null);}
    if(f==null)throw new IllegalStateException("No function "+s);
    println("=== "+s+" ===");var it=currentProgram.getListing().getInstructions(f.getBody(),true);
    while(it.hasNext()){var i=it.next();println(i.getAddress()+" "+i);}
    var r=d.decompileFunction(f,45,monitor);if(!r.decompileCompleted())throw new IllegalStateException(r.getErrorMessage());
    println(r.getDecompiledFunction().getC());
   }
  }finally{d.dispose();}
 }
}
