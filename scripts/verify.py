#!/usr/bin/env python3
"""Check the record hash chain: every record must point at the exact bytes of the one before it."""
import hashlib, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
bad = 0
for mdir in (sorted((ROOT / "records").iterdir()) if (ROOT / "records").is_dir() else []):
    if not mdir.is_dir():
        continue
    prev = None
    for p in sorted(mdir.glob("*/*.json")):
        rec = json.loads(p.read_text())
        link = rec["previous_record"]
        if prev is None:
            ok = link is None
        else:
            ok = bool(link) and link["path"] == prev.relative_to(ROOT).as_posix() \
                and link["sha256"] == hashlib.sha256(prev.read_bytes()).hexdigest()
        if not ok:
            bad += 1
            print(f"BROKEN: {p.relative_to(ROOT)}")
        prev = p
    print(f"{mdir.name}: checked up to {prev.relative_to(ROOT) if prev else 'nothing'}")
sys.exit(1 if bad else 0)
