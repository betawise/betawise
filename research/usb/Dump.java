import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
public class Dump extends GhidraScript {
 public void run() throws Exception {
  for(String arg:getScriptArgs()){
   var a=toAddr(Long.parseLong(arg,16));
   disassemble(a);
   var f=getFunctionAt(a);
   if(f==null) f=createFunction(a,null);
   if(f==null) continue;
   var it=currentProgram.getListing().getInstructions(f.getBody(),true);
   while(it.hasNext()){var i=it.next(); println(i.getAddress()+" "+i);}
   var d=new DecompInterface(); d.openProgram(currentProgram);
   var r=d.decompileFunction(f,10,monitor);
   if(r.decompileCompleted()) println(r.getDecompiledFunction().getC());
   d.dispose();
  }
 }
}
