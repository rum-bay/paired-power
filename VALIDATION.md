# Validation record

## Clean-room implementation

The investigation session documented [REA] binary findings in REA_EVIDENCE.md. A separate clean-room writer session was instructed to use only SPEC.md; it produced the shared paired-t engine and CLI. The coordinating session reviewed the implementation and corrected the CLI spelling for the contract's underscore fields (n_total and beta_alpha_ratio). The MCP server and agent were added as thin wrappers after the engine work; both call the same calculation engine.

## Reproducible public-vector check

Run from this directory:

~~~powershell
python verify_public_vectors.py
~~~

The script runs each instructor-provided t-paired JSONL vector through the actual CLI, checks required output fields, applies the contract's absolute/relative numeric tolerance, and checks integer fields exactly. Result before integration work: all five public vectors passed; the single public a-priori N was exact (45).

## MCP and agent integration checks

Run:

~~~powershell
python verify_integrations.py
~~~

This check starts the stdio MCP server and verifies initialization, deterministic tool discovery, calls for all five public vectors, and representative invalid-input responses. It also runs the natural-language agent's tool-call loop against the real MCP server while substituting a deterministic mock for the external model response. That verifies the model-to-MCP-to-model wiring without an API key or network request. A live OpenAI API call was not made.

## Reference program observations

The saved G*Power UI captures show the five one-tailed public cases for a-priori, post-hoc, compromise, criterion, and sensitivity. A sixth calculation capture checks a two-tailed post-hoc case: G*Power displays power=.9065953 and the CLI returns .9065953041. The N=2 screenshot records the visible admissible-range rejection. These are marked UI observations in REA_EVIDENCE.md; they are supplementary and are not represented as [REA]-scored evidence.

## REA-directed CLI boundary checks

Representative probes returned the listed contract codes:

| Probe | Result |
|---|---|
| supplied N=2 | OUT_OF_RANGE, field n_total |
| a-priori dz=1e-5 | OUT_OF_RANGE, field dz |
| alpha=1e-8 | OUT_OF_RANGE, field alpha |
| a-priori power=.04 with alpha=.05 | INCONSISTENT, field power |
| unrecognized --bogus field | UNKNOWN_PARAM |
| decimal comma 0,5 | INVALID_VALUE, field dz |

The limits align with the paired-path [REA] records in REA_EVIDENCE.md. The N=2 UI screenshot is separate runtime corroboration.

## Remaining uncertainty

The engine computes the noncentral-t CDF by adaptive integration over the chi-square mixture and uses a large-df asymptotic expansion for central-t values above df 1,000,000. The instructor's public cases exercise df=44; no large-df oracle vectors are included here. The hidden-vector N >= 90% exact-match gate remains unmeasured until the instructor's evaluator runs the repository. Do not claim the hidden gate has passed.