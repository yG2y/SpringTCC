import com.github.mauricioaniche.ck.CK;
import com.github.mauricioaniche.ck.CKClassResult;
import com.github.mauricioaniche.ck.CKNotifier;
import com.github.mauricioaniche.ck.ResultWriter;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;

/** Preserve the CK metrics unchanged while identifying a class by file AND name.
 * Upstream Runner keys only by name, overwriting classes in different modules.
 * NOC/type binding still use upstream semantics; collisions are separately audited.
 */
public final class AuditedCKRunner {
    public static void main(String[] args) throws Exception {
        if (args.length != 5) throw new IllegalArgumentException("source useJars partition details output");
        String output = args[4];
        Map<String, CKClassResult> results = new LinkedHashMap<>();
        int[] errors = {0};
        new CK(Boolean.parseBoolean(args[1]), Integer.parseInt(args[2]), Boolean.parseBoolean(args[3]))
            .calculate(args[0], new CKNotifier() {
                public void notify(CKClassResult result) {
                    results.put(result.getFile() + "\u0000" + result.getClassName(), result);
                }
                public void notifyError(String file, Exception error) {
                    errors[0]++;
                    System.err.println("CK_FILE_ERROR: " + file);
                    error.printStackTrace(System.err);
                }
            });
        ResultWriter writer = new ResultWriter(
            Paths.get(output, "class.csv").toString(), Paths.get(output, "method.csv").toString(),
            Paths.get(output, "variable.csv").toString(), Paths.get(output, "field.csv").toString(), false);
        for (CKClassResult result : results.values()) writer.printResult(result);
        writer.flushAndClose();
        System.out.println("CK classes=" + results.size() + " callback_errors=" + errors[0]);
        if (errors[0] > 0) System.exit(2);
    }
}
