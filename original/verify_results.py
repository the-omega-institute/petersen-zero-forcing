"""Semantic checks of saved witnesses and CNFs, independent of their producers.

Pass --recheck to rerun DRAT-trim on every saved proof. No SAT search, Lean,
email, or git operations are performed here.
"""
import sys,json,hashlib,argparse,subprocess,time,itertools
from collections import Counter
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'deps'))
from pysat.formula import CNF,IDPool
from pysat.card import CardEnc,EncType

ROOT=Path(__file__).parent
def adj(n):
    return [{(i-1)%n,(i+1)%n,n+i} for i in range(n)]+[
        {i,n+(i-4)%n,n+(i+4)%n} for i in range(n)]

def rows(name):
    result={}
    for line in (ROOT/name).read_text().splitlines():
        r=json.loads(line);result[r['n']]=r
    return result

def same_clauses(actual,expected):
    assert len(actual)==len(expected)
    assert [frozenset(c) for c in actual]==[frozenset(c) for c in expected]

def boundary_formula(n):
    N=2*n;x=list(range(1,N+1));z=list(range(N+1,2*N+1))
    pool=IDPool(start_from=2*N+1);a=adj(n);clauses=[]
    if n<=31:
        for v in range(N):
            for u in [v]+sorted(a[v]):clauses.append([-x[u],z[v]])
            clauses.append([-z[v]]+[x[u] for u in [v]+sorted(a[v])])
        cap=25
    else:
        for v in range(N):
            clauses.append([-z[v],-x[v]])
            clauses.append([-z[v]]+[x[u] for u in sorted(a[v])])
            for u in sorted(a[v]):clauses.append([-x[u],x[v],z[v]])
        cap=9
    clauses+=CardEnc.equals(x,16,vpool=pool,encoding=EncType.seqcounter).clauses
    clauses+=CardEnc.atmost(z,cap,vpool=pool,encoding=EncType.seqcounter).clauses
    clauses.append([x[0],x[n]])
    return clauses

def check_fort_formula(n,b,data,actual):
    N=2*n;x=list(range(1,N+1));pool=IDPool(start_from=N+1);a=adj(n)
    counter=CardEnc.atmost(x,b,vpool=pool,encoding=EncType.seqcounter).clauses
    same_clauses(actual[:len(counter)],counter)
    anchors=[];clauses=[]
    for u,v in [(0,n),(0,1),(n,0),(n,n+4)]:
        flag=pool.id(('case',u,v));anchors.append(flag)
        clauses += [[-flag,x[w]] for w in {u}|(a[u]-{v})]
        clauses.append([-flag,-x[v]])
    clauses.append(anchors)
    offset=len(counter)
    assert Counter(map(frozenset,actual[offset:offset+len(clauses)]))==Counter(map(frozenset,clauses))
    tail=actual[offset+len(clauses):]
    assert len(tail)==len(data['forts'])
    assert {frozenset(c) for c in tail}=={frozenset(v+1 for v in F) for F in data['forts']}
    for F in data['forts']:
        F=set(F)
        assert F and F<=set(range(N))
        assert all(len(a[v]&F)!=1 for v in range(N) if v not in F)

def deletion_checks():
    count=0
    # Exhaustively test every layer assignment outside a fixed nine-column gap.
    for n in range(10,17):
        old=adj(n);new=adj(n-1);available=list(range(9,n))+list(range(n+9,2*n))
        def image(v):
            i=v%n;assert i!=4
            return (v//n)*(n-1)+i-(i>4)
        for mask in range(1<<len(available)):
            X={v for j,v in enumerate(available) if mask&(1<<j)}
            B=set().union(*(old[v] for v in X))-X if X else set()
            Y={image(v) for v in X}
            D=set().union(*(new[v] for v in Y))-Y if Y else set()
            assert {image(v) for v in B}==D
            count+=1
    return count

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true')
    parser.add_argument('--recheck',action='store_true');args=parser.parse_args()
    start=time.monotonic();frows=rows('fort-proof-results.jsonl');brows=rows('boundary-proof-results.jsonl')
    expected_small={9:6,10:6,11:7,12:6,13:8,14:8,15:9,16:8,17:9}
    witnesses=json.loads((ROOT/'forcing-witnesses.json').read_text())
    assert [r['n'] for r in witnesses]==list(range(9,31))
    for row in witnesses:
        n=row['n'];a=adj(n);black=set(row['seeds'])
        assert len(black)==row['z']==expected_small.get(n,10)
        for u,v in row['trace']:
            assert u in black and v not in black and a[u]-black=={v},(n,u,v)
            black.add(v)
        assert len(black)==2*n
    manifest=[]
    for kind,records,ns in [('fort',frows,range(9,20)),('boundary',brows,range(20,109))]:
        for n in ns:
            if n not in records:
                assert args.partial,('missing proof',kind,n)
                continue
            r=records[n];assert r['drat_verified'] is True
            prefix=ROOT/'proofs'/f'{kind}-{n}'
            cnf=CNF(from_file=str(prefix)+'.cnf')
            if kind=='fort':
                data=json.loads(Path(str(prefix)+'.json').read_text())
                b=expected_small.get(n,10)-1
                assert data['n']==n and data['seed_bound']==r['seed_bound']==b
                check_fort_formula(n,b,data,cnf.clauses)
            else:
                assert r['p']==16 and r['boundary_bound']==9 and r['sat'] is False
                same_clauses(cnf.clauses,boundary_formula(n))
                for ext in ['.cnf','.drat']:
                    assert hashlib.sha256(Path(str(prefix)+ext).read_bytes()).hexdigest()==r['sha256'][ext]
            log=Path(str(prefix)+'.check.log').read_text();assert 's VERIFIED' in log
            if args.recheck:
                run=subprocess.run([str(ROOT/'checker'/'drat-trim'),str(prefix)+'.cnf',str(prefix)+'.drat','-i','-t','300'],capture_output=True,text=True)
                assert 's VERIFIED' in run.stdout,(kind,n,run.stdout[-2000:])
                Path(str(prefix)+'.recheck.log').write_text(run.stdout+run.stderr)
            files={}
            for ext in ['.cnf','.drat','.check.log']+(['.json'] if kind=='fort' else []):
                p=Path(str(prefix)+ext);files[p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            manifest.append({'kind':kind,'n':n,'files':files})
    deletions=deletion_checks()
    result={'complete':len(manifest)==100,'finite_boundary_cases':sum(r['kind']=='boundary' for r in manifest),
            'fort_cases':sum(r['kind']=='fort' for r in manifest),'forcing_witnesses':len(witnesses),
            'exhaustive_deletion_checks':deletions,'drat_receipts_verified':len(manifest),
            'drat_rechecks_run':args.recheck,
            'seconds':round(time.monotonic()-start,3),'files':manifest}
    (ROOT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}),flush=True)

if __name__=='__main__':main()
