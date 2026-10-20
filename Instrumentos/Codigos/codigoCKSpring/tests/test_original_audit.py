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

from auditar_painel_original import audit, verify_source_tree, record_contract
from ck_pipeline.extraction import CLASS_COLUMNS, METRICS, aggregate
from evolution.framework import detect


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
            classes=[dict({column:1 for column in CLASS_COLUMNS.values()},file='A.java',**{'class':'A','loc':1,'lcom':0})]
            methods=[dict(file='A.java',loc=1)]
            zipped_csv('class.csv.gz',classes)
            zipped_csv('method.csv.gz',methods)
            dest=out/'repositories/1/snapshots/E1';dest.mkdir(parents=True)
            candidate=dict(repository_id='1',full_name='fixture/project',created_at='2013-01-01T00:00:00Z')
            result=dict(candidate,era='E1',sha=sha,pinned_tip=sha,instrument_hash='fixture',
                period_start='2009-01-01T00:00:00+00:00',cutoff='2013-12-31T23:59:59+00:00',
                committed_at='2013-06-01T00:00:00+00:00',authored_at='2013-06-01T00:00:00+00:00',
                status='ok',eligible=False,ia_status='sem_evidencia_detectada',cache_key=key,source_hash=source_hash,
                java_files=1,total_loc=1,production_loc=1,test_loc=0,production_java_files=1,test_java_files=0,
                exclusion_reasons='below_2000_loc', **aggregate(classes,methods))
            result.update({'production_'+k:v for k,v in aggregate(classes,methods).items()})
            result.update({'test_'+k:v for k,v in aggregate([],[]).items()})
            framework=detect(repo,['A.java'],candidate['full_name'])
            result.update({k:v for k,v in framework.items() if k not in {'evidence','diagnostics'}})
            (dest/'framework_evidence.json').write_text(json.dumps(framework))
            (dest/'result.json').write_text(json.dumps(result))
            (dest/'ai_evidence.json').write_text(json.dumps(dict(ia_status='sem_evidencia_detectada',present_evidence=[],historical_evidence=[])))
            (out/'repositories/1/reference.json').write_text(json.dumps(dict(candidate,tip=sha)))
            (out/'instrument.json').write_text(json.dumps(dict(instrument_hash='fixture')))
            with patch('auditar_painel_original.validate_filter',return_value=[candidate]):
                outcome=audit(out,out/'separate_audit.json')
            self.assertFalse((out/'audit.json').exists())
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

class ContractAuditTests(unittest.TestCase):
    def fixture(self):
        candidate=dict(created_at='2013-01-01T00:00:00Z')
        result=dict(candidate,era='E1',period_start='2009-01-01T00:00:00Z',cutoff='2013-12-31T23:59:59Z',
            status='ok',eligible=True,sha='sha',cache_key='cache',framework='spring_boot',framework_confirmed=True,
            exclusion_reasons='',submodules=0,source_coverage=1,files_without_class_output=0,ck_error_signals=0,
            java_files=10,total_loc=2000,**{m:1 for m in METRICS})
        return result,candidate

    def test_wrong_historical_boundary_cannot_pass_using_its_own_cutoff(self):
        result,candidate=self.fixture()
        self.assertEqual(record_contract(result,candidate,{}),[])
        result['cutoff']='2026-12-31T23:59:59Z'
        self.assertIn('wrong_era_cutoff',record_contract(result,candidate,{}))

    def test_false_eligibility_and_exclusion_are_rejected(self):
        result,candidate=self.fixture()
        result.update(framework='not_confirmed',framework_confirmed=False,status='partial_ck',source_coverage=.9)
        errors=record_contract(result,candidate,{})
        self.assertIn('eligible_without_confirmed_framework',errors)
        self.assertIn('eligible_without_successful_extraction',errors)
        self.assertIn('eligible_without_complete_coverage',errors)
        result.update(eligible=False,exclusion_reasons='')
        self.assertIn('ineligible_without_reason',record_contract(result,candidate,{}))
