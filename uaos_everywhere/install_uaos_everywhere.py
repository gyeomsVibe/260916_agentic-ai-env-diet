"""Install UAOS for every project on this PC. Nothing is written without --apply.

    python uaos_everywhere/install_uaos_everywhere.py            # preview
    python uaos_everywhere/install_uaos_everywhere.py --apply    # install (backups in ~/.uaos-backups/)
    python uaos_everywhere/install_uaos_everywhere.py --check    # exit 1 if something is missing or drifted
    python uaos_everywhere/install_uaos_everywhere.py --apply --register-sentinel D:/path/to/project   # Windows 24/7
    python uaos_everywhere/install_uaos_everywhere.py --apply --uninstall

See uaos_everywhere/README.md for what each step does.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from v7_harness.global_install import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
