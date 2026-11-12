#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""CLI: seal a Voyage USB offline kit (frozen docs → SHA256SUMS → preflight).

See voyage_usb_kit_seal.py. Evidence JSON is written *outside* the kit so it
does not invalidate SHA256SUMS.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from voyage_usb_kit_seal import seal_kit  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kit', type=Path, required=True)
    ap.add_argument('--host-test-results', type=Path,
                    help='frozen HOST-TEST-RESULTS.txt installed before SHA256SUMS')
    ap.add_argument('--doc', action='append', default=[],
                    help='REL_IN_KIT=SOURCE_PATH; installed before SHA256SUMS')
    ap.add_argument('--skip-preflight', action='store_true')
    ap.add_argument('--reassemble-outdir', type=Path)
    ap.add_argument('--evidence-out', type=Path, required=True,
                    help='seal evidence JSON written outside the kit')
    args = ap.parse_args()

    frozen: dict[str, Path] = {}
    if args.host_test_results:
        frozen['HOST-TEST-RESULTS.txt'] = args.host_test_results
    for item in args.doc:
        if '=' not in item:
            raise SystemExit('--doc needs REL=SOURCE, got %r' % item)
        rel, src = item.split('=', 1)
        if rel == 'SHA256SUMS' or rel.endswith('/SHA256SUMS'):
            raise SystemExit('cannot install SHA256SUMS via --doc')
        frozen[rel] = Path(src)

    evidence = seal_kit(
        args.kit,
        frozen or None,
        run_preflight=not args.skip_preflight,
        reassemble_outdir=args.reassemble_outdir,
        evidence_out=args.evidence_out,
    )
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
