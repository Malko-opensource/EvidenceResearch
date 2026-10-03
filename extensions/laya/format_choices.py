"""Export a prospective Laya choice projection; no model execution or adoption."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from semantic_first_choice import ProjectionError, project_choice


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate_JSON_key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('nonfinite_JSON_value')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True,
        help='JSON with prepared, annotations, registry, and independent expected hashes')
    parser.add_argument('--output', type=Path, required=True, help='New projection file; existing files are refused')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('fresh_output_required')
    payload = strict_json(args.input.read_text(encoding='utf-8-sig'))
    required = {'prepared', 'annotations', 'registry', 'expected_prepared_sha256', 'expected_evidence_registry_sha256'}
    if type(payload) is not dict or set(payload) != required:
        raise ValueError('exact_projection_input_shape_required')
    projection = project_choice(payload['prepared'], payload['annotations'], payload['registry'],
        expected_prepared_sha256=payload['expected_prepared_sha256'],
        expected_evidence_registry_sha256=payload['expected_evidence_registry_sha256'])
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(projection, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': 'prospective_input_projection_exported',
        'projection_fingerprint_sha256': projection['projection_fingerprint_sha256'],
        'output': str(args.output.resolve()), 'scientific_adoption_allowed': False,
        'model_calls': 0, 'SDK_48_token_fit_guaranteed': False}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ProjectionError, ValueError, OSError) as error:
        print(json.dumps({'status': 'input_projection_failed', 'reason': str(error), 'scientific_adoption_allowed': False}))
        raise SystemExit(2)
