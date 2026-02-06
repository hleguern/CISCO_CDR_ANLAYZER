"""
Hunt group and queue analysis for CDR data
Includes hunt group performance, member statistics, overflow analysis, and IVR flow
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import logging

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class HuntGroupAnalyzer(BaseAnalyzer):
    """Hunt group and call queue analysis"""
    
    # ==================== HUNT GROUP IDENTIFICATION ====================
    
    def get_all_hunt_groups(self) -> List[str]:
        """
        Get all unique hunt group pilot numbers
        
        :return: List of hunt pilot DNs
        """
        if not self._check_cdr_loaded():
            return []
        
        if 'huntPilotDN' not in self.cdr.columns:
            return []
        
        hunt_dns = self.cdr['huntPilotDN'].dropna().unique()
        hunt_dns = [dn for dn in hunt_dns if dn and dn not in ['', 'nan', '\\']]
        
        return sorted(hunt_dns)
    
    def get_hunt_group_calls(
        self, 
        hunt_dn: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get all calls that went through hunt groups
        
        :param hunt_dn: Optional specific hunt pilot DN
        :return: DataFrame with hunt group calls
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        if 'huntPilotDN' not in df.columns:
            return pd.DataFrame()
        
        # Filter hunt group calls
        if hunt_dn:
            hunt_calls = df[df['huntPilotDN'] == hunt_dn]
        else:
            hunt_calls = df[df['huntPilotDN'].notna() & (df['huntPilotDN'] != '')]
        
        return hunt_calls
    
    # ==================== HUNT GROUP STATISTICS ====================
    
    def get_hunt_group_stats(
        self, 
        hunt_dn: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a hunt group
        
        :param hunt_dn: Hunt pilot DN
        :return: Dictionary with hunt group statistics
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty:
            return {'hunt_dn': hunt_dn, 'error': 'No calls found for this hunt group'}
        
        answered = calls[calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        
        stats = {
            'hunt_dn': hunt_dn,
            'total_calls': len(calls),
            'answered_calls': len(answered),
            'abandoned_calls': len(calls) - len(answered),
            'answer_rate': round(len(answered) / len(calls) * 100, 2) if len(calls) > 0 else 0,
            'abandonment_rate': round((len(calls) - len(answered)) / len(calls) * 100, 2) if len(calls) > 0 else 0,
            'total_duration_sec': int(calls['duration'].sum()),
            'avg_duration_sec': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
            'max_duration_sec': int(calls['duration'].max()) if len(calls) > 0 else 0,
        }
        
        # Wait time analysis
        if 'totalWaitTimeInQueue' in calls.columns:
            wait_times = calls['totalWaitTimeInQueue'].dropna()
            if len(wait_times) > 0:
                stats['wait_time'] = {
                    'avg_sec': round(wait_times.mean(), 1),
                    'max_sec': int(wait_times.max()),
                    'median_sec': round(wait_times.median(), 1),
                    'p90_sec': round(wait_times.quantile(0.90), 1),
                    'p95_sec': round(wait_times.quantile(0.95), 1),
                }
        
        # Ring time analysis
        if 'ring_time' in calls.columns:
            ring_times = calls['ring_time'].dropna()
            if len(ring_times) > 0:
                stats['ring_time'] = {
                    'avg_sec': round(ring_times.mean(), 1),
                    'max_sec': int(ring_times.max()),
                }
        
        # Time distribution
        if 'hour' in calls.columns:
            stats['hourly_distribution'] = calls['hour'].value_counts().sort_index().to_dict()
            stats['peak_hour'] = int(calls['hour'].mode().iloc[0]) if not calls['hour'].mode().empty else None
        
        if 'day_name' in calls.columns:
            stats['daily_distribution'] = calls['day_name'].value_counts().to_dict()
        
        # Member devices that answered
        if 'destDeviceName' in calls.columns and not answered.empty:
            stats['answering_devices'] = answered['destDeviceName'].value_counts().to_dict()
            stats['unique_members'] = answered['destDeviceName'].nunique()
        
        # Date range
        if 'dateTimeOrigination_dt' in calls.columns:
            stats['first_call'] = calls['dateTimeOrigination_dt'].min().isoformat()
            stats['last_call'] = calls['dateTimeOrigination_dt'].max().isoformat()
            if 'date' in calls.columns:
                stats['active_days'] = calls['date'].nunique()
                stats['avg_calls_per_day'] = round(len(calls) / calls['date'].nunique(), 1)
        
        return stats
    
    def get_hunt_group_summary(self) -> pd.DataFrame:
        """
        Get summary statistics for all hunt groups
        
        :return: DataFrame with summary for all hunt groups
        """
        hunt_groups = self.get_all_hunt_groups()
        
        if not hunt_groups:
            return pd.DataFrame()
        
        summaries = []
        
        for hunt_dn in hunt_groups:
            stats = self.get_hunt_group_stats(hunt_dn)
            
            if 'error' in stats:
                continue
            
            summaries.append({
                'hunt_dn': hunt_dn,
                'total_calls': stats['total_calls'],
                'answered_calls': stats['answered_calls'],
                'abandoned_calls': stats['abandoned_calls'],
                'answer_rate': stats['answer_rate'],
                'abandonment_rate': stats['abandonment_rate'],
                'avg_duration_sec': stats['avg_duration_sec'],
                'avg_wait_sec': stats.get('wait_time', {}).get('avg_sec', 0),
                'unique_members': stats.get('unique_members', 0),
                'avg_calls_per_day': stats.get('avg_calls_per_day', 0),
            })
        
        return pd.DataFrame(summaries).sort_values('total_calls', ascending=False)
    
    # ==================== MEMBER STATISTICS ====================
    
    def get_hunt_group_member_stats(
        self, 
        hunt_dn: str
    ) -> pd.DataFrame:
        """
        Get per-member statistics for a hunt group
        
        :param hunt_dn: Hunt pilot DN
        :return: DataFrame with member statistics
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty:
            return pd.DataFrame()
        
        answered = calls[calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        
        if answered.empty:
            return pd.DataFrame()
        
        # Group by destination device/number
        member_stats = answered.groupby('destDeviceName').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean', 'max'],
            'finalCalledPartyNumber': 'first',
        }).reset_index()
        
        member_stats.columns = ['device', 'calls_handled', 'total_duration',
                               'avg_duration', 'max_duration', 'extension']
        
        # Calculate percentage of total handled
        total_handled = member_stats['calls_handled'].sum()
        member_stats['handle_pct'] = (
            member_stats['calls_handled'] / total_handled * 100
        ).round(2) if total_handled > 0 else 0
        
        # Add ring-to-answer time if available
        if 'ring_time' in answered.columns:
            ring_stats = answered.groupby('destDeviceName')['ring_time'].mean().reset_index()
            ring_stats.columns = ['device', 'avg_ring_time']
            member_stats = pd.merge(member_stats, ring_stats, on='device', how='left')
        
        return member_stats.sort_values('calls_handled', ascending=False)
    
    def get_member_performance_comparison(
        self, 
        hunt_dn: str
    ) -> Dict[str, Any]:
        """
        Compare performance across hunt group members
        
        :param hunt_dn: Hunt pilot DN
        :return: Dictionary with comparison data
        """
        member_stats = self.get_hunt_group_member_stats(hunt_dn)
        
        if member_stats.empty:
            return {'hunt_dn': hunt_dn, 'error': 'No member data available'}
        
        return {
            'hunt_dn': hunt_dn,
            'total_members': len(member_stats),
            'top_performer': {
                'device': member_stats.iloc[0]['device'],
                'calls_handled': int(member_stats.iloc[0]['calls_handled']),
                'handle_pct': member_stats.iloc[0]['handle_pct'],
            },
            'workload_distribution': {
                'mean_calls': round(member_stats['calls_handled'].mean(), 1),
                'std_dev': round(member_stats['calls_handled'].std(), 1),
                'min_calls': int(member_stats['calls_handled'].min()),
                'max_calls': int(member_stats['calls_handled'].max()),
                'cv': round(member_stats['calls_handled'].std() / member_stats['calls_handled'].mean() * 100, 1)
                       if member_stats['calls_handled'].mean() > 0 else 0,
            },
            'duration_stats': {
                'member_with_longest_avg': member_stats.loc[member_stats['avg_duration'].idxmax(), 'device'],
                'longest_avg_duration': round(member_stats['avg_duration'].max(), 1),
                'member_with_shortest_avg': member_stats.loc[member_stats['avg_duration'].idxmin(), 'device'],
                'shortest_avg_duration': round(member_stats['avg_duration'].min(), 1),
            },
            'members': member_stats.to_dict('records'),
        }
    
    # ==================== OVERFLOW ANALYSIS ====================
    
    def get_hunt_overflow_analysis(
        self, 
        hunt_dn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze hunt group overflow occurrences
        
        :param hunt_dn: Optional hunt pilot DN
        :return: Dictionary with overflow analysis
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty:
            return {'error': 'No hunt group calls found'}
        
        # Identify potential overflow situations
        answered = calls[calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        
        analysis = {
            'total_hunt_calls': len(calls),
            'answered': len(answered),
            'unanswered': len(calls) - len(answered),
        }
        
        # Check for redirects (potential overflow to voicemail or other destination)
        if 'lastRedirectDn' in calls.columns:
            redirected = calls[calls['lastRedirectDn'].notna() & (calls['lastRedirectDn'] != '')]
            analysis['redirected_calls'] = len(redirected)
            analysis['redirect_destinations'] = redirected['lastRedirectDn'].value_counts().head(10).to_dict()
        
        # Long wait time analysis
        if 'totalWaitTimeInQueue' in calls.columns:
            long_wait = calls[calls['totalWaitTimeInQueue'] > 60]  # > 60 seconds
            analysis['long_wait_calls'] = len(long_wait)
            analysis['long_wait_pct'] = round(len(long_wait) / len(calls) * 100, 2) if len(calls) > 0 else 0
            
            # Very long waits might indicate overflow
            very_long_wait = calls[calls['totalWaitTimeInQueue'] > 120]
            analysis['very_long_wait_calls'] = len(very_long_wait)
        
        # Abandoned call analysis
        abandoned = calls[~calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        if not abandoned.empty:
            analysis['abandoned_analysis'] = {
                'total_abandoned': len(abandoned),
                'abandonment_rate': round(len(abandoned) / len(calls) * 100, 2) if len(calls) > 0 else 0,
                'by_hour': abandoned['hour'].value_counts().sort_index().to_dict() if 'hour' in abandoned.columns else {},
                'by_day': abandoned['day_name'].value_counts().to_dict() if 'day_name' in abandoned.columns else {},
            }
            
            if 'totalWaitTimeInQueue' in abandoned.columns:
                analysis['abandoned_analysis']['avg_wait_before_abandon'] = round(
                    abandoned['totalWaitTimeInQueue'].mean(), 1
                )
        
        return analysis
    
    # ==================== QUEUE ANALYSIS ====================
    
    def get_queue_wait_times(
        self, 
        hunt_dn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze queue wait times
        
        :param hunt_dn: Optional hunt pilot DN
        :return: Dictionary with wait time analysis
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty or 'totalWaitTimeInQueue' not in calls.columns:
            return {'error': 'No wait time data available'}
        
        wait_times = calls['totalWaitTimeInQueue'].dropna()
        
        if wait_times.empty:
            return {'error': 'No wait time data available'}
        
        answered = calls[calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        answered_waits = answered['totalWaitTimeInQueue'].dropna() if not answered.empty and 'totalWaitTimeInQueue' in answered.columns else pd.Series(dtype=float)
        
        abandoned = calls[~calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        abandoned_waits = abandoned['totalWaitTimeInQueue'].dropna() if not abandoned.empty and 'totalWaitTimeInQueue' in abandoned.columns else pd.Series(dtype=float)
        
        analysis = {
            'total_calls': len(calls),
            'overall': {
                'mean': round(wait_times.mean(), 1),
                'median': round(wait_times.median(), 1),
                'std': round(wait_times.std(), 1),
                'min': int(wait_times.min()),
                'max': int(wait_times.max()),
                'p75': round(wait_times.quantile(0.75), 1),
                'p90': round(wait_times.quantile(0.90), 1),
                'p95': round(wait_times.quantile(0.95), 1),
            },
            'answered_calls': {
                'count': len(answered_waits),
                'mean': round(answered_waits.mean(), 1) if len(answered_waits) > 0 else 0,
                'median': round(answered_waits.median(), 1) if len(answered_waits) > 0 else 0,
            },
            'abandoned_calls': {
                'count': len(abandoned_waits),
                'mean': round(abandoned_waits.mean(), 1) if len(abandoned_waits) > 0 else 0,
                'median': round(abandoned_waits.median(), 1) if len(abandoned_waits) > 0 else 0,
            },
            'distribution': {
                '0-15 sec': int((wait_times <= 15).sum()),
                '15-30 sec': int(((wait_times > 15) & (wait_times <= 30)).sum()),
                '30-60 sec': int(((wait_times > 30) & (wait_times <= 60)).sum()),
                '1-2 min': int(((wait_times > 60) & (wait_times <= 120)).sum()),
                '2-5 min': int(((wait_times > 120) & (wait_times <= 300)).sum()),
                '>5 min': int((wait_times > 300).sum()),
            },
        }
        
        # Service level calculations
        if len(answered_waits) > 0:
            for threshold in [15, 20, 30, 60]:
                calls_within = (answered_waits <= threshold).sum()
                analysis[f'service_level_{threshold}s'] = round(
                    calls_within / len(answered_waits) * 100, 2
                )
        else:
            for threshold in [15, 20, 30, 60]:
                analysis[f'service_level_{threshold}s'] = 0
        
        # Wait time by hour
        if 'hour' in calls.columns:
            hourly_wait = calls.groupby('hour')['totalWaitTimeInQueue'].mean()
            analysis['wait_by_hour'] = hourly_wait.round(1).to_dict()
            analysis['worst_hour'] = int(hourly_wait.idxmax())
            analysis['best_hour'] = int(hourly_wait.idxmin())
        
        return analysis
    
    def get_service_level_trend(
        self,
        hunt_dn: Optional[str] = None,
        threshold_seconds: int = 20,
        period: str = 'daily'
    ) -> pd.DataFrame:
        """
        Get service level trend over time
        
        :param hunt_dn: Optional hunt pilot DN
        :param threshold_seconds: Service level threshold
        :param period: 'daily', 'weekly', or 'monthly'
        :return: DataFrame with service level trend
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty or 'totalWaitTimeInQueue' not in calls.columns:
            return pd.DataFrame()
        
        answered = calls[calls['answered']].copy() if 'answered' in calls.columns else pd.DataFrame()
        
        if answered.empty:
            return pd.DataFrame()
        
        # Determine grouping column
        if period == 'daily':
            if 'date' not in answered.columns:
                answered['date'] = answered['dateTimeOrigination_dt'].dt.date
            group_col = 'date'
        elif period == 'weekly':
            answered['period'] = answered['dateTimeOrigination_dt'].dt.to_period('W').astype(str)
            group_col = 'period'
        else:  # monthly
            answered['period'] = answered['dateTimeOrigination_dt'].dt.to_period('M').astype(str)
            group_col = 'period'
        
        # Calculate service level per period using agg instead of apply
        # This avoids the FutureWarning about grouping columns
        trend_data = []
        
        for group_key, group_df in answered.groupby(group_col):
            total_answered = len(group_df)
            within_threshold = (group_df['totalWaitTimeInQueue'] <= threshold_seconds).sum()
            service_level = (within_threshold / total_answered * 100) if total_answered > 0 else 0
            avg_wait_time = group_df['totalWaitTimeInQueue'].mean()
            
            trend_data.append({
                group_col: group_key,
                'total_answered': total_answered,
                'within_threshold': within_threshold,
                'service_level': round(service_level, 2),
                'avg_wait_time': round(avg_wait_time, 1),
            })
        
        trend = pd.DataFrame(trend_data)
        
        if not trend.empty:
            trend = trend.sort_values(group_col)
        
        return trend
    
    # ==================== ABANDONED CALLS ====================
    
    def get_abandoned_calls_analysis(
        self, 
        hunt_dn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Detailed analysis of abandoned calls
        
        :param hunt_dn: Optional hunt pilot DN
        :return: Dictionary with abandoned call analysis
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty:
            return {'error': 'No hunt group calls found'}
        
        abandoned = calls[~calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        
        if abandoned.empty:
            return {
                'total_calls': len(calls),
                'abandoned_calls': 0,
                'abandonment_rate': 0,
                'message': 'No abandoned calls'
            }
        
        analysis = {
            'total_calls': len(calls),
            'abandoned_calls': len(abandoned),
            'abandonment_rate': round(len(abandoned) / len(calls) * 100, 2) if len(calls) > 0 else 0,
        }
        
        # Caller analysis
        analysis['repeat_abandoners'] = abandoned['callingPartyNumber'].value_counts().head(10).to_dict()
        analysis['unique_abandoners'] = abandoned['callingPartyNumber'].nunique()
        
        # Time-based patterns
        if 'hour' in abandoned.columns:
            analysis['by_hour'] = abandoned['hour'].value_counts().sort_index().to_dict()
            if not abandoned['hour'].mode().empty:
                analysis['peak_abandon_hour'] = int(abandoned['hour'].mode().iloc[0])
        
        if 'day_name' in abandoned.columns:
            analysis['by_day'] = abandoned['day_name'].value_counts().to_dict()
        
        # Wait time before abandonment
        if 'totalWaitTimeInQueue' in abandoned.columns:
            wait_times = abandoned['totalWaitTimeInQueue'].dropna()
            if len(wait_times) > 0:
                analysis['wait_before_abandon'] = {
                    'mean': round(wait_times.mean(), 1),
                    'median': round(wait_times.median(), 1),
                    'min': int(wait_times.min()),
                    'max': int(wait_times.max()),
                    'distribution': {
                        '<10 sec': int((wait_times < 10).sum()),
                        '10-30 sec': int(((wait_times >= 10) & (wait_times < 30)).sum()),
                        '30-60 sec': int(((wait_times >= 30) & (wait_times < 60)).sum()),
                        '1-2 min': int(((wait_times >= 60) & (wait_times < 120)).sum()),
                        '>2 min': int((wait_times >= 120).sum()),
                    }
                }
                
                # Short abandons might be wrong numbers
                analysis['short_abandons'] = int((wait_times < 5).sum())
                analysis['short_abandon_pct'] = round(
                    (wait_times < 5).sum() / len(abandoned) * 100, 2
                )
        
        # Business hours vs after hours
        if 'is_business_hours' in abandoned.columns:
            analysis['business_hours_abandons'] = int(abandoned['is_business_hours'].sum())
            analysis['after_hours_abandons'] = int((~abandoned['is_business_hours']).sum())
        
        return analysis
    
    def get_abandoned_calls_trend(
        self,
        hunt_dn: Optional[str] = None,
        period: str = 'daily'
    ) -> pd.DataFrame:
        """
        Get abandoned calls trend over time
        
        :param hunt_dn: Optional hunt pilot DN
        :param period: 'daily', 'weekly', or 'monthly'
        :return: DataFrame with abandonment trend
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty:
            return pd.DataFrame()
        
        calls = calls.copy()
        
        if period == 'daily':
            if 'date' not in calls.columns:
                calls['date'] = calls['dateTimeOrigination_dt'].dt.date
            group_col = 'date'
        elif period == 'weekly':
            calls['period'] = calls['dateTimeOrigination_dt'].dt.to_period('W').astype(str)
            group_col = 'period'
        else:
            calls['period'] = calls['dateTimeOrigination_dt'].dt.to_period('M').astype(str)
            group_col = 'period'
        
        trend = calls.groupby(group_col).agg({
            'globalCallID_callId': 'count',
            'answered': 'sum',
        }).reset_index()
        
        trend.columns = [group_col, 'total_calls', 'answered_calls']
        trend['abandoned_calls'] = trend['total_calls'] - trend['answered_calls']
        trend['abandonment_rate'] = (
            trend['abandoned_calls'] / trend['total_calls'] * 100
        ).round(2)
        
        return trend.sort_values(group_col)
    
    # ==================== FIRST CALL RESOLUTION ====================
    
    def get_first_call_resolution(
        self,
        hunt_dn: Optional[str] = None,
        callback_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Estimate First Call Resolution (FCR) based on callback patterns
        
        :param hunt_dn: Optional hunt pilot DN
        :param callback_window_minutes: Time window to check for callbacks
        :return: Dictionary with FCR metrics
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty:
            return {'error': 'No hunt group calls found'}
        
        answered = calls[calls['answered']].copy() if 'answered' in calls.columns else pd.DataFrame()
        
        if answered.empty:
            return {'error': 'No answered calls to analyze'}
        
        answered = answered.sort_values('dateTimeOrigination_dt')
        
        # Find callers who called back within the window
        callbacks = 0
        total_analyzed = 0
        
        callback_window = timedelta(minutes=callback_window_minutes)
        
        # Group by caller
        caller_calls = answered.groupby('callingPartyNumber')
        
        for caller, group in caller_calls:
            if len(group) < 2:
                total_analyzed += 1
                continue
            
            group = group.sort_values('dateTimeOrigination_dt')
            times = group['dateTimeOrigination_dt'].tolist()
            
            for i in range(len(times) - 1):
                total_analyzed += 1
                if times[i + 1] - times[i] <= callback_window:
                    callbacks += 1
        
        # If last call in each group, assume resolved
        if total_analyzed == 0:
            total_analyzed = len(answered)
        
        fcr_rate = (1 - callbacks / total_analyzed) * 100 if total_analyzed > 0 else 0
        
        return {
            'total_answered_calls': len(answered),
            'calls_analyzed': total_analyzed,
            'estimated_callbacks': callbacks,
            'estimated_fcr_rate': round(fcr_rate, 2),
            'callback_window_minutes': callback_window_minutes,
            'note': 'FCR is estimated based on same-caller calls within the callback window',
        }
    
    # ==================== IVR ANALYSIS ====================
    
    def get_ivr_call_flow_analysis(
        self,
        ivr_device_pattern: str = 'CTI',
        max_chain_length: int = 10
    ) -> Dict[str, Any]:
        """
        Analyze IVR menu usage and call flow patterns
        
        :param ivr_device_pattern: Device pattern to identify IVR
        :param max_chain_length: Maximum chain length to track
        :return: Dictionary with IVR analysis
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        # Identify IVR-involved calls
        ivr_orig_mask = df['origDeviceName'].str.contains(ivr_device_pattern, case=False, na=False)
        ivr_dest_mask = df['destDeviceName'].str.contains(ivr_device_pattern, case=False, na=False)
        
        ivr_calls = df[ivr_orig_mask | ivr_dest_mask]
        
        if ivr_calls.empty:
            return {
                'ivr_device_pattern': ivr_device_pattern,
                'ivr_calls_found': 0,
                'message': 'No IVR calls found with the specified pattern'
            }
        
        # Collect IVR devices
        ivr_devices = set()
        if ivr_orig_mask.any():
            ivr_devices.update(df.loc[ivr_orig_mask, 'origDeviceName'].unique())
        if ivr_dest_mask.any():
            ivr_devices.update(df.loc[ivr_dest_mask, 'destDeviceName'].unique())
        
        analysis = {
            'ivr_device_pattern': ivr_device_pattern,
            'total_ivr_calls': len(ivr_calls),
            'ivr_devices': list(ivr_devices),
        }
        
        # Analyze exit points (where calls go after IVR)
        ivr_exits = ivr_calls[
            ivr_orig_mask.loc[ivr_calls.index] & 
            ~ivr_dest_mask.loc[ivr_calls.index]
        ]
        
        if not ivr_exits.empty:
            analysis['exit_destinations'] = ivr_exits['destDeviceName'].value_counts().head(10).to_dict()
            analysis['exit_numbers'] = ivr_exits['finalCalledPartyNumber'].value_counts().head(10).to_dict()
        
        # Duration in IVR (calls where both endpoints are IVR)
        ivr_only = ivr_calls[
            ivr_orig_mask.loc[ivr_calls.index] & 
            ivr_dest_mask.loc[ivr_calls.index]
        ]
        
        if not ivr_only.empty:
            analysis['ivr_only_calls'] = len(ivr_only)
            analysis['avg_ivr_duration'] = round(ivr_only['duration'].mean(), 1)
        
        # Time distribution
        if 'hour' in ivr_calls.columns:
            analysis['by_hour'] = ivr_calls['hour'].value_counts().sort_index().to_dict()
        
        return analysis
    
    # ==================== HUNT GROUP PERFORMANCE METRICS ====================
    
    def get_hunt_group_kpis(
        self,
        hunt_dn: str,
        service_level_threshold: int = 20
    ) -> Dict[str, Any]:
        """
        Get key performance indicators for a hunt group
        
        :param hunt_dn: Hunt pilot DN
        :param service_level_threshold: Seconds for service level calculation
        :return: Dictionary with KPIs
        """
        calls = self.get_hunt_group_calls(hunt_dn)
        
        if calls.empty:
            return {'error': 'No calls found'}
        
        answered = calls[calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        abandoned = calls[~calls['answered']] if 'answered' in calls.columns else pd.DataFrame()
        
        kpis = {
            'hunt_dn': hunt_dn,
            'period': {
                'start': calls['dateTimeOrigination_dt'].min().isoformat(),
                'end': calls['dateTimeOrigination_dt'].max().isoformat(),
            },
            'volume': {
                'total_calls': len(calls),
                'answered': len(answered),
                'abandoned': len(abandoned),
                'avg_calls_per_day': round(len(calls) / calls['date'].nunique(), 1) if 'date' in calls.columns and calls['date'].nunique() > 0 else len(calls),
            },
            'answer_rate': round(len(answered) / len(calls) * 100, 2) if len(calls) > 0 else 0,
            'abandonment_rate': round(len(abandoned) / len(calls) * 100, 2) if len(calls) > 0 else 0,
        }
        
        # Average Speed of Answer (ASA)
        if 'totalWaitTimeInQueue' in answered.columns and len(answered) > 0:
            kpis['asa_seconds'] = round(answered['totalWaitTimeInQueue'].mean(), 1)
        else:
            kpis['asa_seconds'] = None
        
        # Service Level
        if 'totalWaitTimeInQueue' in answered.columns and len(answered) > 0:
            within_sl = (answered['totalWaitTimeInQueue'] <= service_level_threshold).sum()
            kpis['service_level'] = {
                'threshold_seconds': service_level_threshold,
                'calls_within_threshold': int(within_sl),
                'service_level_pct': round(within_sl / len(answered) * 100, 2),
            }
        
        # Average Handle Time (AHT)
        if len(answered) > 0:
            kpis['aht_seconds'] = round(answered['duration'].mean(), 1)
        else:
            kpis['aht_seconds'] = None
        
        # Longest Wait Time
        if 'totalWaitTimeInQueue' in calls.columns:
            kpis['longest_wait_seconds'] = int(calls['totalWaitTimeInQueue'].max())
        
        return kpis