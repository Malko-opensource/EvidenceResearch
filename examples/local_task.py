"""A tiny real, deterministic experiment; no model or agent calls."""
import json
from pathlib import Path
import statistics

data = [1.0, 2.0, 3.0, 4.0]
Path('result.json').write_text(json.dumps({'values': data, 'mean': statistics.mean(data)}), encoding='utf-8')
