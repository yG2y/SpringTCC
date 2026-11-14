#!/usr/bin/env python3
"""Historical Spring study: metadata discovery, frozen lottery, collection, reporting."""
import argparse
import json
from pathlib import Path

from evolution.selection import discover, plan, recount
from ck_pipeline.extraction import now
from spring_boot_selection.util import parse_iso

CODE = Path(__file__).resolve().parent
ORIGINAL = CODE.parent/'Artefatos/selecao_spring_boot/runs/20260920_java/population.csv'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage', choices=['recount', 'discover', 'plan', 'collect', 'report', 'validate-instrument', 'validate-pilot'])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--original', type=Path, default=ORIGINAL)
    p.add_argument('--scope', choices=['pilot', 'all'], default='pilot')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--retry-errors', action='store_true')
    args = p.parse_args()
    if args.stage in {'recount', 'discover', 'plan', 'collect'}:
        p.error('Fluxo ampliado descontinuado por decisão do autor em 15/10/2026. '
                'Use analisar_painel_original.py, limitado à seleção original. '
                'Os relatórios anteriores continuam disponíveis para consulta.')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.stage == 'recount':
        result = recount(args.original, out/'original_recount', parse_iso(now()))
        print(json.dumps({'candidates': len(result)}))
    elif args.stage == 'discover':
        discover(out, args.original)
    elif args.stage == 'plan':
        print(json.dumps(plan(out), indent=2))
    elif args.stage == 'collect':
        from evolution.collection import collect
        collect(out, args.scope, args.workers, args.retry_errors)
    elif args.stage == 'report':
        from evolution.reporting import report
        report(out)
    elif args.stage == 'validate-instrument':
        from evolution.collection import validate_instrument
        result=validate_instrument(out)
        print(json.dumps(result,indent=2))
        if not result['passed']: raise SystemExit(1)
    else:
        from evolution.collection import validate_pilot
        result=validate_pilot(out)
        print(json.dumps(result, indent=2))
        if not result['passed']: raise SystemExit(1)


if __name__ == '__main__':
    main()
