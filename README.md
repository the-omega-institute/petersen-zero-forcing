# Zero forcing in generalized Petersen graphs P(n,4)

Working repository for the collaboration with Arnav Krishnan on the zero forcing number of P(n,4).

Result (computer-assisted): Z(P(n,4)) = 10 for every n >= 18, and 18 is sharp; exact values for 9 <= n <= 17 are
6, 6, 7, 6, 8, 8, 9, 8, 9. See `notes/k4-note-v2.pdf`.

- `notes/` - the current note (PDF and TeX).
- Verification package (this directory): generator, semantic checker, fort lists, CNFs and checks; see
  `PACKAGE-README.md` for the exact commands. The DRAT proofs are large and are attached to the GitHub release
  `v2-full` as `krishnan-k4-v2-full.zip`; `verify_all` regenerates and checks everything else.

Open direction: a structural argument for the lower bound that replaces or reduces the 89 finite boundary cases.
