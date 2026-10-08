"""Exact experiments on P(n,4); no Lean execution or repository mutation.

Vertices 0..n-1 are u_i, n..2*n-1 are v_i.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'deps'))
import argparse, json, time
from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

def graph(n, k=4):
    assert n > 2*k
    return [sorted({(i-1)%n,(i+1)%n,n+i}) for i in range(n)] + [
        sorted({i,n+(i-k)%n,n+(i+k)%n}) for i in range(n)]

def closure(adj, seeds):
    black=set(seeds); trace=[]
    while True:
        changed=False
        for u, neigh in enumerate(adj):
            if u not in black: continue
            white=[v for v in neigh if v not in black]
            if len(white)==1:
                v=white[0]; black.add(v); trace.append([u,v]); changed=True
        if not changed: return black,trace

def boundary(n,p,b,solver='cadical195',budget=None,k=4):
    adj=graph(n,k); pool=IDPool(); cnf=CNF()
    x=[pool.id(('x',v)) for v in range(2*n)]
    y=[pool.id(('y',v)) for v in range(2*n)]
    for v in range(2*n):
        cnf.append([-y[v],-x[v]])
        cnf.append([-y[v]]+[x[u] for u in adj[v]])
        for u in adj[v]: cnf.append([-x[u],x[v],y[v]])
    cnf.extend(CardEnc.equals(x,p,vpool=pool,encoding=EncType.seqcounter).clauses)
    cnf.extend(CardEnc.atmost(y,b,vpool=pool,encoding=EncType.seqcounter).clauses)
    # Any nonempty set rotates so that one of the vertices in column zero is in it.
    cnf.append([x[0],x[n]])
    t=time.monotonic()
    with Solver(name=solver,bootstrap_with=cnf) as s:
        if budget:
            s.conf_budget(budget); sat=s.solve_limited()
        else: sat=s.solve()
        result={'n':n,'k':k,'p':p,'boundary_bound':b,'sat':sat,
                'seconds':round(time.monotonic()-t,3),'stats':s.accum_stats()}
        if sat:
            model=set(s.get_model()); X=[v for v in range(2*n) if x[v] in model]
            B=sorted({u for v in X for u in adj[v]}-set(X))
            assert len(X)==p and len(B)<=b
            result.update(X=X,boundary=B)
        return result

def forcing(n,b,solver='cadical195',budget=None,k=4,anchor=None):
    adj=graph(n,k); N=2*n; pool=IDPool(); cnf=CNF()
    rank=[[pool.id(('r',v,t)) for t in range(N)] for v in range(N)]
    edges={(u,v):pool.id(('f',u,v)) for u in range(N) for v in adj[u]}
    for v in range(N):
        cnf.append([rank[v][N-1]])
        for t in range(N-1): cnf.append([-rank[v][t],rank[v][t+1]])
        cnf.append([rank[v][0]]+[edges[u,v] for u in adj[v]])
    for (u,v),f in edges.items():
        cnf.append([-f,-rank[v][0]])
        predecessors=[u]+[w for w in adj[u] if w!=v]
        for t in range(1,N):
            for w in predecessors: cnf.append([-f,-rank[v][t],rank[w][t-1]])
    seeds=[rank[v][0] for v in range(N)]
    cnf.extend(CardEnc.atmost(seeds,b,vpool=pool,encoding=EncType.seqcounter).clauses)
    cnf.append([seeds[0],seeds[n]])
    if anchor is not None:
        u=(anchor//3)*n; v=adj[u][anchor%3]
        for w in [u]+[w for w in adj[u] if w!=v]: cnf.append([seeds[w]])
        cnf.append([-seeds[v]])
    t=time.monotonic()
    with Solver(name=solver,bootstrap_with=cnf) as s:
        if budget: s.conf_budget(budget); sat=s.solve_limited()
        else: sat=s.solve()
        result={'n':n,'k':k,'seed_bound':b,'sat':sat,'anchor':anchor,
                'seconds':round(time.monotonic()-t,3),'stats':s.accum_stats()}
        if sat:
            model=set(s.get_model()); S=[v for v in range(N) if seeds[v] in model]
            B,trace=closure(adj,S); assert len(B)==N and len(S)<=b
            result.update(seeds=S,trace=trace)
        return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('kind',choices=['boundary','forcing'])
    ap.add_argument('n',type=int); ap.add_argument('bound',type=int)
    ap.add_argument('--p',type=int,default=16); ap.add_argument('--k',type=int,default=4)
    ap.add_argument('--solver',default='cadical195'); ap.add_argument('--budget',type=int)
    ap.add_argument('--anchor',type=int); ap.add_argument('--out')
    a=ap.parse_args()
    if a.kind=='boundary': r=boundary(a.n,a.p,a.bound,a.solver,a.budget,a.k)
    else: r=forcing(a.n,a.bound,a.solver,a.budget,a.k,a.anchor)
    data=json.dumps(r); print(data,flush=True)
    if a.out: Path(a.out).write_text(data+'\n')
