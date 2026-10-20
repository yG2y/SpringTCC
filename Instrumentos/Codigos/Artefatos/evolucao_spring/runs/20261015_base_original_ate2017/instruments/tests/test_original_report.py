"""Checks the scientific denominators, not the HTML presentation."""
import unittest

from ck_pipeline.extraction import METRICS
from relatorio_painel_original import summarize


def candidate(rid,year):
    return dict(repository_id=str(rid),created_at=f'{year}-01-01T00:00:00Z')


def observation(row,era,value,eligible=True,ai='sem_evidencia_detectada'):
    return dict(row,era=era,sha='test',status='ok',eligible=eligible,
                framework='spring_boot',ia_status=ai,**{m:value for m in METRICS})


class OriginalReportTests(unittest.TestCase):
    def test_denominators_are_projects_not_classes_or_snapshots(self):
        old=candidate(1,2013);later=candidate(2,2017)
        rows=[observation(old,'E1',2),observation(old,'E2',4),observation(later,'E2',10),
              observation(old,'E3',6),observation(later,'E3',100,eligible=False),
              observation(old,'E4',8,ai='com_evidencia'),observation(later,'E4',12)]
        result=summarize([old,later],rows)
        e2=next(r for r in result['cohort_era_summary'] if r['cohort']=='todos' and r['era']=='E2')
        self.assertEqual(e2['avg_cbo'],7)
        pairs=[r for r in result['paired_summary'] if r['cohort']=='todos' and r['before_era']=='E2' and r['after_era']=='E3']
        self.assertTrue(all(r['n_pairs']==1 and r['mean_difference']==2 for r in pairs))
        balanced=result['balanced_panel']
        self.assertTrue(all(r['n_projects']==1 and r['repository_ids']=='1' for r in balanced if r['cohort']=='ate2013'))
        self.assertTrue(all(r['n_projects']==0 and r['avg_cbo'] is None for r in balanced if r['cohort']=='2014_2017'))
        ia=[r for r in result['ai_ck_comparison'] if r['cohort']=='todos' and r['era']=='E4']
        self.assertTrue(all(r['n_a']==r['n_b']==1 and r['difference_a_minus_b']==-4 for r in ia))

    def test_no_missing_data_as_zero_or_foreign_projects(self):
        old=candidate(1,2013)
        result=summarize([old],[])
        self.assertTrue(all(r['avg_cbo'] is None for r in result['cohort_era_summary']))
        row=observation(old,'E1',1)
        with self.assertRaises(ValueError): summarize([old],[row,row])
        with self.assertRaises(ValueError): summarize([old],[observation(candidate(2,2017),'E2',1)])
        with self.assertRaises(ValueError): summarize([candidate(2,2017)],[observation(candidate(2,2017),'E1',1)])


if __name__=='__main__':
    unittest.main()
