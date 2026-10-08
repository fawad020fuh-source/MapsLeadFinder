from __future__ import annotations

import sys

from src.app import run_cli, run_streamlit


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cli()
    else:
        try:
            run_streamlit()
        except Exception:
            run_cli()
