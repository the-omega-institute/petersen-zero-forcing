#!/usr/bin/env python3
"""Offline one-command verification; temporary outputs never alter the package."""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
NAMES = [f'boundary-{n}' for n in range(20,109)]+[f'fort-{n}' for n in range(9,20)]


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def check_manifest():
    entries = []
    for line in (ROOT/'MANIFEST.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = ROOT/name
        if not path.is_file() or sha(path) != digest:
            raise ValueError(f'manifest mismatch: {name}')
        entries.append(name)
    if len(entries) != len(set(entries)):
        raise ValueError('duplicate manifest entry')
    actual = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.name != 'MANIFEST.sha256'}
    if set(entries) != actual:
        raise ValueError(f'manifest coverage mismatch: {actual ^ set(entries)}')
    print(f'PASS SHA-256 manifest: {len(entries)} files', flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--semantic-only', action='store_true', help='skip proof verification (lite package)')
    p.add_argument('--timeout', type=int, default=600, help='seconds allowed for each DRAT check')
    p.add_argument('--log-dir', type=Path, help='save each checker output outside the package')
    args = p.parse_args()
    started = time.monotonic()
    check_manifest()
    if args.log_dir:
        args.log_dir = args.log_dir.resolve()
        if args.log_dir == ROOT or ROOT in args.log_dir.parents:
            raise ValueError('log directory must be outside the immutable package')
        args.log_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='krishnan-verify-') as tmp:
        work = Path(tmp)
        generated = work/'cnf'
        subprocess.run([sys.executable, '-B', str(ROOT/'generate.py'), '--out', str(generated)], check=True)
        for name in NAMES:
            a, b = generated/(name+'.cnf'), ROOT/'cnf'/(name+'.cnf')
            if a.read_bytes() != b.read_bytes():
                raise ValueError(f'regenerated CNF differs: {name}')
        print('PASS byte comparison: all 100 regenerated CNFs match the archive', flush=True)
        subprocess.run([sys.executable, '-B', str(ROOT/'semantic_check.py'), '--cnf-dir', str(generated)], check=True)
        if args.semantic_only:
            print('PASS semantic-only checks; DRAT certificates were not checked', flush=True)
            return
        index = json.loads((ROOT/'data'/'proof-index.json').read_text())
        records = {r['name']:r for r in index}
        if set(records) != set(NAMES) or len(index) != 100:
            raise ValueError('proof-index coverage')
        checker = work/'drat-trim'
        command = shlex.split(os.environ.get('CC', 'cc'))
        subprocess.run(command+['-O2', str(ROOT/'checker'/'drat-trim.c'), '-o', str(checker)], check=True)
        print('PASS built bundled DRAT-trim source', flush=True)
        for i, name in enumerate(NAMES, 1):
            compressed = ROOT/'proofs'/(name+'.drat.xz')
            if not compressed.is_file():
                raise ValueError(f'missing {compressed.name}; use the full package or regenerate proofs')
            raw = work/(name+'.drat')
            with lzma.open(compressed, 'rb') as a, raw.open('wb') as b:
                shutil.copyfileobj(a, b, 1024*1024)
            if raw.stat().st_size != records[name]['raw_bytes'] or sha(raw) != records[name]['raw_sha256']:
                raise ValueError(f'raw proof hash mismatch: {name}')
            before = time.monotonic()
            run = subprocess.run([str(checker), str(generated/(name+'.cnf')), str(raw), '-i', '-t', str(args.timeout)],
                                 capture_output=True, text=True, timeout=args.timeout+30)
            output = run.stdout+run.stderr
            if args.log_dir:
                (args.log_dir/(name+'.log')).write_text(output)
            # DRAT-trim historically returns a nonzero code even when verified.
            # Require the exact success line, not a recorded receipt or exit code.
            if 's VERIFIED' not in output.splitlines():
                raise ValueError(f'DRAT failure {name}, return={run.returncode}: {output[-2000:]}')
            raw.unlink()
            print(f'PASS DRAT {i:03d}/100 {name} ({time.monotonic()-before:.3f} s)', flush=True)
        print(f'PASS ALL: 89 boundary + 11 fort certificates, all semantics and forcing; '
              f'elapsed {time.monotonic()-started:.3f} s', flush=True)


if __name__ == '__main__':
    main()
