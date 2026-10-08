import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ck_pipeline.extraction import aggregate, cohort, has_measurable_type, detect_ai, is_source, is_test, java_sloc, spring_boot
from ck_pipeline.statistics import mw, kw, dunn
from analisar_ck import load_classification, consolidate

class ExtractionTests(unittest.TestCase):
    def test_annotation_coverage_and_record_limitations(self):
        self.assertFalse(has_measurable_type('public @interface Flag {}'))
        self.assertFalse(has_measurable_type('// class Pretend {}\n public @interface Flag {}'))
        self.assertTrue(has_measurable_type('record Point(int x) {}'))
        self.assertTrue(has_measurable_type('class X {}'))
        self.assertTrue(has_measurable_type('enum Choice {A,B}'))
        self.assertTrue(has_measurable_type('interface X {}'))

    def test_cohort_boundaries(self):
        for date, expected in [('2008-12-31','fora_das_coortes'),('2009-01-01','E1'),('2013-12-31','E1'),('2014-01-01','E2'),('2018-01-01','E3'),('2022-01-01','E4')]:
            self.assertEqual(cohort(date+'T00:00:00Z'), expected)

    def test_sloc_comments_strings_and_textblocks(self):
        source = '\n// hi\nclass A { /* x\ncontinued */\nString url="http://x";\nString t="""\n// literal\n/* literal */\n""";\n}\n'
        self.assertEqual(java_sloc(source), 7)

    def test_directories_and_test_scope(self):
        self.assertFalse(is_source('a/target/X.java'))
        self.assertFalse(is_source('.hidden/X.java'))
        self.assertTrue(is_source('src/main/java/X.java'))
        self.assertTrue(is_test('mod/src/test/java/X.java'))
        self.assertFalse(is_test('src/main/java/Contest.java'))

    def test_lcom_star_zeros_and_missing(self):
        classes = [{k:'0' for k in ('cbo','rfc','wmc','dit','noc','loc','lcom','lcom*')} for _ in range(3)]
        classes[0].update({'lcom':'100','lcom*':'0.5','cbo':'6'})
        classes[1]['lcom*']='NaN'
        result = aggregate(classes,[{'loc':'3'},{'loc':'9'}])
        self.assertEqual(result['avg_lcom'], .25)
        self.assertEqual(result['n_lcom_star'], 2)
        self.assertEqual(result['avg_cbo'], 2)
        self.assertEqual(result['avg_loc_method'], 6)
        self.assertAlmostEqual(result['avg_lcom_legacy'],100/3)

    def test_ai_nested_directory_and_no_commit_request(self):
        with tempfile.TemporaryDirectory() as d, patch('ck_pipeline.extraction.run',side_effect=AssertionError('Unexpected git')):
            r=detect_ai(Path(d),['.roo/rules.md'])
            self.assertEqual(r['ia_status'],'com_evidencia')
            self.assertEqual(r['ia_level'],1)

    def test_ai_commit_mentions_are_not_trailers(self):
        raw='abc\x002026-01-01\x00Human\x00human@example.org\x00Document aider and claude@anthropic.com\x00\x1e'
        with tempfile.TemporaryDirectory() as d, patch('ck_pipeline.extraction.run',return_value=raw):
            self.assertEqual(detect_ai(Path(d),[])['ia_status'],'sem_evidencia_detectada')
        raw=raw.replace('Document aider and claude@anthropic.com','Change\nCo-authored-by: Claude <claude@anthropic.com>')
        with tempfile.TemporaryDirectory() as d, patch('ck_pipeline.extraction.run',return_value=raw):
            self.assertEqual(detect_ai(Path(d),[])['ia_level'],2)

    def test_git_failure_never_becomes_negative(self):
        with tempfile.TemporaryDirectory() as d, patch('ck_pipeline.extraction.run',side_effect=RuntimeError('git error')):
            with self.assertRaises(RuntimeError): detect_ai(Path(d),[])

    def test_gitignore_comment_is_not_evidence(self):
        raw='abc\x002026\x00Human\x00human@example.org\x00message\x00\x1e'
        with tempfile.TemporaryDirectory() as d, patch('ck_pipeline.extraction.run',return_value=raw):
            root=Path(d); (root/'.gitignore').write_text('# CLAUDE.md\n!.cursor/\n')
            self.assertEqual(detect_ai(root,['.gitignore'])['ia_status'],'sem_evidencia_detectada')
            (root/'.gitignore').write_text('.cursor/\n')
            self.assertEqual(detect_ai(root,['.gitignore'])['ia_level'],1)

    def test_boot_property_resolution(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'pom.xml').write_text('<project xmlns="http://maven.apache.org/POM/4.0.0"><properties><spring.version>3.2.1</spring.version></properties><parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>${spring.version}</version></parent></project>')
            result=spring_boot(root,['pom.xml'])
            self.assertTrue(result['spring_boot_confirmed'])
            self.assertEqual(result['spring_boot_versions'],'3.2.1')
            self.assertEqual(result['spring_boot_major'],'3')

    def test_metadata_does_not_confirm_boot(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'pom.xml').write_text('<project><!-- org.springframework.boot --><description>org.springframework.boot</description></project>')
            self.assertFalse(spring_boot(root,['pom.xml'])['spring_boot_confirmed'])

    def test_external_error_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ai.csv'; p.write_text('repository_id,ia_detectada,erro\n1,False,403\n')
            self.assertEqual(load_classification(p,{'1'})['1']['ia_status'],'indeterminada')
            with self.assertRaises(ValueError): load_classification(p,{'2'})

    def test_partial_status_not_complete(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d); p=out/'repositories/1'; p.mkdir(parents=True)
            (p/'result.json').write_text(json.dumps({'repository_id':'1','status':'error','ia_status':'indeterminada','eligible':False}))
            r=consolidate(out,[{'repository_id':'1'},{'repository_id':'2'}])
            self.assertFalse(r['complete']); self.assertEqual(r['pending'],1)

class StatisticsTests(unittest.TestCase):
    def test_cliffs_delta_direction(self):
        r=mw([3,4,5],[0,1,2])
        self.assertEqual(r['cliffs_delta_a_minus_b'],1)
        self.assertEqual(mw([0,1,2],[3,4,5])['cliffs_delta_a_minus_b'],-1)
        self.assertAlmostEqual(r['p_adjusted'],min(1,r['p_raw']*7))

    def test_ties_and_insufficient_n(self):
        self.assertEqual(mw([0,0],[0,0])['p_adjusted'],1)
        self.assertEqual(mw([0],[1,2])['status'],'insufficient_n')
        self.assertEqual(kw([[1,2],[3,4],[],[5,6]])['status'],'insufficient_n')

    def test_dunn_fixed_family_and_ties(self):
        rows=dunn({'E1':[0,0],'E2':[0,1],'E3':[2,3],'E4':[8,9]})
        self.assertEqual(len(rows),6)
        for r in rows:
            self.assertEqual(r['family_tests'],42)
            self.assertAlmostEqual(r['p_adjusted'],min(1,r['p_raw']*42))
        self.assertTrue(all(r['p_raw']==1 for r in dunn({'A':[0,0],'B':[0,0]})))

if __name__=='__main__': unittest.main()
