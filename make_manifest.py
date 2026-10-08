#!/usr/bin/env python3
"""Build a complete member manifest after an intentional package update."""
import hashlib
from pathlib import Path

root = Path(__file__).resolve().parent
paths = sorted(p for p in root.rglob('*') if p.is_file()
               and '__pycache__' not in p.parts and p.name != 'MANIFEST.sha256')
rows = []
for path in paths:
    with path.open('rb') as f:
        digest = hashlib.file_digest(f,'sha256').hexdigest()
    rows.append(f'{digest}  {path.relative_to(root)}\n')
(root/'MANIFEST.sha256').write_text(''.join(rows))
print(f'Wrote SHA-256 manifest for {len(rows)} files')
