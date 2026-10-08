# Zero forcing in P(n,4): complete finite proof package, v2

Wenlin Zhang and Haobo Ma, 8 October 2026.

This package accompanies `note.pdf` / `note.tex`. It supplies all finite
evidence used to prove Z(P(n,4)) = 10 for n >= 18 and the values
6, 6, 7, 6, 8, 8, 9, 8, 9 for n = 9,...,17. The mathematical reduction
from arbitrary circumference to 20 <= n <= 108 is proved in the note.

## One-command verification (offline)

Requirements: Python 3.11 or later, including its standard-library `lzma`
module, and a C compiler available as `cc`. Neither PySAT nor a SAT solver
is required. Run from this directory:

```sh
./verify_all --log-dir ../verification-logs
```

The command can also be launched by absolute path from any directory.
It uses a temporary directory for generated CNFs, the compiled checker and
one decompressed proof at a time. It never changes the archived package.
Set `CC` to select a C compiler. `--timeout 600` is the default time limit
in seconds for each proof; increase it if a slower computer needs more time.
The logs must be outside this directory so the immutable manifest remains
complete. The command exits on any missing file or failed check.

Expected output includes:

```text
PASS SHA-256 manifest: ... files
PASS generated 89 boundary CNFs and 11 fort CNFs
PASS byte comparison: all 100 regenerated CNFs match the archive
PASS semantic: 89 boundary CNFs, 11 fort CNFs, 33396 nonempty forts
PASS forcing: 22 complete witnesses; uniform construction n=11..108
PASS deletion: 86112 offset checks and 21844 exhaustive layer assignments
PASS built bundled DRAT-trim source
PASS DRAT 001/100 boundary-20 (... s)
...
PASS DRAT 100/100 fort-19 (... s)
PASS ALL: 89 boundary + 11 fort certificates, all semantics and forcing; elapsed ... s
```

Each saved DRAT-trim log must contain the exact line `s VERIFIED`. The
driver requires this line from a newly run checker; it does not accept
historical receipts as verification. DRAT-trim's return code alone is not
used as its success criterion. `evidence/verify-all.log` records the complete
run performed when this package was assembled; per-case logs are included
there as well when present.

## Files and graph conventions

* `MANIFEST.sha256`: SHA-256 of every regular package file except the
  manifest itself. `verify_all` checks both the hashes and complete membership.
* `generate.py`: deterministic standard-library generator for all 100 CNFs.
* `semantic_check.py`: independent semantic checker, importing neither the
  generator nor PySAT. It reconstructs graph adjacency, validates all clause
  families and every nonempty fort, and checks all forcing traces.
* `cnf/boundary-N.cnf`, N = 20,...,108: 89 boundary formulas.
* `cnf/fort-N.cnf`, N = 9,...,19: 11 fort-hitting formulas.
* `forts/fort-N.json`: nonempty fort vertex lists, their order in the CNF,
  and the order of the mandatory seed literals in each first-force case.
  The checker validates that both order fields describe exactly the required
  objects; these fields are not trusted mathematical premises.
* `proofs/*.drat.xz`: all 100 original binary DRAT proofs, losslessly XZ
  compressed. `data/proof-index.json` records their uncompressed sizes/hashes.
* `data/forcing-witnesses.json`: seeds and complete ordered force pairs for
  n = 9,...,30; the nine cases n <= 17 are printed in the note.
* `data/exact-values.csv`: claimed values and checked upper-bound seeds.
  Lower bounds come from the finite certificates and the note's reduction.
* `checker/drat-trim.c`, `LICENSE`, `SOURCE.md`: pinned checker source.
* `VERSIONS.json`: exact tool versions, complete checker revision and hashes.
* `original/`: unchanged producing-run Python sources and the original
  PySAT sequential-counter source, with its MIT license. They preserve the
  generation provenance; verification runs the new top-level scripts.
* `vendor/python_sat-1.9.dev15.tar.gz`: exact PyPI source distribution,
  including the CaDiCaL 1.9.5 source archive used by its `cadical195` backend.
  The directory also includes pinned wheels for six 1.17.0, setuptools
  80.9.0 and wheel 0.45.1, with their licenses and hashes.
* `regenerate_proofs.py`: optional fresh UNSAT search against the archived CNFs.

The integer code of u_i is i; that of v_i is n+i, for 0 <= i < n. The
graph has undirected edges u_i-u_(i+1), u_i-v_i, v_i-v_(i+4), with indices
modulo n. DIMACS seed/selection variable for vertex w is w+1. Boundary
variables are 2n+w+1. All other variables are counter cells or case flags.

For boundary formulas, exactly 16 vertices are selected. For n <= 31,
`z_w` represents membership in the closed neighborhood and its sum is at
most 25. For n >= 32, it represents the external boundary and its sum is
at most 9. The clause `x_u0 OR x_v0` normalizes rotation of a nonempty set.

