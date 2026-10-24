# Clean-room implementation specification

This is the complete brief for the second, clean-room coding session. Implement only the t-paired family and all five modes. Use this file as the only project requirements source: do not inspect the reference application, REA output, class materials, or other project files. Write an independent calculation engine and thin CLI wrapper. Do not include G*Power binaries, decompiler output, or copied G*Power code.

## CLI contract

Executable: gpower-clone.

Usage:
- gpower-clone --test t-paired --mode <mode> --<field> <value> ...
- gpower-clone --version

Supported modes: a-priori, post-hoc, compromise, criterion, sensitivity.

The version command prints one JSON line with contract_version 1.0.0, name paired-power, and engine Python plus runtime version. Each success prints exactly one JSON object on one line to stdout and exits 0. Do not round finite numeric outputs. Integer outputs must be JSON integers. Errors print one JSON object with error, code, and when applicable field; exit 2 for invalid input, unsupported test/mode, or no solution, and 1 only for unexpected internal errors. Supported codes: MISSING_PARAM, UNKNOWN_PARAM, INVALID_VALUE, OUT_OF_RANGE, INCONSISTENT, UNSUPPORTED, NO_SOLUTION.

No defaults. Reject missing, unknown, duplicate, and mode-irrelevant arguments. Preserve field spelling exactly in flags: use --n_total and --beta_alpha_ratio, including underscores. Decimal separator is always a period. No network. Calls must complete within 2 seconds. Do not implement MCP or an AI agent in this session. Keep CLI thin: parse, validate, serialize, call the shared engine.

## Supported fields

Every mode requires tails, integer 1 or 2.

| Mode | Required inputs | Required outputs |
|---|---|---|
| a-priori | tails, dz, alpha, power | ncp, critical_t, df, n_total, actual_power |
| post-hoc | tails, dz, alpha, n_total | ncp, critical_t, df, power |
| compromise | tails, dz, beta_alpha_ratio, n_total | ncp, critical_t, df, alpha, beta, power |
| criterion | tails, dz, power, n_total | ncp, critical_t, df, alpha |
| sensitivity | tails, alpha, power, n_total | ncp, critical_t, df, dz |

For paired observations, n_total is the number of pairs and df = n_total - 1. Noncentrality is ncp = dz * sqrt(n_total). Effect size is positive under this CLI contract.

## Independent statistical calculation

Implement from the mathematical definition of the noncentral t distribution with standard-library numerical methods. Do not copy implementation code from G*Power.

Let nu=df and delta=ncp. The statistic follows a noncentral t distribution with degrees of freedom nu and noncentrality delta.

- tails=1: critical_t = central_t_quantile(1-alpha, nu); power = 1 - noncentral_t_cdf(critical_t, nu, delta).
- tails=2: critical_t = central_t_quantile(1-alpha/2, nu); power = noncentral_t_cdf(-critical_t, nu, delta) + 1 - noncentral_t_cdf(critical_t, nu, delta).
- A-priori: find the smallest integer n_total >= 2 for which power is at least target; return achieved power. Use integer bracketing and binary search so N is minimal.
- Post-hoc: use supplied N; return achieved power.
- Compromise: use supplied N and beta_alpha_ratio; solve for alpha such that (1-power)/alpha equals beta_alpha_ratio; return beta=1-power.
- Criterion: use supplied N and target power; solve for the t boundary giving that power, then calculate central-t alpha for the selected tail count.
- Sensitivity: use supplied N and alpha; solve for nonnegative dz producing requested power; return ncp=dz*sqrt(N).
- Numerical values must agree with public values within absolute or relative tolerance 1e-6. Do not round to displayed digits.

## Validation: contract plus [REA] findings

Ordinary interface requirements: finite values, 0<alpha<1, 0<power<1, dz>0, integer n_total>=2, beta_alpha_ratio>0. The narrower paired-test limits below are part of the implementation requirements:

- Any supplied n_total must satisfy 3 <= n_total <= 2147483646 inclusive. This corrects the generic contract's supplied N >= 2 rule. Evidence: [REA] ev_f84a94568fc8c0d9c1644e9f7b2d57f17aab607bd63780206d8c035a49b6e11e (paired dispatcher routes N-input modes through range validation) and [REA] ev_81acf144be2f4a097dc9cd2a14ef8b2205aa27e00335a45e07743c6e0afb9304 (inclusive range check and error path).
- Alpha and power each lie in [1e-7, 0.9999999], inclusive. When both are supplied in a mode, power >= alpha. Evidence: [REA] ev_73e814d4af2262adb5df69fea45351e7651a40716ffa574ae0f8032cff764223, [REA] ev_116bd1c5bfd5545adb9ab0b7eb83ffbae118176e4082e3c09c1486a59776d831, [REA] ev_f6045dcca4d3d9b8da4785ca6f75564122ca52b1dd223723194d22621b455e60.
- In compromise, beta_alpha_ratio is [0.01, 100], inclusive. Evidence: [REA] ev_e2abc80816b89636a73b53f443ca196fbe739dd106d2482e8d55de55fae1dbc8.
- dz must be positive and at most 20. In a-priori only, additionally require dz > 1e-5; the boundary is rejected. Do not apply this extra lower cutoff to other modes. Evidence: [REA] ev_aa9fcc8decdc4a7380db39424f791579648154bdfe1b740e3bad3cd8cdb6f348.
- For a-priori's calculated N, start search at 2; the supplied-N minimum does not establish a minimum for result N.

Map discovered interval violations to OUT_OF_RANGE. Map power below alpha to INCONSISTENT on field power. Invalid integer syntax, non-finite, and nonnumeric values are INVALID_VALUE. Unknown or irrelevant fields are UNKNOWN_PARAM. Unknown test/mode is UNSUPPORTED.

## Public acceptance values

These are from the instructor-provided contract, not hidden-vector results. N exactness matters because the evaluation gate compares sample sizes exactly.

| Mode | Input | Expected values |
|---|---|---|
| a-priori | tails=1, dz=.5, alpha=.05, power=.95 | N=45, df=44, ncp=3.3541020, critical_t=1.6802300, actual_power=.9512400 |
| post-hoc | tails=1, dz=.5, alpha=.05, N=45 | df=44, ncp=3.3541020, critical_t=1.6802300, power=.9512400 |
| compromise | tails=1, dz=.5, ratio=1, N=45 | ncp=3.3541020, critical_t=1.6864315, alpha=beta=.0493959, power=.9506041 |
| criterion | tails=1, dz=.5, power=.95, N=45 | ncp=3.3541020, critical_t=1.6922637, alpha=.0488334 |
| sensitivity | tails=1, alpha=.05, power=.95, N=45 | ncp=3.3417616, critical_t=1.6802300, dz=.4981604 |

The exact machine-readable JSONL vectors will be placed at public_vectors.jsonl beside this file. Do not search for or use hidden vectors.

## Deliverables

Create a pure-Python implementation in this directory with a reusable engine module, CLI entry point, and concise README showing installation and run commands. Use only the Python standard library. Add no G*Power binary, decompiler output, or G*Power-derived source. Report created paths and any unfinished numerical or contract limitations.