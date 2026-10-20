import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analisar_painel_original import choose, filter_rows, period_snapshots, prepare, validate_filter
from ck_pipeline.extraction import METRICS, digest, write_csv
from evolution.measurement import eligibility
from spring_boot_selection.filters import run_filters
from spring_boot_selection.util import parse_iso


def row(rid, created):
    return dict(repository_id=str(rid), full_name='fixture/r'+str(rid), created_at=created)


class OriginalSelectionTests(unittest.TestCase):
    def test_creation_cutoff_includes_whole_last_day_and_uses_utc(self):
        rows = [row(1,'2017-12-31T23:59:59Z'), row(2,'2018-01-01T00:00:00Z'),
                row(3,'2017-12-31T22:00:00-03:00'), row(4,'invalid'), row(5,'2013-01-01T00:00:00Z')]
        kept, excluded = filter_rows(rows)
        self.assertEqual([r['repository_id'] for r in kept], ['1','5'])
        self.assertEqual(len(excluded), 3)
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            filter_rows(rows+rows[:1])

    def test_modes_do_not_mix_520_later_with_20_old(self):
        early = [row(i,'2013-01-01T00:00:00Z') for i in range(20)]
        later = [row(i,'2017-01-01T00:00:00Z') for i in range(20,540)]
        self.assertEqual(len(choose(early+later,'all540')),540)
        self.assertEqual(choose(early+later,'e2_520'),choose(list(reversed(early+later)),'e2_520'))
        subset = choose(early+later,'combined520')
        self.assertEqual(len(subset),520)
        self.assertTrue({r['repository_id'] for r in early} <= {r['repository_id'] for r in subset})
        self.assertEqual(subset,choose(list(reversed(early+later)),'combined520'))

    def test_changed_population_is_rejected_even_if_manifest_hash_is_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'source.csv'; out=root/'out'; out.mkdir()
            rows=[row(1,'2013-01-01T00:00:00Z')]
            write_csv(source,rows); write_csv(out/'eligible_repositories.csv',[row(999,'2013-01-01T00:00:00Z')])
            (out/'filter_manifest.json').write_text(json.dumps({'source_sha256':digest(source), 'filtered_sha256':digest(out/'eligible_repositories.csv')}))
            with patch('analisar_painel_original.BASE',source), patch('analisar_painel_original.BASE_HASH',digest(source)):
                with self.assertRaisesRegex(ValueError,'exactly'):
                    validate_filter(out)

    def test_generic_filter_supports_creation_cutoff_before_other_filters(self):
        rows=[dict(row(i,date),language='Java',size_kb=10,default_branch='main') for i,date in [(1,'2017-12-31T23:59:59Z'),(2,'2018-01-01T00:00:00Z')]]
        with tempfile.TemporaryDirectory() as tmp:
            result=run_filters(rows, {'creation':{'before':'2018-01-01T00:00:00Z'},'exclude':{'inactive':False}},Path(tmp))
        self.assertEqual([r['repository_id'] for r in result['eligible']],['1'])
        self.assertEqual(result['attrition'][1]['stage'],'remove_creation_date')


class EndpointTests(unittest.TestCase):
    def commit(self,sha,date,ancestry=None):
        return dict(sha=sha,committed=parse_iso(date),authored=parse_iso(date),ancestry_max_date=parse_iso(ancestry or date))

    def test_era_boundary_no_current_code_and_no_carry_from_other_era(self):
        commits={'a':self.commit('a','2013-12-31T23:59:59Z'),
                 'b':self.commit('b','2014-01-01T00:00:00Z'),
                 'c':self.commit('c','2026-01-01T00:00:00Z')}
        rows=period_snapshots(commits,list(commits),parse_iso('2026-10-15T00:00:00Z'),True)
        self.assertEqual(rows[0]['sha'],'a');self.assertEqual(rows[1]['sha'],'b')
        self.assertEqual(rows[2]['status'],'missing_snapshot');self.assertNotIn('sha',rows[2])
        self.assertEqual(rows[3]['sha'],'c')
        self.assertEqual(len(period_snapshots(commits,list(commits),parse_iso('2026-10-15T00:00:00Z'),False)),3)

    def test_future_ancestry_rejected_without_choosing_earlier_convenient_commit(self):
        commits={'a':self.commit('a','2010-01-01T00:00:00Z'),
                 'b':self.commit('b','2013-12-31T23:59:59Z','2014-01-01T00:00:00Z')}
        first=period_snapshots(commits,list(commits),parse_iso('2026-10-15T00:00:00Z'),True)[0]
        self.assertEqual(first['status'],'temporal_anomaly');self.assertEqual(first['sha'],'b')

    def test_cutoff_limits_e4_and_preserves_missing_metrics(self):
        commits={'a':self.commit('a','2026-10-16T00:00:00Z')}
        last=period_snapshots(commits,list(commits),parse_iso('2026-10-15T00:00:00Z'),True)[-1]
        self.assertEqual(last['status'],'missing_snapshot')
        self.assertNotIn('avg_cbo',last)


class SizeCriteriaTests(unittest.TestCase):
    def test_both_size_limits_and_missing_counts(self):
        measured=dict(status='ok',total_loc=2000,java_files=10,**{m:1.0 for m in METRICS})
        framework=dict(framework_confirmed=True,diagnostics=[])
        self.assertEqual(eligibility(measured,framework),[])
        self.assertIn('below_10_java_files',eligibility(dict(measured,java_files=9),framework))
        self.assertIn('below_2000_loc',eligibility(dict(measured,total_loc=1999),framework))
        missing=dict(measured);missing.pop('total_loc');missing.pop('java_files')
        reasons=eligibility(missing,framework)
        self.assertIn('missing_loc',reasons);self.assertIn('missing_java_files',reasons)


if __name__ == '__main__':
    unittest.main()
