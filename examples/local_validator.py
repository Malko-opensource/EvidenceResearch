"""Independently recompute from preserved data, rather than trust the mean."""
import json
from pathlib import Path
import statistics
import sys

bundle = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
result = json.loads(Path(bundle['artifacts']['result']).read_text(encoding='utf-8'))
values = result['values']
correct = values == [1.0, 2.0, 3.0, 4.0] and result['mean'] == statistics.mean(values)
print(json.dumps({'metrics': {'correct': int(correct)}, 'details': {'independently_recomputed': True}}))
