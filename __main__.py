"""
Allow running the package as a module: python -m cisco_cdr_analyzer
"""

import sys

from .main import main

if __name__ == '__main__':
    sys.exit(main())