// Static entry/dispatcher evidence; run on disposable imports only.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import java.io.*;
import java.util.*;
public class AuditMessageEntry extends GhidraScript {
 PrintWriter w;
 boolean inside(long n){return n>=0x94&&n<currentProgram.getMaxAddress().getOffset();}
 void resolve(Function f)throws Exception{
  for(int pass=0;pass<6;pass++){
   boolean changed=false;
   var it=currentProgram.getListing().getInstructions(f.getBody(),true);
   var list=new ArrayList<Instruction>();while(it.hasNext())list.add(it.next());
   for(int k=0;k<list.size();k++){
    var i=list.get(k);long p=i.getAddress().getOffset();var m=currentProgram.getMemory();
    int op=Short.toUnsignedInt(m.getShort(i.getAddress()));
    // Vendor idiom: MOVEA.L #delta,An; JSR (PC,An.L,-2).
    if(op==0x4ebb&&k>0){var prev=list.get(k-1);int po=Short.toUnsignedInt(m.getShort(prev.getAddress()));
     int ext=Short.toUnsignedInt(m.getShort(i.getAddress().add(2)));
     if((po&0xf1ff)==0x207c&&((po>>9)&7)==((ext>>12)&7)&&prev.getAddress().add(6).equals(i.getAddress())&&(ext&0xfff)==0x8fe){
      long target=p+m.getInt(prev.getAddress().add(2));
      if(inside(target))currentProgram.getReferenceManager().addMemoryReference(i.getAddress(),toAddr(target),RefType.COMPUTED_CALL,SourceType.USER_DEFINED,0);
     }
    }
    if(op!=0x4efb)continue;
    int ext=Short.toUnsignedInt(m.getShort(i.getAddress().add(2)));
    if(ext!=0x0002&&ext!=0x1002)continue;
    int count=-1;
    // Dense or sparse compiler switches use a nearby explicit D1 bound.
    for(int j=k-1;j>=0&&p-list.get(j).getAddress().getOffset()<90;j--){
     var q=list.get(j).getAddress();int qo=Short.toUnsignedInt(m.getShort(q));
     if((qo&0xff00)==0x7200&&(qo&255)<64){count=(qo&255)+1;break;}
    }
    if(count<1)continue;
    long table=p+4;boolean valid=true;var targets=new ArrayList<Address>();
    for(int j=0;j<count;j++){long t=table+m.getShort(toAddr(table+2*j));if(!inside(t)||t%2!=0){valid=false;break;}targets.add(toAddr(t));}
    if(!valid)continue;
    boolean fresh=false;
    for(var target:targets){boolean exists=false;for(var r:getReferencesFrom(i.getAddress()))if(r.getToAddress().equals(target))exists=true;
     if(!exists){currentProgram.getReferenceManager().addMemoryReference(i.getAddress(),target,RefType.COMPUTED_JUMP,SourceType.USER_DEFINED,0);disassemble(target);fresh=true;}}
    if(fresh){w.println("RESOLVED_SWITCH "+i.getAddress()+" count="+count+" table="+Long.toHexString(table));changed=true;}
   }
   if(!changed)break;CreateFunctionCmd.fixupFunctionBody(currentProgram,f,monitor);
  }
 }
 public void run()throws Exception{
  var m=currentProgram.getMemory();var base=currentProgram.getMinAddress();
  if(m.getInt(base)!=0xc0ffeead)throw new Exception("Not an applet header");
  long entry=Integer.toUnsignedLong(m.getInt(base.add(0x84)));
  var file=new File(getScriptArgs()[0],currentProgram.getName()+".txt");
  try(var writer=new PrintWriter(file)){w=writer;
   w.println("IMAGE "+currentProgram.getName()+" ENTRY "+Long.toHexString(entry));
   var a=base.add(entry);disassemble(a);var f=getFunctionAt(a);if(f==null)f=createFunction(a,null);
   if(f==null)throw new Exception("Entry creation failed");
   var d=new DecompInterface();d.openProgram(currentProgram);
   var q=new ArrayDeque<Function>();q.add(f);var seen=new HashSet<String>();
   var depth=new HashMap<String,Integer>();depth.put(f.getEntryPoint().toString(),0);
   while(!q.isEmpty()){
    var g=q.remove();if(!seen.add(g.getEntryPoint().toString()))continue;
    int level=depth.get(g.getEntryPoint().toString());
    if((Short.toUnsignedInt(m.getShort(g.getEntryPoint()))&0xf000)==0xa000){w.println("SYSCALL_STUB "+g.getEntryPoint());continue;}
    resolve(g);w.println("FUNCTION "+g.getEntryPoint());
    var it=currentProgram.getListing().getInstructions(g.getBody(),true);boolean interesting=level<=2;
    var instructions=new ArrayList<Instruction>();while(it.hasNext())instructions.add(it.next());
    for(var i:instructions){String s=i.toString();if(s.contains("#0x10000")||s.contains("#0x100000")||s.contains("#0x300")||s.contains("#0x400")||s.contains("#0x500")||s.contains("#0x600")||s.contains("#0x700")||s.contains("#0x18,")||s.contains("#0x19,"))interesting=true;
     if(i.getFlowType().isCall())for(var r:getReferencesFrom(i.getAddress()))if(r.getReferenceType().isCall()){
      var t=r.getToAddress();if(!inside(t.getOffset()))continue;var h=getFunctionAt(t);if(h==null){disassemble(t);h=createFunction(t,null);}if(h!=null&&!depth.containsKey(h.getEntryPoint().toString())){depth.put(h.getEntryPoint().toString(),level+1);q.add(h);}
     }
    }
    if(interesting||seen.size()<4){for(var i:instructions)w.println(i.getAddress()+" "+i);d.flushCache();var r=d.decompileFunction(g,12,monitor);
     if(r.decompileCompleted())w.println(r.getDecompiledFunction().getC());else w.println("DECOMPILATION_FAILED "+r.getErrorMessage());}
    else w.println("HELPER instructions="+instructions.size());
   }
   w.println("ENTRY_AUDIT_DONE functions="+seen.size()+" pending="+q.size());d.dispose();
  }println("ENTRY_AUDIT_SAVED "+file);
 }
}
