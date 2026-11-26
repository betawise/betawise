import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.Reference;
public class InspectNativeBearings extends GhidraScript {
 public void run() throws Exception {
  if(getScriptArgs().length>0)java.nio.file.Files.write(java.nio.file.Path.of(getScriptArgs()[0]),getBytes(toAddr(0x420000),0x10000));
  for(long target:new long[]{0x421a82,0x42bece,0x4205de,0x420c20,0xfffffd00L,0xfffffd0cL}) {
   println("REFERENCES "+Long.toHexString(target));
   for(Reference r:getReferencesTo(toAddr(target)))println(r.getFromAddress()+" "+r.getReferenceType()+" "+getInstructionAt(r.getFromAddress()));
  }
  for(int c=0;c<256;c++)println(String.format("CLASS %02X %02X",c,getByte(toAddr(0x44c7e0+c))&255));
 }
}
