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
| Secrets | `gitleaks detect --source . --redact -v` (all history, 12 commits as of run 2) and `gitleaks detect --no-git --source . --redact` |
| GitHub Actions | SHA pinning of `uses:`, top-level `permissions:`, `${{ github.event.* }}` interpolated into `run:` |
| Dockerfiles | none present |
| Tests / lint | `uv sync --extra dev`, `uv run pytest -q`, `make test-ci`, `uv run ruff check .`, `uv run ruff format --check .` |
| Coverage | `uv run --with pytest-cov pytest -q --cov=illusionframe --cov-report=term` (ad hoc; does not touch `uv.lock`) |
| Makefile/CLI drift | `tests/test_makefile.py` (strict xfail until G-009 verbs exist) |

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
| G-009 | low | quality: `make demo` / `make fetch-models` call CLI subcommands (`evolve`, `fetch-models`) and `examples/painting.jpg` that do not exist yet | `Makefile` | open (tracked by strict xfail `test_makefile_cli_verbs_are_registered`) | 2026-10-15 |
| G-010 | low | bug: `cli.main` called `args.func` unconditionally, so any verb registered without `set_defaults(func=...)` crashed with `AttributeError` | `src/illusionframe/cli.py` | fixed (run 2) | 2026-10-17 |

No secrets found (gitleaks: 0 in history, 0 in working tree; re-checked run 2). Bandit: 0 issues. Custom grep: 0 hits.

## Metrics

Run 2 (2026-10-17):

| Metric | Before | After |
|---|---|---|
| Open vulns crit / high / med / low | 0 / 3 / 1 / 1 | 0 / 3 / 1 / 1 (unchanged: all blocked on torch pin or `workflow` scope) |
| Open bugs | 2 (G-004, G-010) | 1 (G-004) |
| Test count | 10 (9 pass, 1 xfail) | 13 (11 pass, 2 strict xfail: G-004, G-009) |
| Failing tests | 0 | 0 |
| Ruff lint / format | 0 / clean | 0 / clean |
| Bandit | 0 | 0 |
| Coverage (ad hoc) | not measured | 92% total (`cli.py` 95%, `config.py` 100%) |

Run 1 (2026-10-15): vulns 0/3/1/1 -> 0/3/1/1; tests 0 -> 10; open bugs 3 -> 1.

## Backlog (prioritized)

0. **Owner action: apply the CI patch** (G-004, G-006, G-007). The automation token cannot push workflow files. In `.github/workflows/ci.yml`:
   - add a top-level `permissions:` block with `contents: read`;
   - `actions/checkout@v4` -> `actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4.4.0`;
   - `astral-sh/setup-uv@v3` -> `astral-sh/setup-uv@caf0cab7a618c569241d31dcd442f54681755d39  # v3.2.4`;
   - smoke import: `illusionframe.imageops` -> `illusionframe.config` (or add `imageops`).
   Then remove the `xfail` marker in `tests/test_ci_workflow.py` (strict xfail will flag it as XPASS once fixed).
1. G-001..G-003: when the Intel-Mac constraint is dropped (or via a Linux/GPU-only extra), move to torch >= 2.6, diffusers >= 0.38, transformers >= 5.10. Until then, when model-loading code is written: keep `trust_remote_code=False`, pass `use_safetensors=True`, pin `revision=` to a commit hash, and allowlist `ILLUSIONFRAME_MODEL_ID` / `TINY_VAE_ID` rather than loading arbitrary repos. Never `torch.load` untrusted files.
2. G-009: implement the subcommands the Makefile advertises with `set_defaults(func=...)` (`test_every_registered_verb_has_a_handler` enforces it), then drop the xfail in `tests/test_makefile.py`.
3. Re-run `osv-scanner` where api.osv.dev is reachable.
4. Add `pytest-cov` to the dev extra. Tried in run 2: `uv lock` cannot reach the pytorch-cpu index from the sandbox, so the lockfile could not be regenerated; reverted. Owner: `uv add --optional dev pytest-cov` locally. Until then coverage is measured with `uv run --with pytest-cov`.
5. When `opencv` / image I/O code lands: validate input paths (no writes outside `ILLUSIONFRAME_RUNS_DIR`), and bound image dimensions before allocating.

## Learnings

- The vulnerable packages are all pinned down by a single constraint (torch 2.2.2 for Intel macOS), so dependency fixes are blocked until that platform requirement changes.
- The repo is an early scaffold: the most valuable fixes right now are keeping CI green and honest.
- (run 2) The sandbox cannot reach download.pytorch.org, so any dependency change that needs `uv lock` must be left to the owner; `uv run --with` covers ad hoc tools.
- (run 2) `origin/main` had no new commits since run 1; the scan surface is unchanged.

New ideas for future checks:
1. Statically check that every module named in CI smoke imports exists (now covered by `tests/test_ci_workflow.py`).
2. Check that Makefile targets only call CLI verbs registered in `cli.build_parser()`.
3. Once model loading exists, grep for `from_pretrained(` calls missing `revision=` / `use_safetensors=True`.
4. (run 2) Fail the scan if `uv.lock` and `pyproject.toml` disagree (`uv lock --check`) once the pytorch index is reachable.
5. (run 2) Track `main` drift: if `origin/main` gains source modules, re-run the custom grep against them first.
6. (run 2) Add `cv2.imread`/`imwrite` path checks to the custom grep once image I/O exists.

## Log

- Run 1 — 2026-10-15: baseline scan. 21 dependency advisories in the optional `diffusion` extra (torch/diffusers/transformers), all blocked by the torch 2.2.2 pin, logged as open. Fixed the empty test suite (pytest exit 5) and validated `TORCH_THREADS`; added 10 tests. CI workflow fixes (missing `imageops` import, SHA pinning, `permissions`) were written but could not be pushed (token lacks `workflow` scope), so they are left as an owner patch with a strict-xfail test tracking G-004. No secrets. osv-scanner unavailable (network). Meta-review due at run 4.
- Run 2 — 2026-10-17: `main` unchanged, merge no-op; no PR review comments. Re-ran pip-audit (same diffusers/transformers/torch advisories, still blocked), bandit (0), custom grep (0), gitleaks history + tree (0). Fixed G-010 (`cli.main` crashed with `AttributeError` on a verb lacking `func`; test `test_subcommand_without_handler_is_usage_error_not_crash`), added `test_every_registered_verb_has_a_handler` and a strict-xfail Makefile/CLI drift test for G-009. Adding pytest-cov failed (`uv lock` cannot reach the pytorch index) and was reverted; coverage measured ad hoc at 92%. Tests 10 -> 13. Not a meta-review run (next at run 4).
