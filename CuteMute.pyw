"""Console-free entry point: double-click this, or run it with pythonw.exe."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cutemute.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
