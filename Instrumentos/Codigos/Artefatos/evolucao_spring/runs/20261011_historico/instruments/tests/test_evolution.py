import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ck_pipeline.extraction import METRICS, atomic_json, write_csv
from evolution.framework import detect
from evolution.history import ai_at_snapshot, ai_history, annual_snapshots, git, materialize, read_history, redact
from evolution.measurement import CODE, eligibility, instrument, measure
from evolution.collection import process
from evolution.reporting import project_eras, transitions
from evolution.selection import historical_config, plan, sample
from spring_boot_selection.filters import run_filters
from spring_boot_selection.util import parse_iso


def candidate(i, **kw):
    return dict(repository_id=str(i),full_name='fixture/r'+str(i),language='Java',created_at='2010-01-01T00:00:00Z',
                pushed_at='2010-01-01T00:00:00Z',archived='true',size_kb='50',default_branch='main',
                is_fork='false',disabled='false',is_template='false',**kw)


class SelectionTests(unittest.TestCase):
    def test_archived_inactive_unknown_dates_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows=[candidate(1),candidate(2),candidate(3)]
            rows[1]['pushed_at']='invalid'; rows[2]['disabled']='true'
            result=run_filters(rows,historical_config(),Path(tmp),parse_iso('2026-10-11T00:00:00Z'))
            self.assertEqual({r['repository_id'] for r in result['eligible']},{'1','2'})
            self.assertFalse(any(r['stage'] in {'remove_inactive','remove_archived'} for r in result['attrition']))

    def test_sampling_independent_of_activity_and_input_order(self):
        rows=[candidate(i) for i in range(80)]
        cutoff=parse_iso('2026-10-11T00:00:00Z')
        first=sample(rows,cutoff,limit=30)
        for i,r in enumerate(rows): r['pushed_at']='2026-10-01T00:00:00Z' if i%2 else ''
        second=sample(list(reversed(rows)),cutoff,limit=30)
        identity=lambda rs:[(r['repository_id'],r['lottery_rank'],r['pilot']) for r in rs]
        self.assertEqual(identity(first),identity(second))
        self.assertEqual(sum(r['pilot'] for r in first),10)

    def test_plan_requires_complete_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);atomic_json(out/'discovery_status.json',{'status':'incomplete'})
            with self.assertRaises(ValueError): plan(out)


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.repo=Path(self.tmp.name)/'repo';self.repo.mkdir()
        subprocess.run(['git','init','-q',str(self.repo)],check=True)
        self.base=self.commit({'pom.xml':'<project><dependencies><dependency><groupId>org.springframework</groupId><artifactId>spring-context</artifactId><version>3.0.0</version></dependency></dependencies></project>',
                              'src/main/java/A.java':'class A { int f(){return 1;} }'},'2009-12-31T23:59:59Z')

    def tearDown(self): self.tmp.cleanup()

    def commit(self,files,date,parents=(),message='fixture',author_date=None):
        for path,text in files.items():
            f=self.repo/path
            if text is None:
                if f.exists(): f.unlink()
            else:
                f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
        git(self.repo,'add','-A')
        tree=git(self.repo,'write-tree').strip()
        command=['git','commit-tree',tree,'-m',message]
        for parent in parents: command+=['-p',parent]
        env=dict(os.environ,GIT_AUTHOR_NAME='Fixture',GIT_AUTHOR_EMAIL='fixture@example.test',GIT_COMMITTER_NAME='Fixture',
                 GIT_COMMITTER_EMAIL='fixture@example.test',GIT_AUTHOR_DATE=author_date or date,GIT_COMMITTER_DATE=date)
        p=subprocess.run(command,cwd=self.repo,env=env,check=True,text=True,capture_output=True)
        sha=p.stdout.strip();git(self.repo,'update-ref','refs/heads/main',sha);git(self.repo,'symbolic-ref','HEAD','refs/heads/main')
        return sha

    def snapshots(self,tip):
        cs,line,diag=read_history(self.repo,tip)
        return cs,line,diag,annual_snapshots(cs,line,parse_iso('2026-10-11T00:00:00Z'))

    def test_utc_boundary_absence_and_repeated_sha(self):
        second=self.commit({'src/main/java/B.java':'class B {}'},'2010-01-01T00:00:00Z',[self.base])
        _,_,_,snaps=self.snapshots(second)
        self.assertEqual(snaps[0]['sha'],self.base)
        self.assertEqual(snaps[1]['sha'],second)
        self.assertTrue(snaps[2]['no_new_commit'])
        self.assertTrue(snaps[-1]['partial'])
        cs,line,_=read_history(self.repo,second)
        missing=annual_snapshots(cs,line,parse_iso('2026-10-11T00:00:00Z'),start=2008)[0]
        self.assertEqual(missing['status'],'missing_snapshot');self.assertNotIn('avg_cbo',missing)

    def test_branch_evidence_waits_for_integration(self):
        feature=self.commit({'AGENTS.md':'Agent guidance'},'2011-01-01T00:00:00Z',[self.base],
                            'feature\n\nCo-authored-by: Claude <claude@anthropic.com>')
        main=self.commit({'AGENTS.md':None},'2012-01-01T00:00:00Z',[self.base])
        merged=self.commit({'AGENTS.md':'Agent guidance'},'2014-01-01T00:00:00Z',[main,feature])
        cs,line,_,snaps=self.snapshots(merged)
        events=ai_history(self.repo,merged,cs,line)
        before=ai_at_snapshot(self.repo,next(s for s in snaps if s['year']==2013),events)
        after=ai_at_snapshot(self.repo,next(s for s in snaps if s['year']==2014),events)
        self.assertEqual(before['ia_status'],'sem_evidencia_detectada')
        self.assertEqual(after['ia_status'],'com_evidencia')
        self.assertTrue(any(e['type']=='coauthor' for e in after['historical_evidence']))

    def test_deleted_file_retains_observed_history_not_present(self):
        first=self.commit({'AGENTS.md':'Agent guidance'},'2024-01-01T00:00:00Z',[self.base])
        second=self.commit({'AGENTS.md':None},'2025-01-01T00:00:00Z',[first])
        cs,line,_,snaps=self.snapshots(second);events=ai_history(self.repo,second,cs,line)
        r=ai_at_snapshot(self.repo,next(s for s in snaps if s['year']==2025),events)
        self.assertFalse(r['ia_present']);self.assertTrue(r['ia_history'])

    def test_future_tip_cannot_leak_ai(self):
        future=self.commit({'CLAUDE.md':'Future'},'2026-12-01T00:00:00Z',[self.base])
        cs,line,_,snaps=self.snapshots(future);events=ai_history(self.repo,future,cs,line)
        self.assertEqual(snaps[-1]['sha'],self.base)
        self.assertEqual(ai_at_snapshot(self.repo,snaps[-1],events)['ia_status'],'sem_evidencia_detectada')

    def test_merge_file_removed_before_annual_cut_still_observed(self):
        feature=self.commit({'CLAUDE.md':'Guide'},'2023-01-01T00:00:00Z',[self.base])
        main=self.commit({'CLAUDE.md':None},'2024-01-01T00:00:00Z',[self.base])
        merge=self.commit({'CLAUDE.md':'Guide'},'2025-01-01T00:00:00Z',[main,feature])
        removed=self.commit({'CLAUDE.md':None},'2025-06-01T00:00:00Z',[merge])
        cs,line,_,snaps=self.snapshots(removed)
        result=ai_at_snapshot(self.repo,next(r for r in snaps if r['year']==2025),ai_history(self.repo,removed,cs,line))
        self.assertFalse(result['ia_present']);self.assertTrue(result['ia_history'])

    def test_nonmonotonic_ancestry_diagnosed_no_fallback(self):
        future=self.commit({'future.txt':'x'},'2030-01-01T00:00:00Z',[self.base])
        backdated=self.commit({'past.txt':'x'},'2013-01-01T00:00:00Z',[future])
        _,_,diag,snaps=self.snapshots(backdated)
        snapshot=next(s for s in snaps if s['year']==2013)
        self.assertEqual(snapshot['status'],'temporal_anomaly')
        self.assertEqual(snapshot['sha'],backdated);self.assertTrue(diag)

    def test_shallow_history_rejected(self):
        clone=Path(self.tmp.name)/'shallow'
        subprocess.run(['git','clone','-q','--depth=1',self.repo.as_uri(),str(clone)],check=True)
        with self.assertRaisesRegex(ValueError,'shallow'):read_history(clone,self.base)

    def test_export_ignore_does_not_hide_sources(self):
        sha=self.commit({'.gitattributes':'src export-ignore\n'},'2010-01-01T00:00:00Z',[self.base])
        dest=Path(self.tmp.name)/'export'
        materialize(self.repo,sha,dest,lambda p:p.endswith('.java'))
        self.assertTrue((dest/'src/main/java/A.java').exists())


