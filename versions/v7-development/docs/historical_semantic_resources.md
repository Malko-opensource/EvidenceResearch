# Historical resource and scoped semantic adapters: c6 development

This candidate changes only its semantic verifier and new contract tests. Frozen v4/v5 records, reviews, sources and live controllers remain unchanged. It does not retrospectively approve an existing pending statement. No provider call or research trial is part of this development validation.

The new `historical_pre_proposal_resources` predicate describes resources already available when the host submitted one original C proposal request. It excludes that request's completion and every subsequent request. The whole-unit `resource_accounting` predicate retains its full-inventory contract. These predicates have different scopes; their values cannot be substituted for each other.

`arguments` requires `scope: "historical_pre_proposal"`, `measure`, `value`, and exact `{path, sha256}` links named `proposal_request`, `transport_trace`, `callback_registration`, and `research_audit`. Definitive failures additionally require `failed_lineage`. The original provider input must contain the actual prerequest resource snapshot and host execution ledger. The original request ordinal determines the entire prefix; the reviewer cannot choose a shorter list. Each resource-bearing sentence and parsed clause in the exact reviewed span must visibly restrict its own resources to historical, pre-proposal, prefix, before a proposal/request, or the corresponding supported Korean scope. An unrelated historical appendix or earlier feature-design sentence cannot qualify a later resource assertion. An unqualified sentence such as “Provider input usage was 30 tokens” remains pending/unsupported even when valid historical receipts exist. Conservative clause splitting can also leave a correctly intended enumeration pending until its individual scope is clear; it does not infer omitted scope from nearby prose.

The adapter checks:

- Original C callback source hash and public task/model/resource registration.
- Contiguous durable request ordinals, unique requested/terminal mappings, complete discovery of actual raw request directories, and a completed chronological prefix before the target boundary.
- Actual raw input fingerprint, exact host JSON serialization, complete proposal-only guard, frozen provider source, exact model/effort/CLI isolation settings, raw event usage and linked file hashes.
- The target's immutable snapshot hash and equality with the exact original provider input. Its `observed_resources` is reconstructed from independently audited prefix receipts, including the full lists and order.
- The CPU ledger's append-only event hash chain, actual EXECUTE order, independently discovered execution directories, independently verified artifacts/configuration, original proposal call identity/fingerprint, and public split/model/resource conditions.
- Failed attempts' source-bound no-action and continuation receipts. Absent provider-attested failure tokens remain null. Wall time can still be supported separately. Unknown tokens are never replaced with zero.

Facts label the historical boundary and explicitly exclude final totals, next-call costs, expected gains, prices and independent review/engineering cost. Integer counts/tokens use exact equality; elapsed times allow `rel_tol=abs_tol=1e-9` for a displayed decimal. A forecast or inference cannot be reclassified as measured resource usage. All supporting evidence is rechecked when an independent semantic review is validated.

The first adapter supports finalized C host ledgers matching the executing source version. Completed raw receipts retain the existing frozen raw-audit qualification, including required positive input/output usage. Unresolved transport, legacy/mismatched sources, unsupported ledger shapes or missing failure lineage remain pending rather than guessed. An earlier proposal's CPU invocation appearing only after the target boundary cannot be silently inserted into the original context; a mismatch fails closed. This is a fixed-source forensic contract, not a universal timestamp oracle or an OS security boundary. Model IDs/settings do not expose server weight versions or sampling seeds. Hashes and owner-role fields are not authenticated human identity or signed provider attestations.

Conservative lexical guards also distinguish a narrow set of explicit denying predicates in their own clause and `will test`/similar prospective verbs. An unrelated “no” sentence or a mixed positive clause cannot erase a completed result assertion. The new structured `nonresult_context` is optional and restricted:

- `fixed_next_question`: only an exact `/next_questions/N` JSON string equal to the executing frozen host's literal, with a source hash. This classifies a planning question, not its premises as proven results.
- `registered_hypothesis`: the entire original hypothesis must equal an actual registered/verified run. Matching actual baseline evidence is required before adjectival “verified linear fit” or “measured cubic incumbent” is treated as prior context. Affirmative completed effects remain blocked.

Source attribution now works only with `kind: literature`; its exact report span must equal the cited source excerpt. A negated optimum in an attributed synopsis is not forced into a local minimum predicate. Corpus copying, citation presence and local agent reading/comprehension are distinct: the candidate has no registered comprehension adapter and does not accept a local read/understood claim through corpus attribution. A reference list does not prove that an agent consumed or understood its contents.

These guards do not claim unrestricted natural-language entailment. Independent reviewers must still inventory all units, bind complete non-overlapping spans, map every assertion and check applicability. Numeric and semantic report gates remain jointly required. Current frozen v5 pending items remain pending, including any unqualified historical resource sentence.

Run candidate contracts from `work/c6` after all candidate owners finish their source changes:

```powershell
python -X utf8 -B -m unittest tests.test_historical_semantics tests.test_report_semantics -v
```

The new fixtures contain fabricated raw provider formats tagged `fixture_only`, and small real trusted CPU unit executions. They do not call a provider, run a research comparison or supply performance evidence. They test final/forecast relabeling, unrelated historical cues, fractional token tolerance, fully rehashed source/effort/list/order/serialization tampering, omitted raw calls, raw receipt changes, CPU-chain changes, failure-usage unknowns, explicit denials, mixed assertions, source-bound planning and literature attribution attacks. A first test setup failed because its own snapshot directory had not been created; adding that directory corrected the fixture without weakening a predicate. Whole-candidate release validation must use a fresh source snapshot after the independent sampling/blinding changes are complete.
