# 2026-11-19: Peer review round 5, session log

A record of the session with Claude Code that addressed the two reviews on
the `ee292m_round5` form, the systems review ("where does the time go, and
where does everything run?"). Both scored 5 of 5:

- Chris (cd24), commit `4c4b30b`: `feedback/20261119_cd24_l6134546.md`
- Helena Guan (wgguan), commit `b9118ef`: `feedback/20261119_wgguan_l6134546_7a.md`

Branch: `fix/round1-feedback`, the same branch as rounds 1–4. Committed
locally; not pushed yet.

## 1. Suggestions and outcome

| Reviewer | Suggestion | Outcome |
|---|---|---|
| cd24 | Cache each dataset's per-sweep resonance fits so exclude/restore refits only the two property fits. Profile before and after, and test that the values are unchanged | **Done**: 0.13 s → 0.002 s, identical results |
| wgguan (and cd24) | A small drawing of the system, with the boundaries marked | **Done**: mermaid diagram in ARCHITECTURE.md, linked from the README |
| both | Name the original data, what cannot be rebuilt, and where it is backed up | **Done**: README section, with the backup confirmed by the owner |
| cd24 (finding) | One active dataset for all users and tabs | **Documented** as a known limit in README and ARCHITECTURE |
| wgguan | The API should send the starting-field range and equation text | **Already staged** as the round 3 geometry task; now cross-referenced |

## 2. Owner's decisions

- The bundled data is backed up offline on the owner's **cloud drive**.
- Implement all of the above. The shared-dataset limit is documented, not fixed.

## 3. Profile (`make profile`, new)

The 49 demo sweeps with one exclusion, median of 5 runs, in the app container:

| | Before cache | After cache |
|---|---|---|
| Cold (nothing cached) | 0.131 s | 0.131 s |
| Exclusion after a first analysis | 0.130–0.140 s | **0.002 s** |

- Under `cProfile`, the 49 `fit_derivative_signal` calls take 60 % of a
  cold run, and reading the CSVs most of the rest. The Kittel and linewidth
  fits are negligible, which matches Helena's profile (72 % / 27 %). Her
  absolute time, 0.33 s, was on her laptop.
- The cache stores each sweep's parsed data and fit, so a warm run skips both.
- Helena also said "at the shipped size nothing here needs to be faster",
  which is still true. The cache matters most near the 1000-file upload
  limit, where a cold run is several seconds.

## 4. Design notes

- **Cache key:** the file's resolved path, size and modification time
  (in ns), plus the linewidth seed. An edited file refits only that file. A
  new upload lands in a new `/tmp` folder, so it never reuses old fits. A new
  seed refits everything.
- **Bounded and thread-safe:** an LRU `OrderedDict` of at most
  `RESONANCE_CACHE_SIZE = 2048` sweeps, guarded by a lock. Cached entries
  are frozen dataclasses and are never changed.
- **The answer does not change:** a test compares a warm result with a cold
  one with `==` on the whole response dict, and they are equal.
- **Known gap:** a file rewritten with the same size inside the same
  nanosecond timestamp would be missed. Neither the bundled data (read-only
  in the image) nor uploads (always a new folder) can do that.

## 5. Commits

| Commit | What |
|---|---|
| `3ba0321` | Per-sweep cache, three fail-first tests, `tests/profile_analysis.py`, and the `make profile` target |
| next | ARCHITECTURE diagram and cache notes, README data and backup section, the known limit, the profile note, TASKS, this log |

## 6. Verification

- `make profile` was run before the change (baseline above), then after.
- The three cache tests failed first on the old code (no
  `clear_resonance_cache`), then passed. They cover: 13 fits, then 0 on
  exclude and restore; warm == cold; and a changed file refitting 1 sweep
  while a new seed refits all 13.
- `make verify` passed: lint, 67 tests (the suite is also faster, 3.9 s →
  2.8 s), the API smoke check, and the Chromium checks.

## 7. Not verified

- The mermaid diagram was not rendered here, because that would need a
  host install. It was checked by hand against the flowchart syntax. Check
  it on GitHub after the push.
- The cache's speed-up was measured with a direct call in the container,
  not through HTTP from a browser. HTTP adds the same overhead before and
  after.
- Two tabs at once (the shared-dataset limit) was not tested; it is
  documented only.
- Neither reviewer has seen the changes.
