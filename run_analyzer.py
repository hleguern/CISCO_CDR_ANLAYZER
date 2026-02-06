#!/usr/bin/env python3
"""
Convenience script to run the CDR/CMR Analyzer

Usage:
    python run_analyzer.py --cdr data/cdr.csv --cmr data/cmr.csv --report
"""

import sys
import os

# Add the package to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cisco_cdr_analyzer.main import main

if __name__ == '__main__':
    main()