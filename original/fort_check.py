"""An independent fort-hitting-set lower bound, with an UNSAT proof.

Every zero-forcing set meets every nonempty fort: the first force into a
disjoint fort would have exactly one neighbor in it, contrary to its definition.
"""
import sys,json,time,subprocess,hashlib,ctypes,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'deps'))
from pysat.card import CardEnc,EncType
from pysat.formula import CNF,IDPool
from pysat.solvers import Solver
CHECKER=str(Path(__file__).parent/'checker'/'drat-trim')

def adjacency(n):
    edges=set()
    for i in range(n):
        for a,b in [(i,(i+1)%n),(i,n+i),(n+i,n+(i+4)%n)]:
            edges.add(tuple(sorted((a,b))))
    return [{b if a==v else a for a,b in edges if v==a or v==b} for v in range(2*n)]

def residual(adj,seeds):
    # Parallel rounds, independently implemented from the C++ pending queue.
    black=set(seeds)
    while True:
        new=set()
        for u in black:
            white=adj[u]-black
            if len(white)==1:new.update(white)
        if not new:return set(range(len(adj)))-black
        black.update(new)

def is_fort(adj,F):
    return bool(F) and all(len(adj[v]&F)!=1 for v in range(len(adj)) if v not in F)

def shrink_fort(adj,F):
    # Removing vertices while the fort condition remains true strengthens cuts.
    # Iterate until no single vertex can be removed.
    changed=True
    while changed:
        changed=False
        for v in sorted(F):
            smaller=F-{v}
            if is_fort(adj,smaller):F=smaller;changed=True
    return F

def certify(n,b):
    adj=adjacency(n);pool=IDPool();cnf=CNF()
    x=[pool.id(('seed',v)) for v in range(2*n)]
    cnf.extend(CardEnc.atmost(x,b,vpool=pool,encoding=EncType.seqcounter).clauses)
    anchors=[]
    for u,v in [(0,n),(0,1),(n,0),(n,n+4)]:
        a=pool.id(('anchor',u,v));anchors.append(a)
        for w in {u}|(adj[u]-{v}):cnf.append([-a,x[w]])
        cnf.append([-a,-x[v]])
    cnf.append(anchors)
    forts=set();iterations=0;start=time.monotonic()
    with Solver(name='cadical195',bootstrap_with=cnf) as s:
        while s.solve():
            model=set(s.get_model());S={v for v in range(2*n) if x[v] in model}
            F=shrink_fort(adj,residual(adj,S))
            assert is_fort(adj,F),(n,S,F)
            for reflection in [1,-1]:
                for rotation in range(n):
                    transformed=frozenset((v//n)*n+(reflection*(v%n)+rotation)%n for v in F)
                    if transformed in forts:continue
                    assert is_fort(adj,transformed)
                    forts.add(transformed)
                    clause=[x[v] for v in sorted(transformed)]
                    cnf.append(clause);s.add_clause(clause)
            iterations+=1
            if iterations%100==0:print('fort',n,iterations,len(forts),flush=True)
    out=Path('proofs');out.mkdir(exist_ok=True);prefix=out/f'fort-{n}'
    Path(str(prefix)+'.json').write_text(json.dumps({'n':n,'seed_bound':b,'forts':[sorted(F) for F in sorted(forts,key=lambda F:tuple(sorted(F)))]})+'\n')
    cnf.to_file(str(prefix)+'.cnf')
    with Solver(name='cadical195',with_proof=True) as s:
        s.append_formula(cnf);assert s.solve() is False
        assert ctypes.CDLL(None).fflush(None)==0
        s.solver.prfile.seek(0);proof=s.solver.prfile.read()
        assert proof.endswith(b'a\x00')
        Path(str(prefix)+'.drat').write_bytes(proof)
    run=subprocess.run([CHECKER,str(prefix)+'.cnf',str(prefix)+'.drat','-i','-t','300'],capture_output=True,text=True)
    Path(str(prefix)+'.check.log').write_text(run.stdout+run.stderr)
    verified='s VERIFIED' in run.stdout;assert verified,run.stdout[-2000:]
    return {'n':n,'seed_bound':b,'forts':len(forts),'iterations':iterations,'seconds':round(time.monotonic()-start,3),'drat_verified':True}

if __name__=='__main__':
    Path('fort-worker.pid').write_text(str(os.getpid())+'\n')
    rows=[json.loads(line) for line in Path('exhaustive-values.jsonl').read_text().splitlines()]
    lo=int(sys.argv[1]) if len(sys.argv)>1 else 9
    hi=int(sys.argv[2]) if len(sys.argv)>2 else 19
    with Path('fort-proof-results.jsonl').open('a') as f:
        for row in rows:
            n=row['n']
            if lo<=n<=hi:
                r=certify(n,row['z']-1);f.write(json.dumps(r)+'\n');f.flush();print('DONE',json.dumps(r),flush=True)
