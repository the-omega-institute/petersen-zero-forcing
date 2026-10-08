#!/usr/bin/env python3
"""Optional fresh search with pinned PySAT/CaDiCaL; not needed for verification.

Reads the already archived CNFs. Fresh DRAT hashes can depend on build/platform;
each fresh proof is checked immediately against its corresponding CNF.
"""
import argparse
import ctypes
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    import pysat
    from pysat.solvers import Solver
    if pysat.__version__ != '1.9.dev15':
        raise ValueError('requires python-sat==1.9.dev15')
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--only', help='single CNF stem, e.g. fort-9 (default all 100)')
    args = p.parse_args()
    args.out = args.out.resolve()
    if args.out == ROOT or ROOT in args.out.parents:
        raise ValueError('write fresh proofs outside the immutable package')
    args.out.mkdir(parents=True, exist_ok=True)
    names = [f'boundary-{n}' for n in range(20,109)]+[f'fort-{n}' for n in range(9,20)]
    if args.only:
        if args.only not in names:
            raise ValueError('invalid CNF stem')
        names = [args.only]
    records = []
    with tempfile.TemporaryDirectory(prefix='krishnan-fresh-') as tmp:
        checker = Path(tmp)/'drat-trim'
        subprocess.run(['cc','-O2',str(ROOT/'checker'/'drat-trim.c'),'-o',str(checker)],check=True)
        for name in names:
            cnf = ROOT/'cnf'/(name+'.cnf')
            clauses = [list(map(int,line.split()))[:-1] for line in cnf.read_text().splitlines()[1:]]
            with Solver(name='cadical195', with_proof=True) as s:
                s.append_formula(clauses)
                if s.solve() is not False:
                    raise ValueError(f'unexpected SAT: {name}')
                if ctypes.CDLL(None).fflush(None) != 0:
                    raise ValueError('proof FILE flush failed')
                s.solver.prfile.seek(0)
                proof = s.solver.prfile.read()
            if not proof.endswith(b'a\x00'):
                raise ValueError('missing final empty clause')
            raw = Path(tmp)/(name+'.drat')
            raw.write_bytes(proof)
            run = subprocess.run([str(checker),str(cnf),str(raw),'-i','-t','600'],capture_output=True,text=True)
            (args.out/(name+'.check.log')).write_text(run.stdout+run.stderr)
            if 's VERIFIED' not in run.stdout.splitlines():
                raise ValueError(f'proof rejected: {name}')
            with lzma.open(args.out/(name+'.drat.xz'),'wb',preset=6) as f:
                f.write(proof)
            records.append({'name':name,'raw_bytes':len(proof),'raw_sha256':hashlib.sha256(proof).hexdigest()})
            raw.unlink()
            print(f'PASS fresh CaDiCaL 1.9.5 proof: {name}',flush=True)
        (args.out/'proof-index.json').write_text(json.dumps(records,indent=2)+'\n')


if __name__ == '__main__':
    main()
