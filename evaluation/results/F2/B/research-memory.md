# F2 B plain-file research memory

## State before execution

- The episode contained only BRIEF.ko.md, solution.py, input.csv, task.py, and episode.json. No existing research memory or completed receipt was present.
- Condition B uses the inherited external Codex agent without a research CLI. The exact model identifier and provider token usage have not been observed.
- The provided input is development-visible data. The owner fixed independent checker is an opaque evaluation source; its source and cases will not be inspected.
- The initial source performs input-order windows, includes the left boundary, emits duplicate timestamps, and accepts non-finite values.
- Proposed hypothesis: parse and reject invalid/non-finite rows, sort valid timestamps, aggregate every duplicate timestamp before emitting one output, and remove measurements at or before t - 3. Exact rational running sums avoid mean cancellation and overflow for finite values.
- Comparator: the initial provided source, retained by hash and byte-for-byte copy. No measured baseline result is claimed.
- Seed: 0. The candidate and task are deterministic and use no randomness.
- The decision will use only the independent checker's fixed pass_rate >= 1.0. A task-run artifact is execution evidence, not sufficient evidence of success.

## Limitations recorded before execution

- This is one synthetic F2 episode; it cannot establish general agent improvement.
- The implementation uses the float expression t - 3 for window cutoff, matching the literal task rule. No claim about the owner's undisclosed coverage is made before checking.
- Input, task, initial source, planned source, and final execution evidence will be hashed.

## Measured result

- Fixed independent checker: pass_rate = 1.0; decision = success. Original result: check-1.json.
- Actual task executions recorded by invocations.jsonl: 1. Repeated identical logical request reused receipt.json; invocation count remained 1 -> 1.
- Recovery: {'status': 'observed_and_recovered', 'stage': 'episode summary bookkeeping', 'failure_command': ['C:\\Users\\Potato\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe', 'episode-controller.py', 'finalize'], 'original_result': {'exit_code': 1, 'stdout': '', 'stderr': 'Traceback (most recent call last):\r\n  File "C:\\Users\\Potato\\Documents\\ChatGPT\\Research Agent\\EvidenceResearch\\evaluation\\results\\F2\\B\\episode-controller.py", line 241, in <module>\r\n    actions[sys.argv[1]]()\r\n  File "C:\\Users\\Potato\\Documents\\ChatGPT\\Research Agent\\EvidenceResearch\\evaluation\\results\\F2\\B\\episode-controller.py", line 202, in finalize\r\n    check_files = sorted(ROOT.glob("check-*.json"), key=lambda path: int(path.stem.split("-")[-1]))\r\n                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\r\n  File "C:\\Users\\Potato\\Documents\\ChatGPT\\Research Agent\\EvidenceResearch\\evaluation\\results\\F2\\B\\episode-controller.py", line 202, in <lambda>\r\n    check_files = sorted(ROOT.glob("check-*.json"), key=lambda path: int(path.stem.split("-")[-1]))\r\n                                                                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\r\nValueError: invalid literal for int() with base 10: \'1.bundle\'\r\n'}, 'preserved_original_source': 'episode-controller.failed-finalize.py', 'cause': 'An opaque checker bundle filename matched check-*.json but did not have a numeric result suffix. Bundle contents were not opened or inspected.', 'repair': 'Select only numbered check-N.json result files for finalization. Exclude opaque bundle contents from local manifest hashing to avoid reading them.', 'registered_solution_changed': False, 'registered_input_or_task_changed': False, 'registration_changed': False, 'new_registration_required': False, 'task_reexecuted_for_recovery': False, 'checker_reexecuted_for_recovery': False, 'evidence_paths': ['recovery-1.json', 'episode-controller.failed-finalize.py', 'check-1.json', 'receipt.json', 'receipt-reuse.json']}. Failed or unresolved records, if any, are preserved.
- Exact provider model identifier and external token usage remain unknown. No baseline gain or general improvement is claimed.
