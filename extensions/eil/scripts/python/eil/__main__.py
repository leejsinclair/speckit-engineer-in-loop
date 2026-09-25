"""Entry point for ``python3 <dir>`` (contract test C-04).

Running a directory puts that directory itself first on ``sys.path``; its modules (for example
``trace.py``) could then shadow the standard library. So this file removes it and adds the
directory's parent instead, which lets ``eil`` import as an ordinary package.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]
sys.path.insert(0, os.path.dirname(_HERE))

from eil.cli import main  # noqa: E402

sys.exit(main())
