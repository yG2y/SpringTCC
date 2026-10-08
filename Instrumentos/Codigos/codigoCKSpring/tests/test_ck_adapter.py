import csv
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
JAR = BASE/'ck_tools/ck-8a1ef916.jar'
JAVA = Path('/opt/homebrew/opt/openjdk@17/bin/java')

@unittest.skipUnless(JAR.exists() and JAVA.exists(), 'Fixed CK build/JVM unavailable')
class CKAdapterTests(unittest.TestCase):
    def test_records_and_same_name_in_separate_modules_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); source=root/'source'; output=root/'output'; output.mkdir()
            for module,body in [('a','return 1;'),('b','if(x>0) return 1; return 2;'),('c','return 3;')]:
                folder=source/module/'p';folder.mkdir(parents=True)
                (folder/'Example.java').write_text('package p; public class Example { int f(int x) {'+body+'} }')
            (source/'Point.java').write_text('public record Point(int x, int y) { public int sum(){return x+y;} }')
            cp=str(JAR)+':'+str(BASE/'ck_tools/classes')
            p=subprocess.run([str(JAVA),'-Xmx512m','-cp',cp,'AuditedCKRunner',str(source),'false','100','false',str(output)],capture_output=True,text=True,timeout=40)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            with (output/'class.csv').open() as f: rows=list(csv.DictReader(f))
            examples=[r for r in rows if r['file'].endswith('/Example.java')]
            self.assertEqual(len(examples),3)
            self.assertEqual(len({r['file'] for r in examples}),3)
            self.assertEqual({r['wmc'] for r in examples},{'1','2'})
            self.assertEqual(len([r for r in rows if r['class']=='Point']),1)

if __name__=='__main__':unittest.main()