class FrameworkTests(unittest.TestCase):
    def detect(self,files,name='test/app'):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for p,text in files.items():
                f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
            return detect(root,list(files),name)

    def test_test_dependency_not_production(self):
        result=self.detect({'pom.xml':'<project><dependencies><dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-test</artifactId><scope>test</scope></dependency></dependencies></project>'})
        self.assertEqual(result['framework'],'test_only');self.assertFalse(result['framework_confirmed'])

    def test_parent_and_actual_spring_dependency(self):
        result=self.detect({'pom.xml':'<project><parent><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-parent</artifactId><version>1.0.0.RC1</version></parent><dependencies><dependency><groupId>org.springframework</groupId><artifactId>spring-context</artifactId></dependency></dependencies></project>'})
        self.assertEqual(result['framework'],'spring_boot');self.assertTrue(result['boot_prerelease'])

    def test_catalog_requires_usage_and_correct_version(self):
        catalog='[versions]\nboot="3.2.0"\ndocker="10.0.0"\n[libraries]\nboot-web={module="org.springframework.boot:spring-boot-starter-web", version.ref="boot"}\n[plugins]\ndocker={id="com.bmuschko.docker-remote-api", version.ref="docker"}\n'
        alone=self.detect({'gradle/libs.versions.toml':catalog})
        self.assertFalse(alone['framework_confirmed'])
        used=self.detect({'gradle/libs.versions.toml':catalog,'build.gradle.kts':'dependencies {\n implementation(libs.boot.web)\n}\n'})
        self.assertEqual(used['framework_versions'],'3.2.0');self.assertTrue(used['boot_present'])

    def test_framework_itself_is_separate(self):
        result=self.detect({'pom.xml':'<project><groupId>org.springframework.boot</groupId><artifactId>spring-boot</artifactId></project>'},'spring-projects/spring-boot')
        self.assertEqual(result['framework'],'framework_source');self.assertFalse(result['boot_present'])

    def test_traditional_gradle_map_and_inline_dependency(self):
        result=self.detect({'build.gradle':'''dependencies { compile group: 'org.springframework', name: 'spring-context', version: '3.2.0' }'''})
        self.assertEqual(result['framework'],'spring_traditional')
        inline=self.detect({'build.gradle':'''dependencies { implementation('org.springframework.boot:spring-boot-starter-web:3.0.0') }'''})
        self.assertEqual(inline['framework'],'spring_boot')

    def test_unapplied_boot_plugin_not_adoption(self):
        result=self.detect({'build.gradle':'''plugins { id 'org.springframework.boot' version '3.0.0' apply false }
dependencies { implementation 'org.springframework:spring-context:6.0.0' }'''})
        self.assertEqual(result['framework'],'spring_traditional')

    def test_invalid_xml_diagnostic_not_confirmation(self):
        result=self.detect({'pom.xml':'<invalid> org.springframework.boot'})
        self.assertFalse(result['framework_confirmed']);self.assertTrue(result['diagnostics'])


