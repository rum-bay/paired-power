# Validation record

## Independent implementation

The investigation session documented REA-tagged binary findings in REA_EVIDENCE.md. A separate clean-room writer session was instructed to use only SPEC.md; it produced the shared paired-t engine and CLI. The coordinating session reviewed the implementation and corrected the CLI spelling for the contract's underscore fields (n_total and beta_alpha_ratio).

## Reproducible public-vector check

Run from this directory:

```powershell
python verify_public_vectors.py
```

The script runs each instructor-provided t-paired JSONL vector through the actual CLI, checks the required output fields, applies the contract's absolute/relative numeric tolerance, and checks integer fields exactly. Current result: all five public vectors pass; the single public a-priori N is exact (45).

## Reference program observations

The five saved G*Power UI captures show the same one-tailed public cases for a-priori, post-hoc, compromise, criterion, and sensitivity. A sixth calculation capture checks a two-tailed post-hoc case: G*Power displays power=.9065953 and the CLI returns .9065953041. The N=2 screenshot records the visible admissible-range rejection. These are marked UI observations in REA_EVIDENCE.md; they are supplementary and are not represented as REA-scored evidence.


## REA-directed CLI boundary checks

The following representative probes were run against the CLI and returned the listed contract codes:

| Probe | Result |
|---|---|
| supplied N=2 | OUT_OF_RANGE, field n_total |
| a-priori dz=1e-5 | OUT_OF_RANGE, field dz |
| alpha=1e-8 | OUT_OF_RANGE, field alpha |
| a-priori power=.04 with alpha=.05 | INCONSISTENT, field power |
| unrecognized --bogus field | UNKNOWN_PARAM |
| decimal comma 0,5 | INVALID_VALUE, field dz |

The limits align with the paired-path REA records in REA_EVIDENCE.md. The N=2 UI screenshot is separate runtime corroboration.

## Numerical method and remaining uncertainty

The engine computes the noncentral-t CDF by adaptive integration over the chi-square mixture and uses a large-df asymptotic expansion for central-t values above df 1,000,000. The instructor's public cases exercise df=44; no large-df oracle vectors are included here. The hidden-vector N >= 90% gate remains unmeasured until the instructor's evaluator runs the repository.
