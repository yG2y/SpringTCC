import unittest
import pandas as pd
from ck_pipeline.cohorts import match_covariates,paired_tests,primary_tests
from ck_pipeline.extraction import METRICS


def row(rid,ai,epoch='E3',boot='3',loc=4000):
    r={'repository_id':str(rid),'full_name':'repo/'+str(rid),'ia_status':ai,'epoch':epoch,'spring_boot_major':boot,'total_loc':loc,'stargazers_count':50,'age_years':5}
    r.update({m:float(rid) for m in METRICS})
    return r


class CohortAnalysisTests(unittest.TestCase):
    def test_matching_respects_epoch_known_version_and_size(self):
        frame=pd.DataFrame([row(1,'com_evidencia'),row(2,'sem_evidencia_detectada',loc=4500),
                            row(3,'sem_evidencia_detectada',epoch='E2'),row(4,'sem_evidencia_detectada',boot='2'),
                            row(5,'com_evidencia',boot='unknown'),row(6,'sem_evidencia_detectada',boot='unknown'),
                            row(7,'com_evidencia',epoch='E4',loc=10000),row(8,'sem_evidencia_detectada',epoch='E4',loc=2000)])
        pairs=match_covariates(frame)
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]['ia_repository_id'],'1')
        self.assertEqual(pairs[0]['control_repository_id'],'2')

    def test_matching_never_reuses_controls_or_uses_outcomes(self):
        frame=pd.DataFrame([row(1,'com_evidencia'),row(2,'com_evidencia'),row(3,'sem_evidencia_detectada')])
        first=match_covariates(frame)
        frame[list(METRICS)]=999999.
        second=match_covariates(frame)
        self.assertEqual(len(first),1)
        self.assertEqual([(p['ia_repository_id'],p['control_repository_id']) for p in first],[(p['ia_repository_id'],p['control_repository_id']) for p in second])

    def test_matching_boundary_factor_two(self):
        pairs=match_covariates(pd.DataFrame([row(1,'com_evidencia',loc=2000),row(2,'sem_evidencia_detectada',loc=4000)]))
        self.assertEqual(len(pairs),1)

    def test_paired_effect_sign_and_all_zero(self):
        pairs=[]
        for i in range(4):
            p={'epoch':'E3'}
            for m in METRICS:p['ia_'+m]=i+2;p['control_'+m]=i
            pairs.append(p)
        result=paired_tests(pairs)
        main=[r for r in result if r['family']=='all']
        self.assertTrue(all(r['rank_biserial_ia_minus_control']==1 for r in main))
        for p in pairs:
            for m in METRICS:p['control_'+m]=p['ia_'+m]
        main=[r for r in paired_tests(pairs) if r['family']=='all']
        self.assertTrue(all(r['p_adjusted']==1 and r['rank_biserial_ia_minus_control']==0 for r in main))

    def test_epoch_family_has_28_correction_and_empty_cells_remain_empty(self):
        frame=pd.DataFrame([row(i,'com_evidencia' if i%2 else 'sem_evidencia_detectada') for i in range(1,9)])
        mw,kw,dunn=primary_tests(frame)
        within=[r for r in mw if r['family']=='IA_within_E3']
        self.assertEqual(len(within),7)
        for r in within:self.assertAlmostEqual(r['p_adjusted_across_4_epochs'],min(1,r['p_raw']*28))
        self.assertTrue(all(r['status']=='insufficient_n' for r in kw))
        self.assertEqual(dunn,[])

if __name__=='__main__':unittest.main()
