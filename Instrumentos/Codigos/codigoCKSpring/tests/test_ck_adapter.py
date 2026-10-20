import csv
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
JAR = BASE/'ck_tools/ck-8a1ef916.jar'
JAVA = Path(os.environ['JAVA_HOME'])/'bin/java' if os.environ.get('JAVA_HOME') else Path('/opt/homebrew/opt/openjdk@17/bin/java')
if not JAVA.exists():
    JAVA = Path(shutil.which('java') or '/nonexistent/java')

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

@unittest.skipUnless(JAR.exists() and JAVA.exists(), 'Fixed CK build/JVM unavailable')
class KnownMetricTests(unittest.TestCase):
    def test_seven_aggregates_on_small_inheritance_fixture(self):
        from ck_pipeline.extraction import aggregate, java_sloc
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir();out=root/'output';out.mkdir()
            base='''class Base {
  int x;
  int get() {
    return x;
  }
  int compute(int v) {
    if (v > 0) {
      return x;
    }
    return 0;
  }
}
'''
            child='''class Child extends Base {
  int go() {
    return get();
  }
}
'''
            (source/'Base.java').write_text(base);(source/'Child.java').write_text(child)
            cp=str(JAR)+':'+str(BASE/'ck_tools/classes')
            p=subprocess.run([str(JAVA),'-Xmx512m','-cp',cp,'AuditedCKRunner',str(source),'false','100','false',str(out)],capture_output=True,text=True,timeout=40)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            with (out/'class.csv').open() as f: classes=list(csv.DictReader(f))
            with (out/'method.csv').open() as f: methods=list(csv.DictReader(f))
            got=aggregate(classes,methods)
            expected=dict(avg_cbo=.5,avg_rfc=.5,avg_wmc=2,avg_dit=1.5,avg_noc=.5,avg_lcom=0,avg_loc_method=4)
            for metric,value in expected.items():self.assertAlmostEqual(got[metric],value,msg=metric)
            self.assertEqual(java_sloc(base)+java_sloc(child),17)
