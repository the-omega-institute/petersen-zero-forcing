"""Independent closed-neighborhood encoding; emit and DRAT-check finite proofs."""
import sys, json, time, subprocess, hashlib, ctypes
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'deps'))
from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

CHECKER=str(Path(__file__).parent/'checker'/'drat-trim')

def formula(n,p=16,b=9):
    # Build adjacency independently by adding three families of undirected edges.
    adj=[set() for _ in range(2*n)]
    for i in range(n):
        for u,v in [(i,(i+1)%n),(i,n+i),(n+i,n+(i+4)%n)]:
            adj[u].add(v); adj[v].add(u)
    pool=IDPool(); f=CNF()
    x=[pool.id(('selected',v)) for v in range(2*n)]
    mode='closed' if n<=31 else 'external'
    z=[pool.id((mode,v)) for v in range(2*n)]
    for v in range(2*n):
        if mode=='closed':
            local=[v]+sorted(adj[v])
            for u in local: f.append([-x[u],z[v]])
            f.append([-z[v]]+[x[u] for u in local])
        else:
            f.append([-z[v],-x[v]])
            f.append([-z[v]]+[x[u] for u in sorted(adj[v])])
            for u in sorted(adj[v]): f.append([-x[u],x[v],z[v]])
    f.extend(CardEnc.equals(x,p,vpool=pool,encoding=EncType.seqcounter).clauses)
    f.extend(CardEnc.atmost(z,p+b if mode=='closed' else b,vpool=pool,encoding=EncType.seqcounter).clauses)
    f.append([x[0],x[n]]) # rotation of a nonempty selected set
    return f

def certify(n):
    directory=Path('proofs');directory.mkdir(exist_ok=True)
    prefix=directory/f'boundary-{n}'
    cnf=formula(n);cnf.to_file(str(prefix)+'.cnf')
    start=time.monotonic()
    # Attach the proof logger before inserting clauses, so insertion-time
    # simplifications are included in the proof as well as search lemmas.
    with Solver(name='cadical195',with_proof=True) as s:
        s.append_formula(cnf)
        sat=s.solve();assert sat is False
        # The PySAT wrapper does not flush CaDiCaL's C FILE buffer before
        # get_proof(). Flush it explicitly and preserve the complete binary DRAT.
        assert ctypes.CDLL(None).fflush(None)==0
        s.solver.prfile.seek(0)
        proof=s.solver.prfile.read()
        assert proof.endswith(b'a\x00'), 'Missing final empty clause'
        Path(str(prefix)+'.drat').write_bytes(proof)
        stats=s.accum_stats()
    solved=time.monotonic()
    run=subprocess.run([CHECKER,str(prefix)+'.cnf',str(prefix)+'.drat','-i','-t','300'],capture_output=True,text=True)
    Path(str(prefix)+'.check.log').write_text(run.stdout+run.stderr)
    verified='s VERIFIED' in run.stdout
    assert verified,(n,run.returncode,run.stdout[-1000:])
    files={ext:hashlib.sha256(Path(str(prefix)+ext).read_bytes()).hexdigest() for ext in ['.cnf','.drat']}
    return {'n':n,'p':16,'boundary_bound':9,'encoding':'closed' if n<=31 else 'external',
            'sat':False,'drat_verified':verified,
            'solve_seconds':round(solved-start,3),'check_seconds':round(time.monotonic()-solved,3),
            'proof_bytes':Path(str(prefix)+'.drat').stat().st_size,'sha256':files,'stats':stats}

if __name__=='__main__':
    lo=int(sys.argv[1]) if len(sys.argv)>1 else 20
    hi=int(sys.argv[2]) if len(sys.argv)>2 else 108
    with Path('boundary-proof-results.jsonl').open('a') as out:
        for n in range(lo,hi+1):
            r=certify(n);out.write(json.dumps(r)+'\n');out.flush()
            print(n,r['solve_seconds'],r['check_seconds'],r['proof_bytes'],flush=True)
