# GUARDIAN

Automated security & bug sweep for `juan-garassino/illusionFrame` (public repo). Work lands on the
`claude/guardian` branch only; a meta-review of this process happens every 4th run (count the Log entries below).

## Checks

| Area | Command / rule |
|---|---|
| Python deps | `uv export --frozen --all-extras --no-hashes --no-emit-project > req.txt` then `pip-audit -r req.txt --no-deps --disable-pip`; `torch==2.2.2` audited separately (the `+cpu` local version is not on PyPI) |
| Lockfiles | `osv-scanner -r .` (could not run: api.osv.dev is blocked by the sandbox egress proxy) |
| Code (SAST) | `bandit -r src -q` |
| Custom grep (src) | `eval(`, `exec(`, `pickle`, `torch.load`, `allow_pickle`, `yaml.load`, `shell=True`, `os.system`, `verify=False`, `0.0.0.0`, `debug=True`, SQL string formatting, path traversal, SSRF, CORS `*` |
| Secrets | `gitleaks detect --source . --redact -v` (all history, 11 commits) and `gitleaks detect --no-git --source . --redact` |
| GitHub Actions | SHA pinning of `uses:`, top-level `permissions:`, `${{ github.event.* }}` interpolated into `run:` |
| Dockerfiles | none present |
| Tests / lint | `uv sync --extra dev`, `uv run pytest -q`, `make test-ci`, `uv run ruff check .`, `uv run ruff format --check .` |

## Findings ledger

| id | severity | type | file | status | date |
|---|---|---|---|---|---|
| G-001 | high | dep vuln: torch 2.2.2, 12 advisories (incl. `torch.load` RCE; fixes need torch >= 2.6–2.13) | `pyproject.toml` / `uv.lock` (`diffusion` extra) | open (blocked: torch 2.2.2 is the last wheel for Intel macOS) | 2026-10-15 |
| G-002 | high | dep vuln: diffusers 0.35.2, 3 advisories (`trust_remote_code` bypass / RCE; fix 0.38.0) | `pyproject.toml` / `uv.lock` (`diffusion` extra) | open (blocked: diffusers >= 0.36 needs torch >= 2.4) | 2026-10-15 |
| G-003 | high | dep vuln: transformers 4.57.6, 6 advisories (deserialization RCE, path traversal; fixes in 5.x) | `pyproject.toml` / `uv.lock` (`diffusion` extra) | open (blocked: transformers 5 needs torch >= 2.5) | 2026-10-15 |
| G-004 | med | bug: CI smoke-import step imports non-existent `illusionframe.imageops` (job always fails) | `.github/workflows/ci.yml` | open (patch ready; push token lacks `workflow` scope) | 2026-10-15 |
| G-005 | med | bug: no `tests/` dir, so `pytest` exits 5 ("no tests ran") and `make test-ci` fails CI | `tests/` | fixed | 2026-10-15 |
| G-006 | med | CI: actions referenced by mutable tags (`@v4`, `@v3`) | `.github/workflows/ci.yml` | open (patch ready; needs `workflow` scope) | 2026-10-15 |
| G-007 | low | CI: no `permissions:` block (default token scope) | `.github/workflows/ci.yml` | open (patch ready; needs `workflow` scope) | 2026-10-15 |
| G-008 | low | bug: `ILLUSIONFRAME_TORCH_THREADS` accepted 0/negative and failed with an opaque `int()` error on junk | `src/illusionframe/config.py` | fixed | 2026-10-15 |
| G-009 | low | quality: `make demo` / `make fetch-models` call CLI subcommands (`evolve`, `fetch-models`) and `examples/painting.jpg` that do not exist yet; `cli.main` calls `args.func` that no subparser sets | `Makefile`, `src/illusionframe/cli.py` | open | 2026-10-15 |

No secrets found (gitleaks: 0 in history, 0 in working tree). Bandit: 0 issues. Custom grep: 0 hits.

## Metrics

| Metric | Before | After |
|---|---|---|
| Open vulns crit / high / med / low | 0 / 3 / 1 / 1 (21 dep advisories grouped in G-001..003) | 0 / 3 / 1 / 1 (CI hardening patch pending owner) |
| Open bugs | 3 (G-004, G-005, G-008) | 1 (G-004, tracked by a strict xfail test) |
| Failing tests / CI gates | `pytest` exit 5 (no tests); smoke-import broken | 0 failing (1 strict xfail = G-004); smoke-import still broken until patch applied |
| Test count | 0 | 10 (9 pass, 1 xfail) |
| Ruff lint errors | 0 | 0 |
| Coverage | not measured (pytest-cov not in dev extra) | not measured |

## Backlog (prioritized)

0. **Owner action: apply the CI patch** (G-004, G-006, G-007). The automation token cannot push workflow files. In `.github/workflows/ci.yml`:
   - add a top-level `permissions:` block with `contents: read`;
   - `actions/checkout@v4` -> `actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4.4.0`;
   - `astral-sh/setup-uv@v3` -> `astral-sh/setup-uv@caf0cab7a618c569241d31dcd442f54681755d39  # v3.2.4`;
   - smoke import: `illusionframe.imageops` -> `illusionframe.config` (or add `imageops`).
   Then remove the `xfail` marker in `tests/test_ci_workflow.py` (strict xfail will flag it as XPASS once fixed).
1. G-001..G-003: when the Intel-Mac constraint is dropped (or via a Linux/GPU-only extra), move to torch >= 2.6, diffusers >= 0.38, transformers >= 5.10. Until then, when model-loading code is written: keep `trust_remote_code=False`, pass `use_safetensors=True`, pin `revision=` to a commit hash, and allowlist `ILLUSIONFRAME_MODEL_ID` / `TINY_VAE_ID` rather than loading arbitrary repos. Never `torch.load` untrusted files.
2. G-009: implement the subcommands the Makefile advertises, and give every subparser `set_defaults(func=...)` (add a test that each registered verb has `func`).
3. Re-run `osv-scanner` where api.osv.dev is reachable.
4. Add `pytest-cov` to the dev extra to track coverage.

## Learnings

- The vulnerable packages are all pinned down by a single constraint (torch 2.2.2 for Intel macOS), so dependency fixes are blocked until that platform requirement changes.
- The repo is an early scaffold: the most valuable fixes right now are keeping CI green and honest.

New ideas for future checks:
1. Statically check that every module named in CI smoke imports exists (now covered by `tests/test_ci_workflow.py`).
2. Check that Makefile targets only call CLI verbs registered in `cli.build_parser()`.
3. Once model loading exists, grep for `from_pretrained(` calls missing `revision=` / `use_safetensors=True`.

## Log

- Run 1 — 2026-10-15: baseline scan. 21 dependency advisories in the optional `diffusion` extra (torch/diffusers/transformers), all blocked by the torch 2.2.2 pin, logged as open. Fixed the empty test suite (pytest exit 5) and validated `TORCH_THREADS`; added 10 tests. CI workflow fixes (missing `imageops` import, SHA pinning, `permissions`) were written but could not be pushed (token lacks `workflow` scope), so they are left as an owner patch with a strict-xfail test tracking G-004. No secrets. osv-scanner unavailable (network). Meta-review due at run 4.
