// Apply names from re/symbols.csv to the current program.
// CSV columns: va,name,kind,confidence,notes   (kind = func | data | label)
// Usage (headless): -postScript ApplySymbols.java <path-to-symbols.csv>
// @category Wings
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import ghidra.program.model.symbol.Symbol;
import ghidra.app.cmd.function.CreateFunctionCmd;
import java.io.*;
import java.util.*;

public class ApplySymbols extends GhidraScript {
    private List<String> splitCsv(String line) {
        List<String> out = new ArrayList<>();
        StringBuilder cur = new StringBuilder();
        boolean q = false;
        for (char c : line.toCharArray()) {
            if (c == '"') { q = !q; continue; }
            if (c == ',' && !q) { out.add(cur.toString()); cur.setLength(0); continue; }
            cur.append(c);
        }
        out.add(cur.toString());
        return out;
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File f = args.length > 0 ? new File(args[0]) : askFile("symbols.csv", "Apply");
        int n = 0, created = 0;
        try (BufferedReader r = new BufferedReader(new FileReader(f))) {
            String line = r.readLine(); // header
            while ((line = r.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty() || line.startsWith("#")) continue;
                List<String> c = splitCsv(line);
                if (c.size() < 2) continue;
                Address a = toAddr(Long.decode(c.get(0).trim()));
                String name = c.get(1).trim();
                String kind = c.size() > 2 ? c.get(2).trim() : "label";
                String conf = c.size() > 3 ? c.get(3).trim() : "";
                String notes = c.size() > 4 ? c.get(4).trim() : "";
                if (kind.equals("func")) {
                    Function fn = getFunctionAt(a);
                    if (fn == null) {
                        disassemble(a);
                        new CreateFunctionCmd(a).applyTo(currentProgram);
                        fn = getFunctionAt(a);
                        if (fn != null) created++;
                    }
                    if (fn != null) fn.setName(name, SourceType.USER_DEFINED);
                    else createLabel(a, name, true, SourceType.USER_DEFINED);
                } else {
                    Symbol s = getSymbolAt(a);
                    if (s != null && s.getSource() == SourceType.USER_DEFINED && s.getName().equals(name)) {
                        // already applied
                    } else {
                        createLabel(a, name, true, SourceType.USER_DEFINED);
                    }
                }
                String cm = "[" + conf + "] " + notes;
                if (!notes.isEmpty() || !conf.isEmpty())
                    currentProgram.getListing().setComment(a, ghidra.program.model.listing.CodeUnit.PLATE_COMMENT, cm);
                n++;
            }
        }
        println("ApplySymbols: applied " + n + " symbols, created " + created + " functions");
    }
}