class SummaryTests(unittest.TestCase):
    def row(self,rid,year,value,**kw):
        return dict(repository_id=str(rid),full_name='fixture/'+str(rid),year=year,sha=str(year),eligible=True,
                    creation_cohort='E1',measurement_period='E3',ia_status='sem_evidencia_detectada',ia_history=False,ia_present=False,
                    framework='spring_traditional',framework_confirmed=True,boot_present=False,total_loc=2000,partial=False,status='ok',
                    **{m:value for m in METRICS},**kw)

    def test_one_contribution_per_project_era(self):
        rows=[self.row(1,2018,2),self.row(1,2019,4),self.row(2,2018,20)]
        summary=project_eras(rows)
        self.assertEqual(len(summary),2);self.assertEqual(summary[0]['avg_cbo'],3)

    def test_mixed_ia_epoch_is_not_counted_twice(self):
        first=self.row(1,2018,2);last=self.row(1,2019,4);last['ia_status']='com_evidencia'
        result=project_eras([first,last]);self.assertEqual(result[0]['ia_group'],'transicao_observada')

    def test_pairing_is_within_project_not_between_groups(self):
        a=self.row(1,2013,2);b=self.row(1,2014,4);b.update(boot_present=True,framework='spring_boot')
        c=self.row(2,2014,99);c.update(boot_present=True,framework='spring_boot')
        events,pairs=transitions([a,b,c])
        self.assertEqual(len(pairs),7);self.assertTrue(all(r['difference']==2 for r in pairs))
        self.assertTrue(next(r for r in events if r['repository_id']=='2')['left_censored'])

    def test_missing_measurements_never_zero(self):
        measured={'status':'error','total_loc':5000}
        fw={'framework_confirmed':True,'diagnostics':[]}
        self.assertIn('missing_metric',eligibility(measured,fw))

    def test_redaction(self):
        self.assertNotIn('ghp_',redact('author ghp_'+'x'*36))


