"""
Quality analysis for CDR/CMR data
Includes MOS calculation, quality trends, codec analysis, and SLA compliance
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import logging

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class QualityAnalyzer(BaseAnalyzer):
    """Quality-based analysis of call data"""
    
    # ==================== MOS CALCULATION ====================
    
    def calculate_mos_score(
        self,
        latency: float,
        jitter: float,
        packet_loss: float,
        codec: str = 'G.711'
    ) -> float:
        """
        Calculate Mean Opinion Score (MOS) using E-model
        
        :param latency: One-way delay in ms
        :param jitter: Jitter in ms
        :param packet_loss: Packet loss percentage
        :param codec: Codec name for impairment factor
        :return: MOS score (1.0 - 4.5)
        """
        # Codec impairment factors (Ie)
        codec_ie = {
            'G.711': 0,
            'G.711 A-law': 0,
            'G.711 μ-law': 0,
            'G.722': 0,
            'G.729': 11,
            'G.729a': 11,
            'G.729ab': 11,
            'G.723.1': 15,
            'iLBC': 10,
            'OPUS': 5,
            'AMR': 12,
            'AMR-WB': 8,
        }
        
        # Get codec impairment or default
        Ie = codec_ie.get(codec, 10)
        
        # Base R-factor
        R = 93.2
        
        # Delay impairment (Id)
        total_delay = latency + jitter
        if total_delay < 160:
            Id = 0
        else:
            Id = 0.024 * total_delay + 0.11 * (total_delay - 177.3) * int(total_delay > 177.3)
        
        # Effective equipment impairment (Ie-eff)
        # Accounts for packet loss
        Bpl = 25  # Packet loss robustness factor
        Ie_eff = Ie + (95 - Ie) * packet_loss / (packet_loss + Bpl)
        
        # Calculate R-factor
        R = R - Id - Ie_eff
        R = max(0, min(100, R))
        
        # Convert R-factor to MOS
        if R < 0:
            MOS = 1.0
        elif R > 100:
            MOS = 4.5
        else:
            MOS = 1 + 0.035 * R + R * (R - 60) * (100 - R) * 7e-6
        
        return round(max(1.0, min(4.5, MOS)), 2)
    
    def get_mos_distribution(self) -> Dict[str, Any]:
        """
        Get MOS score distribution across all calls
        
        :return: Dictionary with MOS distribution
        """
        if self.cmr is None:
            return {'error': 'CMR data not loaded'}
        
        df = self.cmr.copy()
        
        if 'avg_mos' not in df.columns:
            return {'error': 'MOS scores not calculated'}
        
        mos = df['avg_mos'].dropna()
        
        distribution = {
            'total_calls': len(mos),
            'average': round(mos.mean(), 2),
            'median': round(mos.median(), 2),
            'std_dev': round(mos.std(), 2),
            'min': round(mos.min(), 2),
            'max': round(mos.max(), 2),
            'percentiles': {
                'p10': round(mos.quantile(0.10), 2),
                'p25': round(mos.quantile(0.25), 2),
                'p50': round(mos.quantile(0.50), 2),
                'p75': round(mos.quantile(0.75), 2),
                'p90': round(mos.quantile(0.90), 2),
                'p95': round(mos.quantile(0.95), 2),
            },
            'quality_breakdown': {
                'excellent (≥4.0)': int((mos >= 4.0).sum()),
                'good (3.5-4.0)': int(((mos >= 3.5) & (mos < 4.0)).sum()),
                'acceptable (3.0-3.5)': int(((mos >= 3.0) & (mos < 3.5)).sum()),
                'poor (2.5-3.0)': int(((mos >= 2.5) & (mos < 3.0)).sum()),
                'bad (<2.5)': int((mos < 2.5).sum()),
            }
        }
        
        return distribution
    
    # ==================== QUALITY TRENDS ====================
    
    def get_quality_trend_over_time(
        self,
        period: str = 'daily',
        metric: str = 'mos'
    ) -> pd.DataFrame:
        """
        Get quality metrics trend over time
        
        :param period: 'hourly', 'daily', 'weekly', or 'monthly'
        :param metric: 'mos', 'jitter', 'latency', or 'packet_loss'
        :return: DataFrame with quality trend
        """
        if self.merged is None:
            if self.cmr is None:
                return pd.DataFrame()
            df = self.cmr.copy()
        else:
            df = self.merged.copy()
        
        # Determine grouping column
        if 'dateTimeOrigination_dt' in df.columns:
            dt_col = 'dateTimeOrigination_dt'
        elif 'dateTimeStamp' in df.columns:
            dt_col = 'dateTimeStamp'
        else:
            return pd.DataFrame()
        
        df = df.copy()
        
        if period == 'hourly':
            df['period'] = df[dt_col].dt.floor('H')
        elif period == 'daily':
            df['period'] = df[dt_col].dt.date
        elif period == 'weekly':
            df['period'] = df[dt_col].dt.to_period('W').astype(str)
        else:
            df['period'] = df[dt_col].dt.to_period('M').astype(str)
        
        # Determine columns to aggregate based on metric
        if metric == 'mos':
            agg_cols = {'avg_mos': ['mean', 'min', 'max', 'std']}
            if 'avg_mos' not in df.columns:
                return pd.DataFrame()
        elif metric == 'jitter':
            agg_cols = {
                'origjitter': ['mean', 'max'],
                'destjitter': ['mean', 'max']
            }
        elif metric == 'latency':
            agg_cols = {
                'origlatency': ['mean', 'max'],
                'destlatency': ['mean', 'max']
            }
        elif metric == 'packet_loss':
            agg_cols = {
                'orig_packet_loss_pct': ['mean', 'max'],
                'dest_packet_loss_pct': ['mean', 'max']
            }
        else:
            return pd.DataFrame()
        
        # Filter to available columns
        agg_cols = {k: v for k, v in agg_cols.items() if k in df.columns}
        if not agg_cols:
            return pd.DataFrame()
        
        # Add count
        first_col = list(agg_cols.keys())[0]
        agg_cols[first_col] = agg_cols[first_col] + ['count']
        
        trend = df.groupby('period').agg(agg_cols).reset_index()
        
        # Flatten column names
        trend.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col 
                        for col in trend.columns]
        
        return trend
    
    def get_quality_by_hour(self) -> pd.DataFrame:
        """
        Get quality metrics by hour of day
        
        :return: DataFrame with hourly quality
        """
        if self.merged is None:
            return pd.DataFrame()
        
        df = self.merged.copy()
        
        if 'hour' not in df.columns:
            return pd.DataFrame()
        
        quality_cols = ['avg_mos', 'origjitter', 'destjitter', 
                       'origlatency', 'destlatency',
                       'orig_packet_loss_pct', 'dest_packet_loss_pct']
        
        available_cols = [c for c in quality_cols if c in df.columns]
        
        if not available_cols:
            return pd.DataFrame()
        
        hourly = df.groupby('hour')[available_cols].mean().reset_index()
        hourly = hourly.round(3)
        hourly['hour_label'] = hourly['hour'].apply(lambda h: f"{h:02d}:00")
        
        return hourly
    
    # ==================== QUALITY BY CODEC ====================
    
    def get_quality_by_codec(self) -> pd.DataFrame:
        """
        Get quality metrics grouped by codec type
        
        :return: DataFrame with quality per codec
        """
        if self.cmr is None:
            return pd.DataFrame()
        
        df = self.cmr.copy()
        
        # Check for codec columns
        codec_col = None
        for col in ['origCodec', 'orig_VoRxCodec', 'payloadType']:
            if col in df.columns:
                codec_col = col
                break
        
        if codec_col is None:
            return pd.DataFrame()
        
        # Map codec numbers to names
        df['codec_name'] = df[codec_col].map(self.settings.codec_names).fillna('Unknown')
        
        # Aggregate quality by codec
        quality_cols = ['origjitter', 'destjitter', 'origlatency', 'destlatency',
                       'orig_packet_loss_pct', 'dest_packet_loss_pct']
        available = [c for c in quality_cols if c in df.columns]
        
        if 'avg_mos' in df.columns:
            available.append('avg_mos')
        
        agg_dict = {col: 'mean' for col in available}
        agg_dict['globalCallID_callId'] = 'count'
        
        codec_quality = df.groupby('codec_name').agg(agg_dict).reset_index()
        codec_quality = codec_quality.rename(columns={'globalCallID_callId': 'call_count'})
        
        # Round values
        for col in available:
            codec_quality[col] = codec_quality[col].round(3)
        
        return codec_quality.sort_values('call_count', ascending=False)
    
    def get_codec_usage_stats(self) -> pd.DataFrame:
        """
        Get codec usage statistics
        
        :return: DataFrame with codec usage
        """
        if self.cmr is None:
            return pd.DataFrame()
        
        df = self.cmr.copy()
        
        codec_col = None
        for col in ['origCodec', 'orig_VoRxCodec']:
            if col in df.columns:
                codec_col = col
                break
        
        if codec_col is None:
            return pd.DataFrame()
        
        # Map and count
        df['codec_name'] = df[codec_col].map(self.settings.codec_names).fillna('Unknown')
        
        usage = df['codec_name'].value_counts().reset_index()
        usage.columns = ['codec', 'count']
        usage['percentage'] = (usage['count'] / usage['count'].sum() * 100).round(2)
        
        return usage
    
    # ==================== QUALITY BY ROUTE/LOCATION ====================
    
    def get_quality_by_route(self) -> pd.DataFrame:
        """
        Get quality metrics per route/trunk
        
        :return: DataFrame with quality per route
        """
        if self.merged is None:
            return pd.DataFrame()
        
        df = self.merged.copy()
        
        # Identify trunk calls
        trunk_patterns = self.settings.trunk_patterns
        
        df['route'] = df.apply(
            lambda row: row['origDeviceName'] 
            if any(p in str(row['origDeviceName']).upper() for p in trunk_patterns)
            else (row['destDeviceName'] 
                  if any(p in str(row['destDeviceName']).upper() for p in trunk_patterns)
                  else 'Internal'),
            axis=1
        )
        
        quality_cols = ['origjitter', 'destjitter', 'origlatency', 'destlatency']
        available = [c for c in quality_cols if c in df.columns]
        
        if 'avg_mos' in df.columns:
            available.append('avg_mos')
        
        if not available:
            return pd.DataFrame()
        
        agg_dict = {col: 'mean' for col in available}
        agg_dict['globalCallID_callId'] = 'count'
        agg_dict['duration'] = 'sum'
        
        route_quality = df.groupby('route').agg(agg_dict).reset_index()
        route_quality = route_quality.rename(columns={
            'globalCallID_callId': 'call_count',
            'duration': 'total_duration'
        })
        
        return route_quality.sort_values('call_count', ascending=False)
    
    def get_quality_by_location(
        self,
        location_mapping: Optional[Dict[str, List[str]]] = None
    ) -> pd.DataFrame:
        """
        Get quality metrics per site/location
        
        :param location_mapping: Dict mapping location name to list of device prefixes
        :return: DataFrame with quality per location
        """
        if self.merged is None:
            return pd.DataFrame()
        
        df = self.merged.copy()
        
        if location_mapping is None:
            # Try to infer locations from device names
            # Common pattern: SEP + first few chars indicate location
            df['location'] = df['origDeviceName'].apply(
                lambda x: str(x)[:7] if str(x).startswith('SEP') else 'Other'
            )
        else:
            def get_location(device):
                device = str(device).upper()
                for location, prefixes in location_mapping.items():
                    if any(prefix.upper() in device for prefix in prefixes):
                        return location
                return 'Unknown'
            
            df['location'] = df['origDeviceName'].apply(get_location)
        
        quality_cols = ['origjitter', 'origlatency', 'orig_packet_loss_pct']
        available = [c for c in quality_cols if c in df.columns]
        
        if 'avg_mos' in df.columns:
            available.append('avg_mos')
        
        if not available:
            return pd.DataFrame()
        
        agg_dict = {col: 'mean' for col in available}
        agg_dict['globalCallID_callId'] = 'count'
        
        location_quality = df.groupby('location').agg(agg_dict).reset_index()
        location_quality = location_quality.rename(columns={'globalCallID_callId': 'call_count'})
        
        return location_quality.sort_values('call_count', ascending=False)
    
    # ==================== QUALITY HEATMAP ====================
    
    def get_quality_heatmap(
        self,
        metric: str = 'mos'
    ) -> pd.DataFrame:
        """
        Get time-based quality heatmap data (hour x day)
        
        :param metric: 'mos', 'jitter', 'latency', 'packet_loss'
        :return: DataFrame pivot table for heatmap
        """
        if self.merged is None:
            return pd.DataFrame()
        
        df = self.merged.copy()
        
        if 'hour' not in df.columns or 'day_name' not in df.columns:
            return pd.DataFrame()
        
        # Select metric column
        metric_map = {
            'mos': 'avg_mos',
            'jitter': 'origjitter',
            'latency': 'origlatency',
            'packet_loss': 'orig_packet_loss_pct'
        }
        
        metric_col = metric_map.get(metric)
        if metric_col is None or metric_col not in df.columns:
            return pd.DataFrame()
        
        heatmap = pd.pivot_table(
            df,
            values=metric_col,
            index='hour',
            columns='day_name',
            aggfunc='mean'
        ).fillna(0)
        
        # Reorder columns
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                    'Friday', 'Saturday', 'Sunday']
        available_days = [d for d in day_order if d in heatmap.columns]
        heatmap = heatmap[available_days]
        
        return heatmap.round(3)
    
    # ==================== PACKET ANALYSIS ====================
    
    def get_packet_loss_analysis(self) -> Dict[str, Any]:
        """
        Detailed packet loss analysis
        
        :return: Dictionary with packet loss analysis
        """
        if self.cmr is None:
            return {'error': 'CMR data not loaded'}
        
        df = self.cmr.copy()
        
        total_sent = df['orignumberPacketsSent'].sum() + df['destnumberPacketsSent'].sum()
        total_lost = df['orignumberPacketsLost'].sum() + df['destnumberPacketsLost'].sum()
        
        # Calls with packet loss
        has_loss = df[
            (df['orignumberPacketsLost'] > 0) | 
            (df['destnumberPacketsLost'] > 0)
        ]
        
        # High packet loss calls
        high_loss = df[
            (df['orig_packet_loss_pct'] > 1.0) | 
            (df['dest_packet_loss_pct'] > 1.0)
        ] if 'orig_packet_loss_pct' in df.columns else pd.DataFrame()
        
        analysis = {
            'total_packets_sent': int(total_sent),
            'total_packets_lost': int(total_lost),
            'overall_loss_pct': round(total_lost / total_sent * 100, 4) if total_sent > 0 else 0,
            'calls_with_loss': len(has_loss),
            'calls_with_loss_pct': round(len(has_loss) / len(df) * 100, 2),
            'high_loss_calls': len(high_loss),
            'high_loss_calls_pct': round(len(high_loss) / len(df) * 100, 2),
            'origin': {
                'total_sent': int(df['orignumberPacketsSent'].sum()),
                'total_lost': int(df['orignumberPacketsLost'].sum()),
                'avg_lost_per_call': round(df['orignumberPacketsLost'].mean(), 2),
                'max_lost': int(df['orignumberPacketsLost'].max()),
            },
            'destination': {
                'total_sent': int(df['destnumberPacketsSent'].sum()),
                'total_lost': int(df['destnumberPacketsLost'].sum()),
                'avg_lost_per_call': round(df['destnumberPacketsLost'].mean(), 2),
                'max_lost': int(df['destnumberPacketsLost'].max()),
            },
        }
        
        if 'orig_packet_loss_pct' in df.columns:
            analysis['loss_distribution'] = {
                'no_loss (0%)': int((df['orig_packet_loss_pct'] == 0).sum()),
                'low (<0.5%)': int(((df['orig_packet_loss_pct'] > 0) & (df['orig_packet_loss_pct'] < 0.5)).sum()),
                'moderate (0.5-1%)': int(((df['orig_packet_loss_pct'] >= 0.5) & (df['orig_packet_loss_pct'] < 1)).sum()),
                'high (1-3%)': int(((df['orig_packet_loss_pct'] >= 1) & (df['orig_packet_loss_pct'] < 3)).sum()),
                'severe (>3%)': int((df['orig_packet_loss_pct'] >= 3).sum()),
            }
        
        return analysis
    
    def get_jitter_analysis(self) -> Dict[str, Any]:
        """
        Detailed jitter analysis
        
        :return: Dictionary with jitter analysis
        """
        if self.cmr is None:
            return {'error': 'CMR data not loaded'}
        
        df = self.cmr.copy()
        
        orig_jitter = df['origjitter']
        dest_jitter = df['destjitter']
        
        analysis = {
            'origin': {
                'mean': round(orig_jitter.mean(), 2),
                'median': round(orig_jitter.median(), 2),
                'std': round(orig_jitter.std(), 2),
                'max': round(orig_jitter.max(), 2),
                'p95': round(orig_jitter.quantile(0.95), 2),
                'p99': round(orig_jitter.quantile(0.99), 2),
            },
            'destination': {
                'mean': round(dest_jitter.mean(), 2),
                'median': round(dest_jitter.median(), 2),
                'std': round(dest_jitter.std(), 2),
                'max': round(dest_jitter.max(), 2),
                'p95': round(dest_jitter.quantile(0.95), 2),
                'p99': round(dest_jitter.quantile(0.99), 2),
            },
            'thresholds': {
                'good (<20ms)': int((orig_jitter < 20).sum()),
                'acceptable (20-30ms)': int(((orig_jitter >= 20) & (orig_jitter < 30)).sum()),
                'problematic (30-50ms)': int(((orig_jitter >= 30) & (orig_jitter < 50)).sum()),
                'bad (>50ms)': int((orig_jitter >= 50).sum()),
            }
        }
        
        # Top devices with high jitter
        if 'origdeviceName' in df.columns:
            high_jitter = df[df['origjitter'] > 30].groupby('origdeviceName').size()
            if not high_jitter.empty:
                analysis['high_jitter_devices'] = high_jitter.head(10).to_dict()
        
        return analysis
    
    def get_latency_analysis(self) -> Dict[str, Any]:
        """
        Detailed latency analysis
        
        :return: Dictionary with latency analysis
        """
        if self.cmr is None:
            return {'error': 'CMR data not loaded'}
        
        df = self.cmr.copy()
        
        orig_latency = df['origlatency']
        dest_latency = df['destlatency']
        
        analysis = {
            'origin': {
                'mean': round(orig_latency.mean(), 2),
                'median': round(orig_latency.median(), 2),
                'std': round(orig_latency.std(), 2),
                'max': round(orig_latency.max(), 2),
                'p95': round(orig_latency.quantile(0.95), 2),
                'p99': round(orig_latency.quantile(0.99), 2),
            },
            'destination': {
                'mean': round(dest_latency.mean(), 2),
                'median': round(dest_latency.median(), 2),
                'std': round(dest_latency.std(), 2),
                'max': round(dest_latency.max(), 2),
                'p95': round(dest_latency.quantile(0.95), 2),
                'p99': round(dest_latency.quantile(0.99), 2),
            },
            'thresholds': {
                'excellent (<100ms)': int((orig_latency < 100).sum()),
                'good (100-150ms)': int(((orig_latency >= 100) & (orig_latency < 150)).sum()),
                'acceptable (150-200ms)': int(((orig_latency >= 150) & (orig_latency < 200)).sum()),
                'problematic (200-300ms)': int(((orig_latency >= 200) & (orig_latency < 300)).sum()),
                'bad (>300ms)': int((orig_latency >= 300).sum()),
            }
        }
        
        return analysis
    
    # ==================== BANDWIDTH ANALYSIS ====================
    
    def get_bandwidth_utilization(self) -> Dict[str, Any]:
        """
        Estimate bandwidth consumption from call data
        
        :return: Dictionary with bandwidth analysis
        """
        if self.cmr is None:
            return {'error': 'CMR data not loaded'}
        
        df = self.cmr.copy()
        
        # Estimate based on packets and codec
        # Typical codec bandwidth:
        codec_bandwidth = {
            'G.711': 87.2,      # kbps (with headers)
            'G.711 A-law': 87.2,
            'G.711 μ-law': 87.2,
            'G.729': 31.2,
            'G.729a': 31.2,
            'G.722': 87.2,
            'iLBC': 29.2,
            'OPUS': 50.0,       # Variable, estimate
        }
        
        total_packets = df['orignumberPacketsSent'].sum() + df['destnumberPacketsSent'].sum()
        total_octets = 0
        
        if 'orignumberOctetsReceived' in df.columns:
            total_octets = (
                df['orignumberOctetsReceived'].sum() + 
                df['destnumberOctetsReceived'].sum()
            )
        
        # Estimate total bandwidth in MB
        total_bytes = total_octets if total_octets > 0 else total_packets * 160  # Assume 160 bytes avg
        total_mb = total_bytes / (1024 * 1024)
        
        # Get average call duration for bandwidth per hour estimate
        if self.cdr is not None:
            total_duration_hours = self.cdr['duration'].sum() / 3600
            avg_bandwidth_mbph = total_mb / total_duration_hours if total_duration_hours > 0 else 0
        else:
            avg_bandwidth_mbph = 0
        
        return {
            'total_packets': int(total_packets),
            'total_data_mb': round(total_mb, 2),
            'total_data_gb': round(total_mb / 1024, 3),
            'avg_bandwidth_mbph': round(avg_bandwidth_mbph, 2),
            'estimated_peak_bandwidth_kbps': round(avg_bandwidth_mbph * 1024 / 3600 * 2, 2),  # Rough peak estimate
        }
    
    # ==================== NETWORK ISSUES ====================
    
    def identify_network_issues(self) -> pd.DataFrame:
        """
        Correlate quality issues with potential network problems
        
        :return: DataFrame with identified issues
        """
        if self.cmr is None:
            return pd.DataFrame()
        
        df = self.cmr.copy()
        
        issues = []
        
        # High jitter periods
        if 'dateTimeOrigination_dt' in self.merged.columns if self.merged is not None else False:
            merged = self.merged.copy()
            merged['hour'] = merged['dateTimeOrigination_dt'].dt.hour
            
            hourly_jitter = merged.groupby('hour')['origjitter'].mean()
            high_jitter_hours = hourly_jitter[hourly_jitter > 30].index.tolist()
            
            if high_jitter_hours:
                issues.append({
                    'issue_type': 'High Jitter Periods',
                    'description': f"High jitter detected during hours: {high_jitter_hours}",
                    'severity': 'warning',
                    'affected_hours': str(high_jitter_hours),
                    'recommendation': 'Check network congestion during these hours',
                })
        
        # High packet loss
        if 'orig_packet_loss_pct' in df.columns:
            high_loss_pct = (df['orig_packet_loss_pct'] > 1).mean() * 100
            if high_loss_pct > 5:
                issues.append({
                    'issue_type': 'Packet Loss',
                    'description': f"{high_loss_pct:.1f}% of calls have >1% packet loss",
                    'severity': 'critical' if high_loss_pct > 10 else 'warning',
                    'affected_calls_pct': round(high_loss_pct, 2),
                    'recommendation': 'Check for network congestion, QoS settings, or faulty equipment',
                })
        
        # High latency
        high_latency_pct = (df['origlatency'] > 150).mean() * 100
        if high_latency_pct > 5:
            issues.append({
                'issue_type': 'High Latency',
                'description': f"{high_latency_pct:.1f}% of calls have >150ms latency",
                'severity': 'warning',
                'affected_calls_pct': round(high_latency_pct, 2),
                'recommendation': 'Review network routing and WAN links',
            })
        
        # Device-specific issues
        device_jitter = df.groupby('origdeviceName')['origjitter'].mean()
        problem_devices = device_jitter[device_jitter > 40].head(5)
        
        if not problem_devices.empty:
            issues.append({
                'issue_type': 'Device Quality Issues',
                'description': f"{len(problem_devices)} devices show consistently high jitter",
                'severity': 'warning',
                'affected_devices': problem_devices.index.tolist(),
                'recommendation': 'Check network connectivity and device firmware for listed devices',
            })
        
        return pd.DataFrame(issues)
    
    # ==================== SLA COMPLIANCE ====================
    
    def get_quality_sla_compliance(
        self,
        sla_thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Check quality metrics against SLA thresholds
        
        :param sla_thresholds: Dictionary with SLA thresholds
        :return: Dictionary with SLA compliance report
        """
        if self.cmr is None:
            return {'error': 'CMR data not loaded'}
        
        df = self.cmr.copy()
        
        # Default SLA thresholds
        if sla_thresholds is None:
            sla_thresholds = {
                'max_jitter_ms': 30,
                'max_latency_ms': 150,
                'max_packet_loss_pct': 1.0,
                'min_mos': 3.5,
                'target_answer_rate_pct': 95,
            }
        
        total_calls = len(df)
        
        compliance = {
            'sla_thresholds': sla_thresholds,
            'total_calls_analyzed': total_calls,
            'metrics': {},
            'overall_compliance': True,
        }
        
        # Jitter compliance
        jitter_compliant = (
            (df['origjitter'] <= sla_thresholds['max_jitter_ms']) &
            (df['destjitter'] <= sla_thresholds['max_jitter_ms'])
        ).sum()
        compliance['metrics']['jitter'] = {
            'compliant_calls': int(jitter_compliant),
            'compliance_pct': round(jitter_compliant / total_calls * 100, 2),
            'threshold': f"≤{sla_thresholds['max_jitter_ms']}ms",
            'status': 'pass' if jitter_compliant / total_calls >= 0.95 else 'fail',
        }
        
        # Latency compliance
        latency_compliant = (
            (df['origlatency'] <= sla_thresholds['max_latency_ms']) &
            (df['destlatency'] <= sla_thresholds['max_latency_ms'])
        ).sum()
        compliance['metrics']['latency'] = {
            'compliant_calls': int(latency_compliant),
            'compliance_pct': round(latency_compliant / total_calls * 100, 2),
            'threshold': f"≤{sla_thresholds['max_latency_ms']}ms",
            'status': 'pass' if latency_compliant / total_calls >= 0.95 else 'fail',
        }
        
        # Packet loss compliance
        if 'orig_packet_loss_pct' in df.columns:
            pl_compliant = (
                (df['orig_packet_loss_pct'] <= sla_thresholds['max_packet_loss_pct']) &
                (df['dest_packet_loss_pct'] <= sla_thresholds['max_packet_loss_pct'])
            ).sum()
            compliance['metrics']['packet_loss'] = {
                'compliant_calls': int(pl_compliant),
                'compliance_pct': round(pl_compliant / total_calls * 100, 2),
                'threshold': f"≤{sla_thresholds['max_packet_loss_pct']}%",
                'status': 'pass' if pl_compliant / total_calls >= 0.95 else 'fail',
            }
        
        # MOS compliance
        if 'avg_mos' in df.columns:
            mos_compliant = (df['avg_mos'] >= sla_thresholds['min_mos']).sum()
            compliance['metrics']['mos'] = {
                'compliant_calls': int(mos_compliant),
                'compliance_pct': round(mos_compliant / total_calls * 100, 2),
                'threshold': f"≥{sla_thresholds['min_mos']}",
                'average_mos': round(df['avg_mos'].mean(), 2),
                'status': 'pass' if mos_compliant / total_calls >= 0.95 else 'fail',
            }
        
        # Overall compliance
        compliance['overall_compliance'] = all(
            m['status'] == 'pass' for m in compliance['metrics'].values()
        )
        
        compliance['summary'] = {
            'passing_metrics': sum(1 for m in compliance['metrics'].values() if m['status'] == 'pass'),
            'total_metrics': len(compliance['metrics']),
            'status': 'COMPLIANT' if compliance['overall_compliance'] else 'NON-COMPLIANT',
        }
        
        return compliance
    
    # ==================== QUALITY ISSUES ====================
    
    def get_quality_issues(
        self,
        jitter_threshold: int = 30,
        latency_threshold: int = 150,
        packet_loss_threshold: float = 1.0
    ) -> pd.DataFrame:
        """
        Get calls with quality issues based on thresholds
        
        :param jitter_threshold: Maximum acceptable jitter (ms)
        :param latency_threshold: Maximum acceptable latency (ms)
        :param packet_loss_threshold: Maximum acceptable packet loss (%)
        :return: DataFrame with problematic calls
        """
        if self.cmr is None:
            return pd.DataFrame()
        
        df = self.cmr.copy()
        
        # Build quality mask
        quality_mask = (
            (df['origjitter'] > jitter_threshold) |
            (df['destjitter'] > jitter_threshold) |
            (df['origlatency'] > latency_threshold) |
            (df['destlatency'] > latency_threshold)
        )
        
        if 'orig_packet_loss_pct' in df.columns:
            quality_mask = quality_mask | (
                (df['orig_packet_loss_pct'] > packet_loss_threshold) |
                (df['dest_packet_loss_pct'] > packet_loss_threshold)
            )
        
        issues = df[quality_mask].copy()
        
        # Add issue type column
        def get_issue_types(row):
            types = []
            if row['origjitter'] > jitter_threshold or row['destjitter'] > jitter_threshold:
                types.append('jitter')
            if row['origlatency'] > latency_threshold or row['destlatency'] > latency_threshold:
                types.append('latency')
            if 'orig_packet_loss_pct' in row and (
                row['orig_packet_loss_pct'] > packet_loss_threshold or 
                row['dest_packet_loss_pct'] > packet_loss_threshold
            ):
                types.append('packet_loss')
            return ', '.join(types)
        
        issues['issue_types'] = issues.apply(get_issue_types, axis=1)
        
        return issues
    
    def get_worst_quality_calls(
        self,
        n: int = 20,
        metric: str = 'mos'
    ) -> pd.DataFrame:
        """
        Get the N worst quality calls
        
        :param n: Number of calls to return
        :param metric: Metric to rank by ('mos', 'jitter', 'latency', 'packet_loss')
        :return: DataFrame with worst calls
        """
        if self.merged is None:
            if self.cmr is None:
                return pd.DataFrame()
            df = self.cmr.copy()
        else:
            df = self.merged.copy()
        
        sort_cols = {
            'mos': ('avg_mos', True),           # Ascending (lower is worse)
            'jitter': ('origjitter', False),     # Descending (higher is worse)
            'latency': ('origlatency', False),   # Descending
            'packet_loss': ('orig_packet_loss_pct', False),  # Descending
        }
        
        col, ascending = sort_cols.get(metric, ('avg_mos', True))
        
        if col not in df.columns:
            return pd.DataFrame()
        
        # Sort and get worst N
        worst = df.nlargest(n, col) if not ascending else df.nsmallest(n, col)
        
        return worst