"""
Data processing and transformation for CDR/CMR data
"""

import pandas as pd
import numpy as np
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging

from ..config.settings import Settings

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process and transform CDR/CMR data"""
    
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
    
    def process_cdr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process CDR DataFrame - convert timestamps, calculate durations, etc.
        
        :param df: Raw CDR DataFrame
        :return: Processed CDR DataFrame
        """
        df = df.copy()
        
        # Convert timestamps
        df = self._convert_timestamps(df)
        
        # Extract time components
        df = self._extract_time_components(df)
        
        # Clean string columns
        df = self._clean_string_columns(df)
        
        # Determine call types
        df = self._determine_call_types(df)
        
        # Calculate additional metrics
        df = self._calculate_cdr_metrics(df)
        
        # Map cause codes
        df = self._map_cause_codes(df)
        
        logger.info(f"CDR processed: {len(df)} records")
        return df
    
    def process_cmr(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process CMR DataFrame - parse VQ metrics, calculate quality scores
        
        :param df: Raw CMR DataFrame
        :return: Processed CMR DataFrame
        """
        df = df.copy()
        
        # Convert numeric columns
        df = self._convert_numeric_columns(df)
        
        # Calculate packet loss percentages
        df = self._calculate_packet_loss(df)
        
        # Parse VQ metrics strings
        df = self._parse_vq_metrics(df)
        
        # Calculate MOS scores
        df = self._calculate_mos_scores(df)
        
        # Classify quality
        df = self._classify_quality(df)
        
        logger.info(f"CMR processed: {len(df)} records")
        return df
    
    def _convert_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert Unix timestamps to datetime"""
        timestamp_cols = [
            'dateTimeOrigination', 
            'dateTimeConnect', 
            'dateTimeDisconnect'
        ]
        
        for col in timestamp_cols:
            if col in df.columns:
                df[f'{col}_dt'] = pd.to_datetime(
                    df[col], unit='s', errors='coerce'
                )
        
        return df
    
    def _extract_time_components(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract time components for analysis"""
        if 'dateTimeOrigination_dt' in df.columns:
            dt_col = df['dateTimeOrigination_dt']
            df['year'] = dt_col.dt.year
            df['month'] = dt_col.dt.month
            df['week'] = dt_col.dt.isocalendar().week
            df['day'] = dt_col.dt.day
            df['date'] = dt_col.dt.date
            df['hour'] = dt_col.dt.hour
            df['minute'] = dt_col.dt.minute
            df['day_of_week'] = dt_col.dt.dayofweek
            df['day_name'] = dt_col.dt.day_name()
            df['is_weekend'] = df['day_of_week'].isin([5, 6])
            
            # Business hours check
            bh = self.settings.business_hours
            df['is_business_hours'] = (
                (df['hour'] >= bh.start_hour) & 
                (df['hour'] < bh.end_hour) &
                (df['day_of_week'].isin(bh.business_days))
            )
        
        return df
    
    def _clean_string_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean phone numbers and device names"""
        str_cols = [
            'callingPartyNumber', 
            'finalCalledPartyNumber',
            'origCalledPartyNumber',
            'lastRedirectDn',
            'origDeviceName', 
            'destDeviceName',
            'callingPartyNumber_uri',
            'callingPartyUnicodeLoginUserID',
            'huntPilotDN',
        ]
        
        for col in str_cols:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .replace('\\\\', '', regex=True)
                    .replace('nan', '', regex=False)
                    .str.strip()
                )
        
        return df
    
    def _determine_call_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Determine call direction and type"""
        
        def get_call_type(row):
            orig = str(row.get('origDeviceName', ''))
            dest = str(row.get('destDeviceName', ''))
            
            is_orig_trunk = any(p in orig.upper() for p in self.settings.trunk_patterns)
            is_dest_trunk = any(p in dest.upper() for p in self.settings.trunk_patterns)
            
            if is_orig_trunk and not is_dest_trunk:
                return 'inbound'
            elif is_dest_trunk and not is_orig_trunk:
                return 'outbound'
            elif is_orig_trunk and is_dest_trunk:
                return 'transit'
            elif orig.startswith('SEP') or orig.startswith('CSF'):
                if dest.startswith('SEP') or dest.startswith('CSF'):
                    return 'internal'
            return 'other'
        
        def get_device_type(device_name):
            device_name = str(device_name).upper()
            for pattern, device_type in self.settings.device_patterns.items():
                if pattern in device_name:
                    return device_type
            return 'Unknown'
        
        df['call_type'] = df.apply(get_call_type, axis=1)
        df['orig_device_type'] = df['origDeviceName'].apply(get_device_type)
        df['dest_device_type'] = df['destDeviceName'].apply(get_device_type)
        
        return df
    
    def _calculate_cdr_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate additional CDR metrics"""
        
        # Answered flag
        if 'duration' in df.columns:
            df['duration'] = pd.to_numeric(df['duration'], errors='coerce').fillna(0)
            df['answered'] = df['duration'] > 0
        
        # Ring time
        if 'dateTimeConnect' in df.columns and 'dateTimeOrigination' in df.columns:
            df['ring_time'] = df['dateTimeConnect'] - df['dateTimeOrigination']
            df['ring_time'] = df['ring_time'].apply(lambda x: max(0, x) if pd.notna(x) else 0)
        
        # Wait time in queue
        if 'totalWaitTimeInQueue' in df.columns:
            df['totalWaitTimeInQueue'] = pd.to_numeric(
                df['totalWaitTimeInQueue'], errors='coerce'
            ).fillna(0)
        
        # Is transfer/forward
        if 'lastRedirectDn' in df.columns:
            df['is_transferred'] = df['lastRedirectDn'].str.len() > 0
        
        # Hunt group call
        if 'huntPilotDN' in df.columns:
            df['is_hunt_group'] = df['huntPilotDN'].str.len() > 0
        
        return df
    
    def _map_cause_codes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Map numeric cause codes to descriptions"""
        
        for col in ['origCause_value', 'destCause_value']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                desc_col = col.replace('_value', '_description')
                df[desc_col] = df[col].map(self.settings.cause_codes).fillna('Unknown')
        
        return df
    
    def _convert_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert CMR numeric columns"""
        numeric_cols = [
            'orignumberPacketsSent', 'orignumberPacketsReceived',
            'orignumberPacketsLost', 'orignumberOctetsReceived',
            'destnumberPacketsSent', 'destnumberPacketsReceived',
            'destnumberPacketsLost', 'destnumberOctetsReceived',
            'origjitter', 'destjitter',
            'origlatency', 'destlatency',
            'origCodec', 'destCodec',
        ]
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    
    def _calculate_packet_loss(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate packet loss percentages"""
        
        if 'orignumberPacketsSent' in df.columns:
            df['orig_packet_loss_pct'] = np.where(
                df['orignumberPacketsSent'] > 0,
                (df['orignumberPacketsLost'] / df['orignumberPacketsSent']) * 100,
                0
            )
        
        if 'destnumberPacketsSent' in df.columns:
            df['dest_packet_loss_pct'] = np.where(
                df['destnumberPacketsSent'] > 0,
                (df['destnumberPacketsLost'] / df['destnumberPacketsSent']) * 100,
                0
            )
        
        # Total packet loss
        if 'orig_packet_loss_pct' in df.columns and 'dest_packet_loss_pct' in df.columns:
            df['avg_packet_loss_pct'] = (
                df['orig_packet_loss_pct'] + df['dest_packet_loss_pct']
            ) / 2
        
        return df
    
    def _parse_vq_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Parse VQ metrics strings into separate columns"""
        
        vq_metrics = {
            'CCR': float,       # Concealment Ratio
            'ICR': float,       # Interval Concealment Ratio
            'ICRmx': float,     # Max Interval Concealment Ratio
            'CS': int,          # Concealment Seconds
            'SCS': int,         # Severely Concealed Seconds
            'VoPktLost': int,   # Voice Packets Lost
            'VoPktDis': int,    # Voice Packets Discarded
            'VoOneWayDelayMs': int,   # One-way Delay
            'maxJitter': int,   # Maximum Jitter
            'VoRxCodec': str,   # Receive Codec
            'VoPktSizeMs': int, # Packet Size
            'MLQK': float,      # MOS-LQK (Listening Quality)
        }
        
        def extract_metric(value, metric_name, dtype):
            if pd.isna(value) or str(value) in ['\\', '\\ ', '', 'nan']:
                return None
            match = re.search(f'{metric_name}=([^;]+)', str(value))
            if match:
                try:
                    val = match.group(1)
                    if dtype == float:
                        return float(val)
                    elif dtype == int:
                        return int(float(val))
                    return val
                except (ValueError, TypeError):
                    return None
            return None
        
        for prefix, col in [('orig', 'origvarVQMetrics'), ('dest', 'destvarVQMetrics')]:
            if col in df.columns:
                for metric, dtype in vq_metrics.items():
                    new_col = f'{prefix}_{metric}'
                    df[new_col] = df[col].apply(
                        lambda x: extract_metric(x, metric, dtype)
                    )
        
        return df
    
    def _calculate_mos_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Mean Opinion Score (MOS) based on network metrics
        Using E-model R-factor calculation
        """
        
        def calculate_r_factor(latency, jitter, packet_loss):
            """Calculate R-factor from network metrics"""
            # Base R-factor
            R = 93.2
            
            # Delay impairment (Id)
            delay = latency + jitter
            if delay < 160:
                Id = 0
            else:
                Id = 0.024 * delay + 0.11 * (delay - 177.3) * (delay > 177.3)
            
            # Equipment impairment (Ie) - simplified for G.711
            Ie = 0
            
            # Packet loss impairment
            Ie_eff = Ie + (95 - Ie) * packet_loss / (packet_loss + 10)
            
            # Calculate R-factor
            R = R - Id - Ie_eff
            
            return max(0, min(100, R))
        
        def r_to_mos(R):
            """Convert R-factor to MOS score"""
            if R < 0:
                return 1.0
            elif R > 100:
                return 4.5
            else:
                MOS = 1 + 0.035 * R + R * (R - 60) * (100 - R) * 7e-6
                return max(1.0, min(4.5, MOS))
        
        # Calculate for origin
        if all(c in df.columns for c in ['origlatency', 'origjitter', 'orig_packet_loss_pct']):
            df['orig_r_factor'] = df.apply(
                lambda row: calculate_r_factor(
                    row['origlatency'],
                    row['origjitter'], 
                    row['orig_packet_loss_pct']
                ), axis=1
            )
            df['orig_mos'] = df['orig_r_factor'].apply(r_to_mos)
        
        # Calculate for destination  
        if all(c in df.columns for c in ['destlatency', 'destjitter', 'dest_packet_loss_pct']):
            df['dest_r_factor'] = df.apply(
                lambda row: calculate_r_factor(
                    row['destlatency'],
                    row['destjitter'],
                    row['dest_packet_loss_pct']
                ), axis=1
            )
            df['dest_mos'] = df['dest_r_factor'].apply(r_to_mos)
        
        # Average MOS
        if 'orig_mos' in df.columns and 'dest_mos' in df.columns:
            df['avg_mos'] = (df['orig_mos'] + df['dest_mos']) / 2
        
        # Use VQ reported MOS if available
        if 'orig_MLQK' in df.columns:
            df['orig_mos_reported'] = df['orig_MLQK']
        if 'dest_MLQK' in df.columns:
            df['dest_mos_reported'] = df['dest_MLQK']
        
        return df
    
    def _classify_quality(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify call quality based on metrics"""
        
        thresholds = self.settings.quality
        
        def classify_jitter(jitter):
            if pd.isna(jitter):
                return 'unknown'
            if jitter <= thresholds.jitter_warning:
                return 'good'
            elif jitter <= thresholds.jitter_critical:
                return 'warning'
            return 'critical'
        
        def classify_latency(latency):
            if pd.isna(latency):
                return 'unknown'
            if latency <= thresholds.latency_warning:
                return 'good'
            elif latency <= thresholds.latency_critical:
                return 'warning'
            return 'critical'
        
        def classify_packet_loss(pl):
            if pd.isna(pl):
                return 'unknown'
            if pl <= thresholds.packet_loss_warning:
                return 'good'
            elif pl <= thresholds.packet_loss_critical:
                return 'warning'
            return 'critical'
        
        def classify_mos(mos):
            if pd.isna(mos):
                return 'unknown'
            if mos >= thresholds.mos_good:
                return 'good'
            elif mos >= thresholds.mos_acceptable:
                return 'acceptable'
            elif mos >= thresholds.mos_poor:
                return 'poor'
            return 'bad'
        
        # Classify individual metrics
        for prefix in ['orig', 'dest']:
            if f'{prefix}jitter' in df.columns:
                df[f'{prefix}_jitter_status'] = df[f'{prefix}jitter'].apply(classify_jitter)
            if f'{prefix}latency' in df.columns:
                df[f'{prefix}_latency_status'] = df[f'{prefix}latency'].apply(classify_latency)
            if f'{prefix}_packet_loss_pct' in df.columns:
                df[f'{prefix}_pl_status'] = df[f'{prefix}_packet_loss_pct'].apply(classify_packet_loss)
            if f'{prefix}_mos' in df.columns:
                df[f'{prefix}_mos_status'] = df[f'{prefix}_mos'].apply(classify_mos)
        
        # Overall quality classification
        def overall_quality(row):
            statuses = []
            for col in row.index:
                if col.endswith('_status') and row[col] != 'unknown':
                    statuses.append(row[col])
            
            if not statuses:
                return 'unknown'
            if 'critical' in statuses or 'bad' in statuses:
                return 'poor'
            if 'warning' in statuses or 'poor' in statuses:
                return 'fair'
            if 'acceptable' in statuses:
                return 'acceptable'
            return 'good'
        
        df['quality_status'] = df.apply(overall_quality, axis=1)
        
        return df
    
    def merge_cdr_cmr(
        self, 
        cdr_df: pd.DataFrame, 
        cmr_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge CDR and CMR data
        
        :param cdr_df: Processed CDR DataFrame
        :param cmr_df: Processed CMR DataFrame
        :return: Merged DataFrame
        """
        merge_keys = ['globalCallID_callManagerId', 'globalCallID_callId']
        
        merged = pd.merge(
            cdr_df,
            cmr_df,
            on=merge_keys,
            how='left',
            suffixes=('', '_cmr')
        )
        
        logger.info(f"Merged CDR/CMR: {len(merged)} records")
        return merged