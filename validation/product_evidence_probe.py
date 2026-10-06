"""Temporarily test a single, explicitly owned development fixture artifact."""
import hashlib
import json
from pathlib import Path
import sys

project = Path(__file__).resolve().parents[1]
expected = '4de3b679081334b6a27a13a022a3f2d98f8e37ec01dc24c947274dea68be163e'
root = (project / 'research-workspaces/product-fixtures-20261004').resolve()
target = (root / '.research/evidence' / expected).resolve()
proof = project / 'validation/product-web-0.7.0'
backup = proof / 'fixture-original-result.bin'
assert target.is_relative_to(root) and target.name == expected
sha = lambda data: hashlib.sha256(data).hexdigest()
action = sys.argv[1]
if action == 'backup':
    data = target.read_bytes()
    assert sha(data) == expected, 'Fixture original must be intact before the probe'
    if backup.exists():
        assert backup.read_bytes() == data, 'Never overwrite a different backup'
    else:
        backup.write_bytes(data)
elif action in ('tamper', 'missing', 'restore'):
    data = backup.read_bytes()
    assert sha(data) == expected, 'Preserved original hash mismatch'
    if action == 'tamper':
        assert target.read_bytes() == data
        target.write_bytes(b'{"weighted_mean":999,"probe":"development-only"}')
    elif action == 'missing':
        assert target.read_bytes() == data
        target.unlink()
    else:
        target.write_bytes(data)
else:
    raise ValueError('Use backup, tamper, missing, or restore')
print(json.dumps({'action': action, 'scope': str(root), 'target': str(target),
                  'exists': target.exists(),
                  'sha256': sha(target.read_bytes()) if target.exists() else None,
                  'original_preserved': backup.exists() and sha(backup.read_bytes()) == expected}))
