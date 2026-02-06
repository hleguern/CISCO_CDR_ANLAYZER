"""
Data loading modules for CDR and CMR files
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Union
import logging
import glob
import os

logger = logging.getLogger(__name__)


class BaseLoader:
    """Base class for data loaders"""
    
    def __init__(self, encoding: str = 'utf-8'):
        self.encoding = encoding
        self.df: Optional[pd.DataFrame] = None
        
    def _detect_separator(self, filepath: str) -> str:
        """Auto-detect CSV separator"""
        with open(filepath, 'r', encoding=self.encoding) as f:
            first_line = f.readline()
        
        if '\t' in first_line:
            return '\t'
        elif ';' in first_line:
            return ';'
        return ','
    
    def _load_single_file(self, filepath: str) -> pd.DataFrame:
        """Load a single CSV file"""
        sep = self._detect_separator(filepath)
        return pd.read_csv(
            filepath, 
            encoding=self.encoding, 
            low_memory=False,
            sep=sep
        )
    
    def load_multiple_files(self, file_pattern: str) -> pd.DataFrame:
        """
        Load multiple files matching a pattern
        
        :param file_pattern: Glob pattern for files (e.g., 'data/cdr_*.csv')
        :return: Combined DataFrame
        """
        files = glob.glob(file_pattern)
        if not files:
            raise FileNotFoundError(f"No files found matching: {file_pattern}")
        
        dfs = []
        for f in sorted(files):
            logger.info(f"Loading: {f}")
            dfs.append(self._load_single_file(f))
        
        self.df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(self.df)} total records from {len(files)} files")
        return self.df
    
    def load_from_directory(self, directory: str, extension: str = '.csv') -> pd.DataFrame:
        """
        Load all files from a directory
        
        :param directory: Directory path
        :param extension: File extension to match
        :return: Combined DataFrame
        """
        pattern = os.path.join(directory, f'*{extension}')
        return self.load_multiple_files(pattern)


class CDRLoader(BaseLoader):
    """Loader specifically for CDR files"""
    
    # Expected CDR columns
    REQUIRED_COLUMNS = [
        'globalCallID_callManagerId',
        'globalCallID_callId', 
        'dateTimeOrigination',
        'callingPartyNumber',
        'finalCalledPartyNumber',
        'duration'
    ]
    
    OPTIONAL_COLUMNS = [
        'dateTimeConnect',
        'dateTimeDisconnect',
        'origDeviceName',
        'destDeviceName',
        'origCause_value',
        'destCause_value',
        'origCalledPartyNumber',
        'lastRedirectDn',
        'callingPartyNumber_uri',
        'callingPartyUnicodeLoginUserID',
        'origMediaCap_payloadCapability',
        'destMediaCap_payloadCapability',
        'huntPilotDN',
        'huntPilotPartition',
        'calledPartyPattern',
        'origConversationId',
        'destConversationId',
        'origIpAddr',
        'destIpAddr',
        'origNodeId',
        'destNodeId',
        'totalWaitTimeInQueue',
        'callingPartyNumberPartition',
        'finalCalledPartyNumberPartition',
    ]
    
    def load(self, filepath: Union[str, Path]) -> pd.DataFrame:
        """
        Load CDR file(s)
        
        :param filepath: Path to CDR file or glob pattern
        :return: CDR DataFrame
        """
        filepath = str(filepath)
        
        if '*' in filepath or '?' in filepath:
            self.df = self.load_multiple_files(filepath)
        elif os.path.isdir(filepath):
            self.df = self.load_from_directory(filepath)
        else:
            self.df = self._load_single_file(filepath)
        
        self._validate_columns()
        logger.info(f"CDR loaded: {len(self.df)} records")
        return self.df
    
    def _validate_columns(self):
        """Validate that required columns exist"""
        if self.df is None:
            return
        
        missing = set(self.REQUIRED_COLUMNS) - set(self.df.columns)
        if missing:
            logger.warning(f"Missing required CDR columns: {missing}")
        
        # Add missing optional columns as NaN
        for col in self.OPTIONAL_COLUMNS:
            if col not in self.df.columns:
                self.df[col] = np.nan


class CMRLoader(BaseLoader):
    """Loader specifically for CMR files"""
    
    REQUIRED_COLUMNS = [
        'globalCallID_callManagerId',
        'globalCallID_callId',
    ]
    
    QUALITY_COLUMNS = [
        'origdeviceName',
        'destdeviceName',
        'orignumberPacketsSent',
        'orignumberPacketsReceived',
        'orignumberPacketsLost',
        'orignumberOctetsReceived',
        'destnumberPacketsSent',
        'destnumberPacketsReceived',
        'destnumberPacketsLost',
        'destnumberOctetsReceived',
        'origjitter',
        'destjitter',
        'origlatency',
        'destlatency',
        'origvarVQMetrics',
        'destvarVQMetrics',
        'origCodec',
        'destCodec',
    ]
    
    def load(self, filepath: Union[str, Path]) -> pd.DataFrame:
        """
        Load CMR file(s)
        
        :param filepath: Path to CMR file or glob pattern
        :return: CMR DataFrame
        """
        filepath = str(filepath)
        
        if '*' in filepath or '?' in filepath:
            self.df = self.load_multiple_files(filepath)
        elif os.path.isdir(filepath):
            self.df = self.load_from_directory(filepath)
        else:
            self.df = self._load_single_file(filepath)
        
        self._validate_columns()
        logger.info(f"CMR loaded: {len(self.df)} records")
        return self.df
    
    def _validate_columns(self):
        """Validate CMR columns"""
        if self.df is None:
            return
        
        missing = set(self.REQUIRED_COLUMNS) - set(self.df.columns)
        if missing:
            logger.warning(f"Missing required CMR columns: {missing}")
        
        # Add missing quality columns
        for col in self.QUALITY_COLUMNS:
            if col not in self.df.columns:
                self.df[col] = np.nan