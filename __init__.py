"""
Cisco CDR/CMR Analyzer
A comprehensive tool for analyzing Cisco Unified Communications Manager
Call Detail Records (CDR) and Call Management Records (CMR)
"""

__version__ = "2.0.0"
__author__ = "CDR Analyzer Team"

from .core.analyzer import CiscoCDRAnalyzer
from .core.data_loader import CDRLoader, CMRLoader
from .core.data_processor import DataProcessor

__all__ = [
    'CiscoCDRAnalyzer',
    'CDRLoader',
    'CMRLoader',
    'DataProcessor'
]