class CKIntegrationTests(GitFixture):
    def test_real_ck_cache_invalidation_and_resume(self):
        out=Path(self.tmp.name)/'results';out.mkdir();(out/'work').mkdir()
        config=instrument(out)
        source=Path(self.tmp.name)/'sources';source.mkdir()
        (source/'A.java').write_text('class A { int x; int f(int y) { if(y>0) return x+y; return x; } }')
        first=measure(source,['A.java'],config,out)
        self.assertEqual(first['status'],'ok')
        self.assertTrue(all(first.get(m) is not None for m in METRICS))
        with patch('evolution.measurement.subprocess.run',side_effect=AssertionError('cache should be reused')):
            same=measure(source,['A.java'],config,out)
        self.assertTrue(same['cache_hit']);self.assertEqual(first['cache_key'],same['cache_key'])
        changed_config=dict(config,instrument_hash='another-instrument')
        changed=measure(source,['A.java'],changed_config,out)
        self.assertNotEqual(changed['cache_key'],first['cache_key'])
        # End-to-end annual collection uses the same fixed reference on resume.
        row=dict(candidate(1),creation_cohort='E1')
        ref=dict(tip=self.base,reference='refs/heads/main')
        with patch('evolution.collection.pin_clone',return_value=(self.repo,ref)):
            r=process(row,config,out,parse_iso('2026-10-11T00:00:00Z'))
            self.assertEqual(r['status'],'complete');self.assertEqual(r['snapshots'],18)
            with patch('evolution.collection.measure',side_effect=AssertionError('completed snapshots must resume')):
                resumed=process(row,config,out,parse_iso('2026-10-11T00:00:00Z'))
            self.assertEqual(resumed['status'],'complete')
        later=json.loads((out/'repositories/1/snapshots/2020/result.json').read_text())
        self.assertFalse(later['eligible']);self.assertIn('below_2000_loc',later['exclusion_reasons'])
        self.assertEqual(later['sha'],self.base);self.assertTrue(later['no_new_commit'])
        self.assertGreater(later['avg_wmc'],0)

    def test_failed_extraction_is_explicit_and_retryable(self):
        out=Path(self.tmp.name)/'failed';out.mkdir();(out/'work').mkdir()
        config=instrument(out)
        source=Path(self.tmp.name)/'java';source.mkdir();(source/'A.java').write_text('class A { int f(){ return 1; } }')
        with patch('evolution.measurement.subprocess.run',side_effect=subprocess.TimeoutExpired('java',1)):
            failed=measure(source,['A.java'],config,out)
        self.assertEqual(failed['status'],'error');self.assertNotIn('avg_cbo',failed)
        recovered=measure(source,['A.java'],config,out,retry_errors=True)
        self.assertEqual(recovered['status'],'ok')

    def test_retrieval_failure_records_every_cut_and_can_resume(self):
        out=Path(self.tmp.name)/'retrieval';out.mkdir();(out/'work').mkdir()
        config=instrument(out);row=dict(candidate(1),creation_cohort='E1')
        cutoff=parse_iso('2026-10-11T00:00:00Z')
        with patch('evolution.collection.pin_clone',side_effect=ValueError('unavailable')):
            failed=process(row,config,out,cutoff)
        self.assertEqual(failed['status'],'error')
        files=list((out/'repositories/1/snapshots').glob('*/result.json'))
        self.assertEqual(len(files),18)
        self.assertTrue(all(json.loads(f.read_text())['status']=='retrieval_error' for f in files))
        ref=dict(tip=self.base,reference='refs/heads/main')
        with patch('evolution.collection.pin_clone',return_value=(self.repo,ref)):
            resumed=process(row,config,out,cutoff,retry_errors=True)
        self.assertEqual(resumed['status'],'complete')
        self.assertTrue(all(json.loads(f.read_text())['status']=='ok' for f in files))


if __name__=='__main__': unittest.main()
