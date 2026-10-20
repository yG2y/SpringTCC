import hashlib
import gzip
import csv
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auditar_painel_original import audit, verify_source_tree
from ck_pipeline.extraction import CLASS_COLUMNS, METRICS


class PinnedSourceAuditTests(unittest.TestCase):
    def test_completeness_is_checked_after_raw_means(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);repo=out/'clones/1';repo.mkdir(parents=True)
            env=dict(os.environ,GIT_AUTHOR_DATE='2013-06-01T00:00:00+00:00',GIT_COMMITTER_DATE='2013-06-01T00:00:00+00:00')
            def git(*args):
                return subprocess.check_output(['git',*args],cwd=repo,text=True,env=env).strip()
            git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            content=b'class A {}\n';(repo/'A.java').write_bytes(content)
            git('add','A.java');git('commit','-qm','fixture');sha=git('rev-parse','HEAD')
            inventory=[dict(file='A.java',sha256=hashlib.sha256(content).hexdigest(),sloc=1,is_test=False,measurable_type=True)]
            source_hash=hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()
            key=hashlib.sha256((source_hash+'fixture').encode()).hexdigest()
            folder=out/'extractions'/key;folder.mkdir(parents=True)
            def zipped_csv(name,rows):
                with gzip.open(folder/name,'wt') as f:
                    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            zipped_csv('source_inventory.csv.gz',inventory)
            zipped_csv('class.csv.gz',[{column:1 for column in CLASS_COLUMNS.values()}])
            zipped_csv('method.csv.gz',[dict(loc=1)])
            dest=out/'repositories/1/snapshots/E1';dest.mkdir(parents=True)
            candidate=dict(repository_id='1',full_name='fixture/project',created_at='2013-01-01T00:00:00Z')
            result=dict(candidate,era='E1',sha=sha,pinned_tip=sha,instrument_hash='fixture',
                period_start='2009-01-01T00:00:00+00:00',cutoff='2013-12-31T23:59:59+00:00',
                committed_at='2013-06-01T00:00:00+00:00',authored_at='2013-06-01T00:00:00+00:00',
                status='ok',eligible=False,ia_status='sem_evidencia_detectada',cache_key=key,source_hash=source_hash,
                java_files=1,total_loc=1,production_loc=1,test_loc=0,production_java_files=1,test_java_files=0,
                **{m:1 for m in METRICS})
            (dest/'result.json').write_text(json.dumps(result))
            (dest/'ai_evidence.json').write_text(json.dumps(dict(ia_status='sem_evidencia_detectada',present_evidence=[],historical_evidence=[])))
            (out/'repositories/1/reference.json').write_text(json.dumps(dict(candidate,tip=sha)))
            (out/'instrument.json').write_text(json.dumps(dict(instrument_hash='fixture')))
            with patch('auditar_painel_original.validate_filter',return_value=[candidate]):
                outcome=audit(out)
            self.assertTrue(outcome['passed'],outcome['errors'])
            self.assertEqual(outcome['expected_slots'],1)
            self.assertEqual(outcome['raw_ck_snapshots'],1)

    def test_future_contents_or_missing_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def git(*args):
                return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
            git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            old=b'class A {}\n';new=b'class A { void addedLater() {} }\n'
            (root/'A.java').write_bytes(old);git('add','A.java');git('commit','-qm','old')
            sha=git('rev-parse','HEAD')
            (root/'A.java').write_bytes(new);git('commit','-qam','new')
            inventory=[dict(file='A.java',sha256=hashlib.sha256(old).hexdigest())]
            cache={}
            self.assertEqual(verify_source_tree(root,sha,inventory,cache),[])
            wrong=[dict(file='A.java',sha256=hashlib.sha256(new).hexdigest())]
            self.assertTrue(verify_source_tree(root,sha,wrong,cache))
            self.assertTrue(verify_source_tree(root,sha,[],cache))


if __name__=='__main__': unittest.main()
