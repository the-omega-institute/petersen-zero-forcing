#!/usr/bin/env python3
"""Independent semantic audit: imports neither generate.py nor PySAT.

Rebuilds P(n,4) from direct neighbor formulas. Parses each clause family and
checks the optimized sequential-counter grid by unifying variables against
mathematical coordinates, rather than calling an encoding library.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VALUES = {9:6, 10:6, 11:7, 12:6, 13:8, 14:8, 15:9, 16:8, 17:9, 18:10, 19:10}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def neighbors(n, v):
    if v < n:
        return {(v-1) % n, (v+1) % n, n+v}
    i = v-n
    return {i, n+(i-4) % n, n+(i+4) % n}


def read_cnf(path):
    lines = path.read_text().splitlines()
    h = lines[0].split()
    require(len(h) == 4 and h[:2] == ['p', 'cnf'], f'{path}: header')
    top, count = map(int, h[2:])
    clauses = []
    for line in lines[1:]:
        row = list(map(int, line.split()))
        require(row and row[-1] == 0 and 0 not in row[:-1], f'{path}: clause')
        require(all(0 < abs(v) <= top for v in row[:-1]), f'{path}: variable range')
        require(len(set(row[:-1])) == len(row)-1, f'{path}: duplicate literal')
        clauses.append(row[:-1])
    require(len(clauses) == count, f'{path}: clause count')
    require(max(abs(v) for c in clauses for v in c) == top, f'{path}: top variable')
    return top, clauses


class Audit:
    def __init__(self, clauses, primary):
        self.clauses = clauses
        self.offset = 0
        self.top = primary

    def family(self, expected):
        actual = self.clauses[self.offset:self.offset+len(expected)]
        require(Counter(map(frozenset, actual)) == Counter(map(frozenset, expected)),
                f'clause family at {self.offset}')
        self.offset += len(expected)

    def counter(self, literals, bound):
        # S(r,t) means: at least r of the first t+1 literals hold.
        # Only the grid 1 <= r <= bound, r-1 <= t <= m-bound+r-2 is needed.
        m = len(literals)
        require(0 < bound < m-1, 'counter bound')
        ids, reverse = {}, {}
        start = self.top

        def consume(spec):
            require(self.offset < len(self.clauses), 'missing counter clause')
            actual = self.clauses[self.offset]
            require(len(actual) == len(spec), 'counter clause length')
            self.offset += 1
            for literal, symbol in zip(actual, spec):
                if isinstance(symbol, int):
                    require(literal == symbol, 'counter input literal')
                else:
                    sign, coordinate = symbol
                    require(literal*sign > start, 'counter auxiliary range/sign')
                    var = abs(literal)
                    if coordinate in ids:
                        require(ids[coordinate] == var, 'counter grid consistency')
                    else:
                        require(var not in reverse, 'counter grid alias')
                        ids[coordinate] = var
                        reverse[var] = coordinate

        def cell(r, t, sign=1):
            return sign, (r, t)

        # Traverse clauses in the archived encoder's order, but identify their
        # variables by the prefix-count meaning of each grid coordinate.
        for j in range(m-bound):
            consume([-literals[j], cell(1, j)])
            for r in range(1, bound+1):
                t = j+r-1
                if j+1 < m-bound:
                    consume([cell(r, t, -1), cell(r, t+1)])
                if r < bound:
                    consume([-literals[t+1], cell(r, t, -1), cell(r+1, t+1)])
                else:
                    consume([-literals[t+1], cell(r, t, -1)])
        size = bound*(m-bound)
        require(len(ids) == size and set(reverse) == set(range(start+1, start+size+1)),
                'counter grid completeness/contiguous fresh variables')
        self.top += size

    def finish(self, top):
        require(self.offset == len(self.clauses) and self.top == top, 'unclassified clauses/variables')


def check_boundary(n, path):
    top, clauses = read_cnf(path)
    N = 2*n
    audit = Audit(clauses, 2*N)
    x = lambda v: v+1
    z = lambda v: N+v+1
    for v in range(N):
        a = neighbors(n, v)
        require(len(a) == 3 and all(v in neighbors(n, w) for w in a), 'simple cubic graph')
        if n <= 31:
            local = {v} | a
            audit.family([[-x(w), z(v)] for w in local]+[[-z(v)]+[x(w) for w in local]])
        else:
            audit.family([[-z(v), -x(v)], [-z(v)]+[x(w) for w in a]]+
                         [[-x(w), x(v), z(v)] for w in a])
    audit.counter([-x(v) for v in range(N)], N-16)
    audit.counter([x(v) for v in range(N)], 16)
    audit.counter([z(v) for v in range(N)], 25 if n <= 31 else 9)
    audit.family([[1, n+1]])
    audit.finish(top)


def check_fort(n, path):
    data = json.loads((ROOT/'forts'/f'fort-{n}.json').read_text())
    require(data['n'] == n and data['seed_bound'] == VALUES[n]-1, 'fort metadata')
    N = 2*n
    all_vertices = set(range(N))
    forts = data['forts']
    require(len({tuple(F) for F in forts}) == len(forts), 'duplicate fort')
    for F in forts:
        require(F == sorted(set(F)) and set(F) <= all_vertices and F, 'fort vertex list')
        S = set(F)
        require(all(len(neighbors(n, v) & S) != 1 for v in all_vertices-S), f'invalid fort n={n}')
    require(sorted(data['cnf_order']) == list(range(len(forts))), 'fort order permutation')
    top, clauses = read_cnf(path)
    audit = Audit(clauses, N)
    audit.counter(list(range(1, N+1)), VALUES[n]-1)
    flags = list(range(audit.top+1, audit.top+5))
    expected = []
    for flag, (u, v), required in zip(flags, ((0,n), (0,1), (n,0), (n,n+4)), data['anchor_seed_order']):
        R = {u} | (neighbors(n, u)-{v})
        require(len(required) == 3 and set(required) == R, 'anchor seed order metadata')
        expected.extend([[-flag, w+1] for w in R])
        expected.append([-flag, -(v+1)])
    expected.append(flags)
    audit.family(expected)
    audit.top += 4
    audit.family([[v+1 for v in F] for F in forts])
    audit.finish(top)
    return len(forts)


def check_forcing():
    rows = json.loads((ROOT/'data'/'forcing-witnesses.json').read_text())
    require([r['n'] for r in rows] == list(range(9,31)), 'witness coverage')
    for row in rows:
        n = row['n']
        black = set(row['seeds'])
        require(len(black) == len(row['seeds']) == row['z'] == VALUES.get(n,10), 'seed size')
        require(black <= set(range(2*n)), 'seed range')
        for u, v in row['trace']:
            require(u in black and v not in black and neighbors(n,u)-black == {v},
                    f'illegal force n={n}: {u}->{v}')
            black.add(v)
        require(black == set(range(2*n)), f'incomplete forcing n={n}')
    # Check the exact uniform sequence and the stated n=19 counterexample.
    for n in range(11,109):
        B = set(range(10))
        trace = [(i,n+i) for i in range(1,9)]+[(n+4,n), (n+5,n+9)]
        trace += [edge for j in range(10,n) for edge in ((j-1,j), (n+j-4,n+j))]
        for u,v in trace:
            require(u in B and v not in B and neighbors(n,u)-B == {v}, 'uniform construction')
            B.add(v)
        require(len(B) == 2*n, 'uniform completion')
    X = set(range(10)) | {19+i for i in (3,4,5,6,10,18)}
    boundary = set().union(*(neighbors(19,v) for v in X))-X
    require(boundary == {10,18} | {19+i for i in (0,1,2,7,8,9,14)}, 'n=19 boundary example')
    return len(rows)


def check_deletion():
    count = 0
    # Check each occupied vertex individually: union then proves N[X] equality.
    for n in range(10,217):
        def f(v):
            i = v % n
            require(i != 4, 'deleted vertex touched')
            return (v//n)*(n-1)+i-(i > 4)
        for i in range(9,n):
            for d in (-4,-1,1,4):
                require(f((i+d) % n) == (f(i)+d) % (n-1), 'cyclic deletion identity')
                count += 1
            for v in (i,n+i):
                require({f(w) for w in neighbors(n,v)} == neighbors(n-1,f(v)), 'deletion neighbors')
    # Exhaust all layer assignments for short graphs, including wrap-around.
    sets = 0
    for n in range(10,17):
        def f(v):
            i = v % n
            require(i != 4, 'deleted boundary vertex')
            return (v//n)*(n-1)+i-(i > 4)
        available = list(range(9,n))+list(range(n+9,2*n))
        for bits in itertools.product((0,1), repeat=len(available)):
            X = {v for v,b in zip(available,bits) if b}
            NX = X | set().union(*(neighbors(n,v) for v in X))
            Y = {f(v) for v in X}
            NY = Y | set().union(*(neighbors(n-1,v) for v in Y))
            require({f(v) for v in NX} == NY, 'closed neighborhood deletion')
            sets += 1
    return count, sets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cnf-dir', type=Path, default=ROOT/'cnf')
    args = parser.parse_args()
    for n in range(20,109):
        check_boundary(n, args.cnf_dir/f'boundary-{n}.cnf')
    forts = sum(check_fort(n, args.cnf_dir/f'fort-{n}.cnf') for n in range(9,20))
    witnesses = check_forcing()
    offsets, sets = check_deletion()
    print(f'PASS semantic: 89 boundary CNFs, 11 fort CNFs, {forts} nonempty forts', flush=True)
    print(f'PASS forcing: {witnesses} complete witnesses; uniform construction n=11..108', flush=True)
    print(f'PASS deletion: {offsets} offset checks and {sets} exhaustive layer assignments', flush=True)


if __name__ == '__main__':
    main()
