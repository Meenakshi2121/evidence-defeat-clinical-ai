# Data

No participant-level data are stored in this repository.

The planned multitrial source is a frozen, cited version of RCT Bench. The exact
release or commit, licences and checksums will be recorded before download.
Only trials meeting preregistered eligibility rules will be analysed.

Expected local layout:

```text
data/
  external/rct_bench/   # downloaded public source files; Git-ignored
  interim/              # harmonised local files; Git-ignored
  manifests/            # checksums, provenance and eligibility logs; tracked
```

Never commit participant-level trial data unless the source licence explicitly
permits redistribution and the protocol records that decision.

