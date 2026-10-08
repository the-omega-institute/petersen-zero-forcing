#!/usr/bin/env python3
"""Deterministically reproduce the archived CNFs using only the standard library.

The counter is a Python translation of PySAT 1.9.dev15's seqcounter_encode_atmostN
(MIT license in original/PYSAT-LICENSE.txt). Exactly-k is at-least then at-most.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def graph(n):
    a = [set() for _ in range(2*n)]
    for i in range(n):
        for u, v in ((i, (i+1) % n), (i, n+i), (n+i, n+(i+4) % n)):
            a[u].add(v)
            a[v].add(u)
    return a


class Formula:
    def __init__(self, top):
        self.top = top
        self.clauses = []

    def atmost(self, literals, bound):
        m = len(literals)
        if bound >= m:
            return
        if bound == m-1:
            self.clauses.append([-v for v in literals])
            return
        if bound == 0:
            self.clauses.extend([[-v] for v in literals])
            return
        assert 0 < bound < m-1
        ids = {}

        def s(k, j):
            if (k, j) not in ids:
                self.top += 1
                ids[k, j] = self.top
            return ids[k, j]

        for j in range(m-bound):
            self.clauses.append([-literals[j], s(0, j)])
            for k in range(bound-1):
                a = s(k, j)
                if j < m-bound-1:
                    self.clauses.append([-a, s(k, j+1)])
                self.clauses.append([-literals[j+k+1], -a, s(k+1, j)])
            a = s(bound-1, j)
            if j < m-bound-1:
                self.clauses.append([-a, s(bound-1, j+1)])
            self.clauses.append([-literals[j+bound], -a])

    def write(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='\n') as f:
            f.write(f'p cnf {self.top} {len(self.clauses)}\n')
            for c in self.clauses:
                f.write(' '.join(map(str, c))+' 0\n')


def boundary(n):
    N = 2*n
    a = graph(n)
    x = list(range(1, N+1))
    z = list(range(N+1, 2*N+1))
    f = Formula(2*N)
    for v in range(N):
        if n <= 31:
            local = [v]+sorted(a[v])
            f.clauses.extend([[-x[u], z[v]] for u in local])
            f.clauses.append([-z[v]]+[x[u] for u in local])
        else:
            f.clauses.append([-z[v], -x[v]])
            f.clauses.append([-z[v]]+[x[u] for u in sorted(a[v])])
            f.clauses.extend([[-x[u], x[v], z[v]] for u in sorted(a[v])])
    f.atmost([-v for v in x], N-16)
    f.atmost(x, 16)
    f.atmost(z, 25 if n <= 31 else 9)
    f.clauses.append([x[0], x[n]])
    return f


def fort(n):
    data = json.loads((ROOT/'forts'/f'fort-{n}.json').read_text())
    x = list(range(1, 2*n+1))
    f = Formula(2*n)
    f.atmost(x, data['seed_bound'])
    flags = []
    for (u, v), required in zip(((0, n), (0, 1), (n, 0), (n, n+4)), data['anchor_seed_order']):
        f.top += 1
        flag = f.top
        flags.append(flag)
        f.clauses.extend([[-flag, x[w]] for w in required])
        f.clauses.append([-flag, -x[v]])
    f.clauses.append(flags)
    f.clauses.extend([[x[v] for v in data['forts'][j]] for j in data['cnf_order']])
    return f


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    for n in range(20, 109):
        boundary(n).write(args.out/f'boundary-{n}.cnf')
    for n in range(9, 20):
        fort(n).write(args.out/f'fort-{n}.cnf')
    print('PASS generated 89 boundary CNFs and 11 fort CNFs', flush=True)


if __name__ == '__main__':
    main()
