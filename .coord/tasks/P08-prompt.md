Add `coord status` subcommand to `v7_harness/cli.py` and a test in `tests/test_cli.py`.

In `v7_harness/cli.py`:
Add `cmd_coord_status` right before `cmd_coord_sentinel`:
```python
def cmd_coord_status(args: argparse.Namespace) -> int:
    """Report coordinator and harness health status."""
    project = Path(args.project)
    lock_file = project / ".work" / "QUIET_LOCK"
    lock_status = "LOCKED" if lock_file.is_file() else "CLEAN"

    mailbox_dir = project / ".coord" / "mailbox" / "inbox"
    mailbox_count = len(list(mailbox_dir.glob("*.json"))) if mailbox_dir.is_dir() else 0

    stream_file = project / ".coord" / "stream" / "events.jsonl"
    stream_count = len(stream_file.read_text(encoding="utf-8").splitlines()) if stream_file.is_file() else 0

    usage_file = project / ".coord" / "usage" / "runs.jsonl"
    usage_count = len(usage_file.read_text(encoding="utf-8").splitlines()) if usage_file.is_file() else 0

    out = {
        "ok": True,
        "lock": lock_status,
        "mailbox_pending": mailbox_count,
        "stream_events": stream_count,
        "ledger_entries": usage_count,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0
```

In `v7_harness/cli.py` inside `build_parser()`:
Right before `p_coord_sentinel = p_coord_subs.add_parser("sentinel")`, add:
```python
    p_coord_status = p_coord_subs.add_parser("status")
    p_coord_status.add_argument("--project", default=".", help="Project root (default: .)")
    p_coord_status.set_defaults(func=cmd_coord_status)
```

In `tests/test_cli.py` inside `TestCLI`:
Add test method:
```python
    def test_cli_coord_status(self):
        ret = main(["coord", "status", "--project", str(self.root)])
        self.assertEqual(ret, 0)
```
