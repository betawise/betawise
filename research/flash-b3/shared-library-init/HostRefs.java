import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import java.util.HashSet;
public class HostRefs extends GhidraScript {
 public void run() throws Exception {
  var seen=new HashSet<String>(); var d=new DecompInterface();d.openProgram(currentProgram);
  for(String arg:getScriptArgs()){
   var a=toAddr(Long.parseLong(arg,16));
   var refs=getReferencesTo(a);
   for(var ref:refs){
    var f=getFunctionContaining(ref.getFromAddress());
    println("REF "+a+" FROM "+ref.getFromAddress()+" FUNCTION "+f);
    if(f!=null && seen.add(f.getEntryPoint().toString())){
     println("FUNCTION "+f.getEntryPoint());
     var r=d.decompileFunction(f,30,monitor);
     if(r.decompileCompleted())println(r.getDecompiledFunction().getC());
     for(var up:getReferencesTo(f.getEntryPoint()))println("CALLER "+up.getFromAddress()+" "+getFunctionContaining(up.getFromAddress()));
    }
   }
  }d.dispose();
 }
}
