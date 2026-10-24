# Evidence ledger — paired t test

This ledger separates reverse-engineering evidence from independent G*Power UI reference captures. Binary evidence supports implementation choices; screenshots are supplementary runtime observations. No decompiler output is reproduced here or intended for the deliverable.

## Analysis target

- Artifact: G*Power 3.1.9.7 Windows executable GPowerNT.exe
- SHA-256: c63e6a133eb6372932f810c08cc33dc35a06d1ddb658f897bd6c34a754efc812
- Architecture/provider: x86; REA local analysis provider Ghidra 12.1.4
- REA overview record: ev_78c66c72c2b358b59187faa905ec5f3f99f9c5795f3ed13569d193d2016a7b72
- Evidence bundle is in private work/; it contains REA records and is not a submission artifact.

## [REA] findings

1. **The selected family is the dependent-means paired t test.** String/RTTI evidence identifies CEff_T_PairedMeans and PowerTPairedMean; constructor evidence labels the test as the difference between two dependent means (matched pairs). Records: ev_2c453343947f5d646fd57cb439810b38fcf56bc0dacfd1766273af1892d2c2e5, ev_6384cd9752729aeb6d5a51d2a7b9a715c926981634b820b7ce11895b6086b104, ev_3d3f68cb52cb11c080b5f65cc98a57585039eea94baadfc8dda1af376d05c37b.
2. **Paired N-input paths impose a minimum of 3 and maximum of 2,147,483,646, inclusive.** The paired analysis dispatcher routes its N-based modes through a shared range check; the validator compares inclusively and produces the admissible-range error. Records: ev_f84a94568fc8c0d9c1644e9f7b2d57f17aab607bd63780206d8c035a49b6e11e, ev_81acf144be2f4a097dc9cd2a14ef8b2205aa27e00335a45e07743c6e0afb9304. This is narrower than the generic supplied n_total >= 2 rule. N=2 was also rejected in a live UI probe, but that screenshot is not REA evidence.
3. **Alpha and power limits are tighter than the interface contract.** Validation helpers accept the closed interval [1e-7, 0.9999999]. Records: alpha ev_73e814d4af2262adb5df69fea45351e7651a40716ffa574ae0f8032cff764223; power ev_116bd1c5bfd5545adb9ab0b7eb83ffbae118176e4082e3c09c1486a59776d831.
4. **Where a mode accepts both alpha and power, power must be at least alpha.** Equal values pass the pairwise comparison; lower power is rejected. Record: ev_f6045dcca4d3d9b8da4785ca6f75564122ca52b1dd223723194d22621b455e60.
5. **Compromise beta/alpha ratio is restricted to [0.01, 100], inclusive.** The paired dispatcher supplies those endpoints to a shared closed-interval validator. Record: ev_e2abc80816b89636a73b53f443ca196fbe739dd106d2482e8d55de55fae1dbc8.
6. **The paired dispatcher uses a shared interval validator for effect-size inputs in multiple N-based modes.** The generic validator checks against caller-supplied inclusive endpoints; the paired a-priori effect path supplies -20 and +20. The CLI contract requires positive dz, so the implementation uses 0<dz<=20 in its paired modes. Records: dispatcher ev_f84a94568fc8c0d9c1644e9f7b2d57f17aab607bd63780206d8c035a49b6e11e and ev_2185086205c8435bed61444346940bd141b6403b49497a4be57895cd8fe9db5a; generic validator ev_303d912404d02930bff6888d2b1940926a29a6f8e4ea03ad8afe39a90bf7e841; paired a-priori endpoints and strict lower cutoff ev_aa9fcc8decdc4a7380db39424f791579648154bdfe1b740e3bad3cd8cdb6f348. The extra dz>1e-5 lower cutoff applies only to a-priori.
7. **The paired class is wired to analysis and effect-size conversion routines.** Vtable/xref records link the paired class to analysis and conversion code; records: ev_15058130f7b2ae8d8e7121cffb91a9b8931aa30660ae5481c684ac1352d600b5, ev_0345df3c382c3c91f80a070cff8f6b0a5509a870b990dcc2feddb3a1cc646216, ev_49fd299b3bae7fa650c37577d6a59282232ddc557d461c292db01d7b1a4586f0, ev_060dc999baf621109893124257ad70d45de20ed7366025dbe79f441c40262df8, ev_eba8657269d8a66ff7da02a392646a00a6f0588c2ecf088dc8e01f115aa34975. These records support family identification and scope; calculations are independently specified from standard probability definitions.

## [UI OBSERVATION] captures — not REA-scored evidence

These screenshots show visible output for the five public paired vectors and two boundary probes. They aid reproduction but do not replace [REA] records for scoring undocumented behavior.

| Capture | Observation |
|---|---|
| screenshots/paired-a-priori-reference.png | tails=1, dz=.5, alpha=.05, power=.95 gives N=45, df=44, ncp=3.3541020, critical t=1.6802300, achieved power=.9512400 |
| screenshots/paired-posthoc-reference.png | same effect, alpha, N gives power=.9512400 |
| screenshots/paired-posthoc-two-tailed-reference.png | tails=2, dz=.5, alpha=.05, N=45 gives power=.9065953, matching the independent CLI result within display precision |
| screenshots/paired-compromise-reference.png | beta/alpha=1, N=45 gives alpha=beta=.0493959, power=.9506041 |
| screenshots/paired-criterion-reference.png | target power=.95, N=45 gives alpha=.0488334 |
| screenshots/paired-sensitivity-reference.png | alpha=.05, power=.95, N=45 gives dz=.4981604 |
| screenshots/paired-n2-rejected.png | N=2 produces admissible-range dialog (3, 2147483646) |
| screenshots/paired-posthoc-fractional-n.png | UI-only fractional-N probe. Outside integer CLI contract; no rounding rule inferred. |

## Limits

- Findings cover one family and one program version; do not generalize them to other tests or versions.
- Static findings are paraphrased observations with evidence IDs, not a claim that all internal behavior has been reconstructed.
- UI captures are separately labeled. Only the REA-tagged records above are REA evidence.