"""Finish the UAOS rollout on this PC in one run: regression, hooks, global-rules canon, generator, checks, sentinel,
commit and push. Dry run unless --apply. No step asks the user anything; the receipt records every step.

    python uaos_everywhere/deploy_to_this_pc.py                    # plan only
    python uaos_everywhere/deploy_to_this_pc.py --apply --push     # do it, commit and push

See docs/43_one-command-pc-rollout-u41.md.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v7_harness.deploy_pc import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
