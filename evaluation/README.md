# Evaluation artifacts

No final evaluation suite has been run by creating this directory. Development
results go under `development/`. A final owner creates fresh private/public data,
preregisters hashes and criteria, then explicitly calls `run_matched`.

Never upload private test outcomes, provider credentials, or raw model traces
without a deliberate sanitization and publication decision. A public result can
include hashes, aggregate metrics, reproduction scripts, and a released dataset
after the blinded comparison has ended. Releasing that dataset turns it into
development material for future framework versions.

Four explicitly approved completed development pairs can be audited from a fresh
public checkout without opening the original private owner files:

```powershell
python -X utf8 -B evaluation/replay_published_units.py --root . --recorded-root "C:\Users\Potato\Documents\ChatGPT\Research Agent\EvidenceResearch" --units linear-seed11 linear-seed19 quadratic-seed31 quadratic-seed43 --out work/public-unit-replay.json
```

The reader authenticates the original registration, the approved publication
manifest and source bytes against fixed SHA-256 anchors. It reconstructs the
deterministic development test split and original serializer in memory, checks
their original hashes, then recalculates saved predictions, scalar test MSE and
model/CPU receipts. It never writes or prints test rows and never invokes a
provider or experiment runner. It does not perform a new experiment, a complete
semantic report review or a final adoption decision.

The isolated relocation and tamper checks are in
`development/published-units-replay-v1/`. These completed public tasks are
development material; their results cannot serve as a new framework version's
unseen final evaluation.

The newly published reader was run from an exact fresh public `c95471c` checkout.
`evidence/fresh-published-reader-c95471c/result.json` links the scalar replay,
7,518 guarded file opens and zero original-owner, model or runner access. The
Python file-open guard does not establish operating-system isolation.

The separate v6 component/source fixtures are in `evidence/c6-check-v1/`, the c6
independent sampler/literature/semantic capsules and
`development/c6-sampled-design-peer-v2/`. Its own environment proofs are under
`versions/v6-development/validation/`. These records contain no newly registered
private task definitions or actual study outcomes. Preserve the first external
audit-guard failure and the corrected proof together.
