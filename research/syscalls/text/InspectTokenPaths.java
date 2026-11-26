import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import java.util.TreeMap;
public class InspectTokenPaths extends GhidraScript {
 public void run() throws Exception {
  var functions=new TreeMap<Long,ghidra.program.model.listing.Function>();
  for(String arg:getScriptArgs()){
   var at=toAddr(Long.parseLong(arg,16));var f=getFunctionContaining(at);
   if(f==null){
    long end=at.getOffset();long start=end;
    for(long p=end&~1L;p>Math.max(currentProgram.getMinAddress().getOffset(),end-0x2000);p-=2){int w=getShort(toAddr(p))&65535;
     if(w==0x48e7||w==0x4e56){start=p;break;}
    }
    disassemble(toAddr(start));f=getFunctionAt(toAddr(start));if(f==null)f=createFunction(toAddr(start),null);
   }
   println("SITE "+at+" FUNCTION "+(f==null?"none":f.getEntryPoint()));
   if(f!=null)functions.put(f.getEntryPoint().getOffset(),f);
  }
  DecompInterface d=new DecompInterface();d.openProgram(currentProgram);
  try{for(var entry:functions.entrySet()){
   var f=entry.getValue();println("=== FUNCTION "+f.getEntryPoint()+" ===");
   var it=currentProgram.getListing().getInstructions(f.getBody(),true);while(it.hasNext()){var i=it.next();println(i.getAddress()+" "+i);}
   var r=d.decompileFunction(f,35,monitor);if(r.decompileCompleted())println(r.getDecompiledFunction().getC());else println("DECOMP_FAILED "+r.getErrorMessage());
  }}finally{d.dispose();}
 }
}
