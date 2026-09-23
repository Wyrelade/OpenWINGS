// Export memory map, function list with call edges, and decompilation of every function.
// Usage (headless, -process): -postScript ExportAll.java <out_dir>
// Writes <out_dir>/memmap.txt, functions.tsv (entry,name,size,callees,callers), decomp.c
// @category Wings
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.util.task.ConsoleTaskMonitor;
import java.io.*;
import java.util.*;

public class ExportAll extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File dir = new File(args.length > 0 ? args[0] : ".");
        dir.mkdirs();
        try (PrintWriter w = new PrintWriter(new File(dir, "memmap.txt"))) {
            for (MemoryBlock b : currentProgram.getMemory().getBlocks())
                w.printf("%s %s-%s init=%s%n", b.getName(), b.getStart(), b.getEnd(), b.isInitialized());
        }
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        ConsoleTaskMonitor mon = new ConsoleTaskMonitor();
        try (PrintWriter ft = new PrintWriter(new File(dir, "functions.tsv"));
             PrintWriter dc = new PrintWriter(new File(dir, "decomp.c"))) {
            ft.println("entry\tname\tsize\tcallees\tcallers");
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                StringBuilder ce = new StringBuilder(), cr = new StringBuilder();
                for (Function c : f.getCalledFunctions(mon)) ce.append(c.getEntryPoint()).append(' ');
                for (Function c : f.getCallingFunctions(mon)) cr.append(c.getEntryPoint()).append(' ');
                ft.printf("%s\t%s\t%d\t%s\t%s%n", f.getEntryPoint(), f.getName(), f.getBody().getNumAddresses(),
                          ce.toString().trim(), cr.toString().trim());
                DecompileResults r = di.decompileFunction(f, 60, mon);
                dc.printf("// ==== %s @ %s ====%n", f.getName(), f.getEntryPoint());
                if (r != null && r.decompileCompleted()) dc.println(r.getDecompiledFunction().getC());
                else dc.println("// decompile failed");
            }
        }
        println("ExportAll done -> " + dir);
    }
}
