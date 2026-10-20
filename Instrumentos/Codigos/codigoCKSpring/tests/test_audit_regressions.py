import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ck_pipeline.extraction import METRICS, digest, write_csv
from relatorio_painel_original import summarize, validate_existing_report

CODE=Path(__file__).resolve().parents[1]


class ReportProvenanceTests(unittest.TestCase):
    def fixture(self, out):
        sample=[dict(repository_id='1',created_at='2013-01-01T00:00:00Z',full_name='fixture/project')]
        records=[dict(sample[0],era=era,status='ok',eligible=True,sha=era,framework='spring_boot',
                      ia_status='sem_evidencia_detectada',**{m:float(i+1) for m in METRICS})
                 for i,era in enumerate(('E1','E2','E3','E4'))]
        for row in records:
            p=out/'repositories/1/snapshots'/row['era']/'result.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps(row))
        hashes={str(p.relative_to(out)):digest(p) for p in sorted((out/'repositories').glob('*/snapshots/*/result.json'))}
        result_hash=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
        (out/'descriptive_report_manifest.json').write_text(json.dumps(dict(collection_complete=True,audit_confirmed=True,result_set_hash=result_hash,sample_sha256='sample')))
        (out/'audit.json').write_text(json.dumps(dict(passed=True,result_set_hash=result_hash,expected_slots=4)))
        for name,rows in summarize(sample,records).items():write_csv(out/(name+'.csv'),rows)
        return sample,[],dict(mode='all540',sample_sha256='sample')

    def test_edited_summary_is_not_accepted_for_article_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);inputs=self.fixture(out)
            with patch('relatorio_painel_original.collection_rows',return_value=inputs):
                self.assertEqual(validate_existing_report(out)['slots'],4)
                path=out/'paired_summary.csv'
                with path.open() as handle: rows=list(csv.DictReader(handle))
                rows[0]['mean_difference']='999';write_csv(path,rows)
                with self.assertRaisesRegex(ValueError,'differs from frozen measurements'):validate_existing_report(out)

    def test_changed_measurement_invalidates_old_success_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);inputs=self.fixture(out)
            p=out/'repositories/1/snapshots/E4/result.json';row=json.loads(p.read_text());row['avg_cbo']=999;p.write_text(json.dumps(row))
            with patch('relatorio_painel_original.collection_rows',return_value=inputs):
                with self.assertRaisesRegex(ValueError,'Stale'):validate_existing_report(out)


class LegacySafetyTests(unittest.TestCase):
    def test_legacy_entrypoints_refuse_before_network_or_measurement(self):
        for name in ('mainBase.py','main_pagination.py','test_ck.py'):
            with self.subTest(script=name):
                result=subprocess.run([sys.executable,str(CODE/name)],cwd=CODE,capture_output=True,text=True,timeout=5)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('painel_original' if name!='test_ck.py' else 'test_ck_adapter',result.stderr)

    def test_old_smoke_test_can_be_imported_without_processes(self):
        with patch('subprocess.run',side_effect=AssertionError('No Java on import')):
            spec=importlib.util.spec_from_file_location('old_smoke',CODE/'test_ck.py')
            spec.loader.exec_module(importlib.util.module_from_spec(spec))

    def test_archived_synthetic_metrics_cannot_return_a_number(self):
        # Compile only these method definitions: importing archival collectors loads .env.
        import ast
        for filename in ('mainBase.py','main_pagination.py'):
            tree=ast.parse((CODE/'legacy'/filename).read_text())
            for node in ast.walk(tree):
                if isinstance(node,ast.FunctionDef) and node.name in {'analyze_code_duplication','calculate_maintainability_index'}:
                    node.returns=None
                    for arg in node.args.args:arg.annotation=None
                    namespace={};exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),namespace)
                    with self.assertRaises(NotImplementedError):
                        namespace[node.name](*([None]*len(node.args.args)))
