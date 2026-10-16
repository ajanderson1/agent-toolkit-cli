# Manifest — Issue #513 (Pytest User-State Isolation)

- issue: 513
- status: firm
- rung: R0
- climb_command: `uv run pytest -q tests/test_test_home_isolation.py tests/test_cli/test_skill_install_engine.py`
- climb_exit: 0 (19 passed, 1 skipped)
- full_suite_command: `uv run pytest -q`
- full_suite_exit: 0 (2386 passed, 5 skipped)
- evidence_path: `assets/verification/513/`
- artifacts:
  - `climb.txt`: output from climb command verifying regression and installation isolation
  - `full-suite.txt`: output from full pytest run under isolation boundary
- checks:
  - pytest startup redirects user-state paths (HOME, USERPROFILE, XDG_CONFIG_HOME, harness homes) before project imports: PASS
  - representative global skill install places canonical skill and lockfile in temporary sandbox root: PASS
  - synthetic outer-home sentinels remain untouched during install and inspection probes: PASS
  - sandbox cleanup removes only exact allocated temporary directory upon shutdown: PASS
  - full test suite executes cleanly without accessing or polluting developer assets: PASS