For fort formulas, the seed-size bound is one below the theorem's value.
Four selector flags represent u_0->v_0, u_0->u_1, v_0->u_0, v_0->v_4.
Each flag implies that the source and its other two neighbors are seeds,
and that the target is not a seed. At least one flag must hold. A clause
for every stored fort requires at least one of its vertices to be a seed.

## Independent semantics of the counter checks

The counter uses the optimized sequential-counter grid in PySAT 1.9.dev15.
For input literals l_0,...,l_(m-1) and bound b, the auxiliary S(r,t) has
the prefix-count interpretation "at least r of l_0,...,l_t hold", on the
grid 1 <= r <= b, r-1 <= t <= m-b+r-2. Clauses propagate a true literal
into S(1,t), propagate S(r,t) into S(r,t+1), and propagate
l_(t+1) AND S(r,t) into S(r+1,t+1). At r=b the latter is forbidden.

If at most b input literals hold, assigning every cell its prefix-count
interpretation satisfies all clauses. If b+1 inputs hold, let their
positions be p_1 < ... < p_(b+1). The inequality p_r <= m-b+r-2 places
S(r,p_r) in the grid for r <= b. The first input starts propagation;
the horizontal and diagonal clauses successively force these cells true,
then the last selected input contradicts the overflow clause. Thus a
satisfying extension exists exactly when the input sum is at most b.
Exactly 16 is encoded as at-most 16 on positives and at-most 2n-16 on
negatives, with separate fresh auxiliary variables.

The checker reads clauses and unifies auxiliary variables with those grid
coordinates, checks all propagation/overflow clauses, and requires complete
fresh contiguous variable coverage. It does not call the generator's
counter routine or an encoding library. Neighborhood clauses are checked
against direct mathematical neighbor lists. Each fort is checked vertex
by vertex. A trace step is accepted only if its source is black, its target
is white, and the source's white-neighbor set is exactly that target.

## Individual commands

```sh
python3 -B generate.py --out ../regenerated-cnf
python3 -B semantic_check.py --cnf-dir ../regenerated-cnf
cc -O2 checker/drat-trim.c -o ../drat-trim
python3 -c 'import lzma,pathlib; pathlib.Path("../fort-9.drat").write_bytes(lzma.open("proofs/fort-9.drat.xz","rb").read())'
../drat-trim ../regenerated-cnf/fort-9.cnf ../fort-9.drat -i -t 600
```

## Pinned versions and fresh proof generation

Original SAT search: CaDiCaL 1.9.5 (`cadical195`) through
`python-sat==1.9.dev15`, Python 3.14.4. Source distribution SHA-256:
`5a2a58022248ce2cf9395b560685185e4773c452a29eb0ae8662d67611336cd3`.
DRAT-trim source revision:
`2e3b2dc0ecf938addbd779d42877b6ed69d9a985`.
DRAT-trim source SHA-256:
`d834b649f437e091597f5347f259b9f681087f89ca0844d0cee250a1a1a0c2ee`.
These identities also appear in `VERSIONS.json` and the manifest.

To generate new proofs, create an environment outside the package and
install the pinned PySAT source distribution and bundled build tools offline.
A C++ compiler and standard Unix build tools (`make`, `patch`, `tar`) are
needed to build PySAT. The verification command above needs only a C compiler.

```sh
python3 -m venv ../proof-env
../proof-env/bin/python -m pip install --no-index --find-links vendor 'six==1.17.0' 'setuptools==80.9.0' 'wheel==0.45.1'
../proof-env/bin/python -m pip install --no-index --no-build-isolation --no-deps vendor/python_sat-1.9.dev15.tar.gz
../proof-env/bin/python regenerate_proofs.py --out ../fresh-proofs --only fort-9
../proof-env/bin/python regenerate_proofs.py --out ../fresh-proofs
```

Each fresh search must be UNSAT and its exported proof must immediately
pass the bundled DRAT-trim. The script attaches proof logging before clause
insertion and explicitly flushes the C FILE buffer before exporting the
binary proof, including the final empty clause. A fresh proof may have a
different hash because of build/platform differences; its CNF remains fixed.

`package-lite/` has all files above except the compressed proofs. Run
`./verify_all --semantic-only` there for semantics and witnesses. To restore
a full, independently verifiable package from lite:

```sh
../proof-env/bin/python regenerate_proofs.py --out ../fresh-proofs
mkdir -p proofs
cp ../fresh-proofs/*.drat.xz proofs/
cp ../fresh-proofs/proof-index.json data/proof-index.json
python3 -B make_manifest.py
./verify_all --log-dir ../fresh-verification-logs
```

The original C++ exhaustive-search corroboration is omitted from the revised
note and is not required by this package's proof chain. No claim of a fresh
exhaustive search is made here.
