"""
Base class for analysis modules
"""

from typing import TYPE_CHECKING, Optional, Dict, Any, List, Union
import pandas as pd
import logging

if TYPE_CHECKING:
    from ..core.analyzer import CiscoCDRAnalyzer

logger = logging.getLogger(__name__)

import numpy as np
from datetime import datetime, timedelta, date

from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BusinessHoursConfig:
    """Configuration for business hours"""
    start_hour: int = 8
    end_hour: int = 18
    business_days: List[str] = field(default_factory=lambda: [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'
    ])


@dataclass 
class QualityThresholds:
    """Thresholds for call quality metrics"""
    jitter_good: int = 20
    jitter_acceptable: int = 50
    jitter_poor: int = 100
    latency_good: int = 100
    latency_acceptable: int = 200
    latency_poor: int = 300
    packet_loss_good: float = 0.5
    packet_loss_acceptable: float = 1.0
    packet_loss_poor: float = 3.0
    mos_excellent: float = 4.0
    mos_good: float = 3.5
    mos_fair: float = 3.0
    mos_poor: float = 2.5


@dataclass
class AnalyzerSettings:
    """Global settings for the analyzer"""
    business_hours: BusinessHoursConfig = field(default_factory=BusinessHoursConfig)
    quality_thresholds: QualityThresholds = field(default_factory=QualityThresholds)
    extension_directory: Dict[str, str] = field(default_factory=dict)
    department_mapping: Dict[str, str] = field(default_factory=dict)
    codec_bandwidth: Dict[str, float] = field(default_factory=lambda: {
        'G.711': 87.2, 'G.711 A-law': 87.2, 'G.711 u-law': 87.2,
        'G.722': 87.2, 'G.729': 31.2, 'G.729a': 31.2, 'G.729ab': 31.2,
        'iLBC': 38.4, 'iSAC': 48, 'OPUS': 50, 'AAC-LD': 128
    })


class BaseAnalyzer:
    """Base class for all analysis modules"""
    
    def __init__(self, analyzer: 'CiscoCDRAnalyzer'):
        """
        Initialize with reference to main analyzer
        
        :param analyzer: Parent CiscoCDRAnalyzer instance
        """
        self.analyzer = analyzer
    
    @property
    def cdr(self) -> Optional[pd.DataFrame]:
        """Get CDR DataFrame"""
        return self.analyzer.cdr_df
    
    @property
    def cmr(self) -> Optional[pd.DataFrame]:
        """Get CMR DataFrame"""
        return self.analyzer.cmr_df
    
    @property
    def merged(self) -> Optional[pd.DataFrame]:
        """Get merged DataFrame"""
        return self.analyzer.merged_df
    
    @property
    def settings(self):
        """Get settings"""
        return self.analyzer.settings
    
    def _check_cdr_loaded(self) -> bool:
        """Check if CDR data is loaded"""
        if self.cdr is None:
            logger.error("CDR data not loaded")
            return False
        return True
    
    def _check_cmr_loaded(self) -> bool:
        """Check if CMR data is loaded"""
        if self.cmr is None:
            logger.error("CMR data not loaded")
            return False
        return True
    
    def _get_data(self, use_merged: bool = False) -> Optional[pd.DataFrame]:
        """Get the appropriate DataFrame"""
        if use_merged and self.merged is not None:
            return self.merged
        return self.cdr