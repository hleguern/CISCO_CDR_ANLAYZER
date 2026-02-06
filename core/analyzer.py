"""
Main CDR/CMR Analyzer class - orchestrates all analysis
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
import logging
from datetime import datetime

from ..config.settings import Settings
from .data_loader import CDRLoader, CMRLoader
from .data_processor import DataProcessor

logger = logging.getLogger(__name__)


class CiscoCDRAnalyzer:
    """
    Main analyzer class that orchestrates CDR/CMR analysis
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the analyzer
        
        :param settings: Optional Settings object
        """
        self.settings = settings or Settings()
        self.processor = DataProcessor(self.settings)
        
        # Data storage
        self.cdr_df: Optional[pd.DataFrame] = None
        self.cmr_df: Optional[pd.DataFrame] = None
        self.merged_df: Optional[pd.DataFrame] = None
        
        # Analysis modules (initialized lazily)
        self._time_analyzer = None
        self._user_analyzer = None
        self._device_analyzer = None
        self._quality_analyzer = None
        self._hunt_group_analyzer = None
        self._security_analyzer = None
        self._visualizer = None
        
        # Metadata
        self.load_timestamp: Optional[datetime] = None
        self.cdr_file_path: Optional[str] = None
        self.cmr_file_path: Optional[str] = None
    
    # ==================== DATA LOADING ====================
    
    def load_cdr(
        self, 
        file_path: Union[str, Path], 
        encoding: str = 'utf-8'
    ) -> pd.DataFrame:
        """
        Load and process CDR file(s)
        
        :param file_path: Path to CDR file, directory, or glob pattern
        :param encoding: File encoding
        :return: Processed CDR DataFrame
        """
        logger.info(f"Loading CDR from: {file_path}")
        
        loader = CDRLoader(encoding=encoding)
        raw_df = loader.load(file_path)
        
        self.cdr_df = self.processor.process_cdr(raw_df)
        self.cdr_file_path = str(file_path)
        self.load_timestamp = datetime.now()
        
        logger.info(f"CDR loaded and processed: {len(self.cdr_df)} records")
        return self.cdr_df
    
    def load_cmr(
        self, 
        file_path: Union[str, Path], 
        encoding: str = 'utf-8'
    ) -> pd.DataFrame:
        """
        Load and process CMR file(s)
        
        :param file_path: Path to CMR file, directory, or glob pattern
        :param encoding: File encoding
        :return: Processed CMR DataFrame
        """
        logger.info(f"Loading CMR from: {file_path}")
        
        loader = CMRLoader(encoding=encoding)
        raw_df = loader.load(file_path)
        
        self.cmr_df = self.processor.process_cmr(raw_df)
        self.cmr_file_path = str(file_path)
        
        logger.info(f"CMR loaded and processed: {len(self.cmr_df)} records")
        return self.cmr_df
    
    def merge_data(self) -> Optional[pd.DataFrame]:
        """
        Merge CDR and CMR data
        
        :return: Merged DataFrame or None if data not loaded
        """
        if self.cdr_df is None:
            logger.error("CDR data not loaded")
            return None
        
        if self.cmr_df is None:
            logger.warning("CMR data not loaded, using CDR only")
            self.merged_df = self.cdr_df.copy()
        else:
            self.merged_df = self.processor.merge_cdr_cmr(self.cdr_df, self.cmr_df)
        
        return self.merged_df
    
    # ==================== ANALYSIS MODULES ====================
    
    @property
    def time(self):
        """Get time analysis module"""
        if self._time_analyzer is None:
            from ..analysis.time_analysis import TimeAnalyzer
            self._time_analyzer = TimeAnalyzer(self)
        return self._time_analyzer
    
    @property
    def users(self):
        """Get user analysis module"""
        if self._user_analyzer is None:
            from ..analysis.user_analysis import UserAnalyzer
            self._user_analyzer = UserAnalyzer(self)
        return self._user_analyzer
    
    @property
    def devices(self):
        """Get device analysis module"""
        if self._device_analyzer is None:
            from ..analysis.device_analysis import DeviceAnalyzer
            self._device_analyzer = DeviceAnalyzer(self)
        return self._device_analyzer
    
    @property
    def quality(self):
        """Get quality analysis module"""
        if self._quality_analyzer is None:
            from ..analysis.quality_analysis import QualityAnalyzer
            self._quality_analyzer = QualityAnalyzer(self)
        return self._quality_analyzer
    
    @property
    def hunt_groups(self):
        """Get hunt group analysis module"""
        if self._hunt_group_analyzer is None:
            from ..analysis.hunt_group_analysis import HuntGroupAnalyzer
            self._hunt_group_analyzer = HuntGroupAnalyzer(self)
        return self._hunt_group_analyzer
    
    @property
    def security(self):
        """Get security analysis module"""
        if self._security_analyzer is None:
            from ..analysis.security_analysis import SecurityAnalyzer
            self._security_analyzer = SecurityAnalyzer(self)
        return self._security_analyzer
    
    @property
    def viz(self):
        """Get visualization module"""
        if self._visualizer is None:
            from ..visualization.charts import ChartGenerator
            self._visualizer = ChartGenerator(self)
        return self._visualizer
    
    # ==================== BASIC QUERIES ====================
    
    def get_call_summary(self) -> Dict[str, Any]:
        """Get overall call statistics summary"""
        if self.cdr_df is None:
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr_df
        answered = df[df['answered']]
        
        summary = {
            'total_calls': len(df),
            'answered_calls': len(answered),
            'missed_calls': len(df) - len(answered),
            'answer_rate_pct': round(len(answered) / len(df) * 100, 2) if len(df) > 0 else 0,
            'total_duration_sec': int(df['duration'].sum()),
            'total_duration_formatted': self._format_duration(df['duration'].sum()),
            'avg_duration_sec': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
            'max_duration_sec': int(df['duration'].max()),
            'avg_ring_time_sec': round(df['ring_time'].mean(), 1) if 'ring_time' in df.columns else 0,
            'call_types': df['call_type'].value_counts().to_dict(),
            'unique_callers': df['callingPartyNumber'].nunique(),
            'unique_called': df['finalCalledPartyNumber'].nunique(),
            'unique_orig_devices': df['origDeviceName'].nunique(),
            'unique_dest_devices': df['destDeviceName'].nunique(),
        }
        
        if 'dateTimeOrigination_dt' in df.columns:
            summary['date_range'] = {
                'start': df['dateTimeOrigination_dt'].min().isoformat(),
                'end': df['dateTimeOrigination_dt'].max().isoformat(),
                'days': (df['dateTimeOrigination_dt'].max() - 
                        df['dateTimeOrigination_dt'].min()).days + 1
            }
        
        return summary
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """Get quality metrics summary"""
        if self.cmr_df is None:
            return {'error': 'CMR data not loaded'}
        
        df = self.cmr_df
        
        summary = {
            'total_records': len(df),
            'metrics': {
                'jitter': {
                    'orig_avg': round(df['origjitter'].mean(), 2),
                    'orig_max': round(df['origjitter'].max(), 2),
                    'dest_avg': round(df['destjitter'].mean(), 2),
                    'dest_max': round(df['destjitter'].max(), 2),
                },
                'latency': {
                    'orig_avg': round(df['origlatency'].mean(), 2),
                    'orig_max': round(df['origlatency'].max(), 2),
                    'dest_avg': round(df['destlatency'].mean(), 2),
                    'dest_max': round(df['destlatency'].max(), 2),
                },
                'packet_loss': {
                    'orig_total': int(df['orignumberPacketsLost'].sum()),
                    'dest_total': int(df['destnumberPacketsLost'].sum()),
                    'orig_avg_pct': round(df['orig_packet_loss_pct'].mean(), 4),
                    'dest_avg_pct': round(df['dest_packet_loss_pct'].mean(), 4),
                }
            }
        }
        
        # MOS scores if calculated
        if 'avg_mos' in df.columns:
            summary['mos'] = {
                'average': round(df['avg_mos'].mean(), 2),
                'min': round(df['avg_mos'].min(), 2),
                'max': round(df['avg_mos'].max(), 2),
            }
        
        # Quality status distribution
        if 'quality_status' in df.columns:
            summary['quality_distribution'] = df['quality_status'].value_counts().to_dict()
        
        return summary
    
    def get_data(self, merged: bool = True) -> pd.DataFrame:
        """
        Get the analysis DataFrame
        
        :param merged: If True, return merged CDR/CMR data
        :return: DataFrame
        """
        if merged and self.merged_df is not None:
            return self.merged_df
        if self.cdr_df is not None:
            return self.cdr_df
        return pd.DataFrame()
    
    # ==================== HELPER METHODS ====================
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in seconds to human readable string"""
        seconds = int(seconds)
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"
    
    def print_summary(self):
        """Print formatted summary to console"""
        print("\n" + "=" * 70)
        print("              CISCO CDR/CMR ANALYSIS SUMMARY")
        print("=" * 70)
        
        call_summary = self.get_call_summary()
        
        if 'error' in call_summary:
            print(f"\n❌ {call_summary['error']}")
            return
        
        print("\n📞 CALL STATISTICS")
        print("-" * 50)
        print(f"  Total Calls:         {call_summary['total_calls']:,}")
        print(f"  Answered Calls:      {call_summary['answered_calls']:,}")
        print(f"  Missed Calls:        {call_summary['missed_calls']:,}")
        print(f"  Answer Rate:         {call_summary['answer_rate_pct']}%")
        print(f"  Total Duration:      {call_summary['total_duration_formatted']}")
        print(f"  Average Duration:    {call_summary['avg_duration_sec']}s")
        print(f"  Unique Callers:      {call_summary['unique_callers']:,}")
        
        if 'date_range' in call_summary:
            dr = call_summary['date_range']
            print(f"\n📅 DATE RANGE")
            print("-" * 50)
            print(f"  From:  {dr['start']}")
            print(f"  To:    {dr['end']}")
            print(f"  Days:  {dr['days']}")
        
        print("\n📊 CALL TYPES")
        print("-" * 50)
        for call_type, count in call_summary.get('call_types', {}).items():
            pct = count / call_summary['total_calls'] * 100
            print(f"  {call_type:15s}: {count:>8,} ({pct:>5.1f}%)")
        
        if self.cmr_df is not None:
            quality = self.get_quality_summary()
            print("\n📶 QUALITY METRICS")
            print("-" * 50)
            m = quality.get('metrics', {})
            print(f"  Avg Jitter:      {m.get('jitter', {}).get('orig_avg', 'N/A')} ms (orig)")
            print(f"  Avg Latency:     {m.get('latency', {}).get('orig_avg', 'N/A')} ms (orig)")
            print(f"  Packet Loss:     {m.get('packet_loss', {}).get('orig_avg_pct', 'N/A')}% (orig)")
            
            if 'mos' in quality:
                print(f"  Average MOS:     {quality['mos']['average']}")
        
        print("\n" + "=" * 70 + "\n")