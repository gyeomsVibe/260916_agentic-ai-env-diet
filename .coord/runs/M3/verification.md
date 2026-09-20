# M3 verification

- Scope discovery: Codex and Antigravity both had `mia-vaccine-test/SKILL.md`; both were included.
- Backups: five `.orig` files were copied before application and their SHA-256 values matched the originals recorded in `manifest.md`.
- Diff fidelity: regenerated `git diff --no-index --unified=3` output matched `application.diff` exactly (`DIFF_EXACT=True`). A diff exit code of 1 means expected differences were present.
- Required text: project `pilot run` / `summary.json` / `--approve` / bridge-helper rules, Codex pilot preference, Gemini staging rule, and both MIA fallback sentences each occurred exactly once.
- Skill validation: the first default-locale attempts exited 1 because Python used cp949 for UTF-8 Korean files; rerunning with `PYTHONUTF8=1` returned `Skill is valid!` and exit 0 for both skill folders.
- New-session gate: task `01a0af1b-f9a6-7d22-9d44-f7470b5c103d`, initial and only gate request `P02 과제 해줘`, automatically selected `v7_harness` SQLite `pilot run` and reported the staging → watch → bundle → dry-run path.
- Non-application: no `--approve` value was supplied. `rg "def sub|test_sub"` against the P02 sample source returned exit 1, so the gate task's proposed P02 change was not present in the original source. Only the gate prompt and isolated staging artifacts were observed.
- Gate stop instruction: after routing PASS, the new task was told not to approve or modify source and to stop after the isolated command returns; M3 review did not wait for P02 execution completion.
