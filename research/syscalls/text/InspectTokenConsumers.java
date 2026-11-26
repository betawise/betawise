// Inspect genuine instructions/consumers, not arbitrary Bx bytes in resources.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.listing.Function;
import java.util.TreeMap;
public class InspectTokenConsumers extends GhidraScript {
 public void run() throws Exception {
  var selected=new TreeMap<Long,Function>();
  var args=getScriptArgs();
  long table=args.length>0?Long.parseLong(args[0],16):0;
  if(table!=0)for(var ref:getReferencesTo(toAddr(table))){
   println("CLASSREF "+ref.getFromAddress());
   var f=getFunctionContaining(ref.getFromAddress());if(f!=null)selected.put(f.getEntryPoint().getOffset(),f);
  }
  var instructions=currentProgram.getListing().getInstructions(true);
  while(instructions.hasNext()){
   var i=instructions.next();boolean hit=false;
   for(int n=0;n<i.getNumOperands();n++){
    if(!i.getDefaultOperandRepresentation(n).contains("#"))continue;
    for(Object o:i.getOpObjects(n))if(o instanceof Scalar){long v=((Scalar)o).getUnsignedValue();
     if(v>=0xb0&&v<=0xbf)hit=true;
    }
   }
   if(hit){var f=getFunctionContaining(i.getAddress());println("TOKENCONST "+i.getAddress()+" "+i+" FUNCTION "+(f==null?"none":f.getEntryPoint()));
    if(f!=null)selected.put(f.getEntryPoint().getOffset(),f);
   }
  }
  DecompInterface d=new DecompInterface();d.openProgram(currentProgram);
  try{for(var entry:selected.entrySet()){
   var f=entry.getValue();println("=== FUNCTION "+f.getEntryPoint()+" ===");
   var it=currentProgram.getListing().getInstructions(f.getBody(),true);while(it.hasNext()){var i=it.next();println(i.getAddress()+" "+i);}
   var r=d.decompileFunction(f,30,monitor);if(r.decompileCompleted())println(r.getDecompiledFunction().getC());else println("DECOMP_FAILED "+r.getErrorMessage());
  }}finally{d.dispose();}
 }
}
