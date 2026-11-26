import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

/* Follow real syscall roots; names are annotations, not discovery criteria. */
public class InspectFontAccess extends GhidraScript {
    private Map<Long,Set<Long>> graph = new TreeMap<>();
    private Set<Long> seen = new HashSet<>();
    private ArrayDeque<Long> pending = new ArrayDeque<>();
    private PrintWriter output;
    private boolean code(long a) { return a>=0x410000L && a<0x44af8eL && (a&1)==0; }
    private Function function(long a) throws Exception {
        Address address=toAddr(a);
        Function f=getFunctionAt(address);
        if(f==null) {
            disassemble(address);
            f=createFunction(address,null);
        }
        return f;
    }
    private void edge(long from,long to) {
        if(!code(to)) return;
        graph.computeIfAbsent(from,k->new TreeSet<>()).add(to);
        if(!seen.contains(to))pending.add(to);
    }
    private boolean interesting(long a) {
        return a==0xe0a || (a>=0x5c7a && a<=0x5c8d) || a==0x42284e || a==0x422af4;
    }
    public void run() throws Exception {
        File dir=new File(getScriptArgs()[0]);dir.mkdirs();
        try(PrintWriter out=new PrintWriter(new File(dir,"functions.txt"))) {
            output=out;
            long[] roots=new long[285];
            for(int i=0;i<285;i++) {
                roots[i]=Integer.toUnsignedLong(getInt(toAddr(0x44f15eL+4*i)));
                out.printf("SLOT %d %08X%n",i,roots[i]);
                if(roots[i]!=0)pending.add(roots[i]);
            }
            // Internal routines of interest, whether exposed by a slot or not.
            pending.add(0x42284eL);pending.add(0x422af4L);
            // Explicitly include every branch of CallSysInt's sparse switch.
            disassemble(toAddr(0x425f42L));
            for(int i=0;i<24;i++) {
                long dest=0x425f80L+getShort(toAddr(0x425f80L+2*(23-i)));
                int selector=(getByte(toAddr(0x425fb0L+i))&255)<<8;
                out.printf("SELECTOR %04X %08X%n",selector,dest);
                disassemble(toAddr(dest));
                currentProgram.getReferenceManager().addMemoryReference(toAddr(0x425f7cL),toAddr(dest),RefType.COMPUTED_JUMP,SourceType.USER_DEFINED,0);
            }
            // Include all statically identified syscall callees. Computed
            // transfers remain explicitly recorded, never silently resolved.
            while(!pending.isEmpty() && seen.size()<5000) {
                monitor.checkCanceled();long entry=pending.removeFirst();
                if(!seen.add(entry))continue;
                Function f=function(entry);
                if(f==null){out.printf("NO_FUNCTION %08X%n",entry);continue;}
                out.printf("FUNCTION %08X %s%n",entry,f.getBody());
                InstructionIterator it=currentProgram.getListing().getInstructions(f.getBody(),true);
                while(it.hasNext()) {
                    Instruction ins=it.next();
                    out.printf("  %s %s%n",ins.getAddress(),ins);
                    for(int operand=0;operand<ins.getNumOperands();operand++)
                        for(Object object:ins.getOpObjects(operand))
                            if(object instanceof ghidra.program.model.scalar.Scalar) {
                                long value=((ghidra.program.model.scalar.Scalar)object).getUnsignedValue();
                                if(interesting(value))out.printf("INTEREST_SCALAR %08X %s %08X%n",entry,ins.getAddress(),value);
                            }
                    for(Reference ref:ins.getReferencesFrom())
                        if(interesting(ref.getToAddress().getOffset()))
                            out.printf("INTEREST %08X %s %s %s%n",entry,ins.getAddress(),ref.getReferenceType(),ref.getToAddress());
                    if(ins.getFlowType().isCall() || ins.getFlowType().isJump()) {
                        Address[] flows=ins.getFlows();
                        if(flows.length==0)
                            out.printf("INDIRECT %08X %s %s%n",entry,ins.getAddress(),ins);
                        if(ins.getFlowType().isCall())for(Address dest:flows)edge(entry,dest.getOffset());
                    }
                }
            }
            out.printf("TOTAL_FUNCTIONS %d%n",seen.size());
            try(PrintWriter links=new PrintWriter(new File(dir,"calls.tsv"))) {
                for(Map.Entry<Long,Set<Long>> e:graph.entrySet())for(long to:e.getValue())
                    links.printf("%08X\t%08X%n",e.getKey(),to);
            }
        }
    }
}
