"""
Security analysis and fraud detection for CDR data
Includes toll fraud detection, after-hours anomalies, and compliance reporting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import logging
import re

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class SecurityAnalyzer(BaseAnalyzer):
    """Security analysis and fraud detection"""
    
    # ==================== HELPER METHODS ====================
    
    def _build_prefix_pattern(self, prefixes: List[str]) -> str:
        """
        Build a regex pattern from prefixes, properly escaping special characters
        
        :param prefixes: List of prefixes
        :return: Regex pattern string
        """
        if not prefixes:
            return ''
        
        # Filter out empty strings and escape special regex characters
        escaped_prefixes = []
        for p in prefixes:
            if p:  # Skip empty strings
                # Escape special regex characters
                escaped = re.escape(str(p))
                escaped_prefixes.append(f'^{escaped}')
        
        if not escaped_prefixes:
            return ''
        
        return '|'.join(escaped_prefixes)
    
    def _match_prefixes(self, series: pd.Series, prefixes: List[str]) -> pd.Series:
        """
        Match a series against prefixes, handling special characters
        
        :param series: Pandas Series to match
        :param prefixes: List of prefixes to match against
        :return: Boolean Series indicating matches
        """
        if not prefixes:
            return pd.Series([False] * len(series), index=series.index)
        
        pattern = self._build_prefix_pattern(prefixes)
        
        if not pattern:
            return pd.Series([False] * len(series), index=series.index)
        
        try:
            return series.astype(str).str.match(pattern, na=False)
        except re.error as e:
            logger.warning(f"Regex pattern error: {e}. Falling back to startswith matching.")
            # Fallback to simple startswith matching
            mask = pd.Series([False] * len(series), index=series.index)
            for prefix in prefixes:
                if prefix:
                    mask = mask | series.astype(str).str.startswith(str(prefix), na=False)
            return mask
    
    # ==================== TOLL FRAUD DETECTION ====================
    
    def detect_toll_fraud(
        self,
        international_prefixes: Optional[List[str]] = None,
        high_risk_prefixes: Optional[List[str]] = None,
        duration_threshold: int = 1800,
        calls_threshold: int = 10
    ) -> Dict[str, Any]:
        """
        Detect potential toll fraud indicators
        
        :param international_prefixes: List of international call prefixes
        :param high_risk_prefixes: List of high-risk destination prefixes
        :param duration_threshold: Long call duration threshold (seconds)
        :param calls_threshold: High frequency threshold per user per day
        :return: Dictionary with fraud indicators
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        if international_prefixes is None:
            international_prefixes = getattr(
                getattr(self.settings, 'security', None), 
                'international_prefixes', 
                ['+1', '+44', '+49', '+33', '+86', '+91', '011', '00']
            )
        
        if high_risk_prefixes is None:
            # Common high-risk/premium rate prefixes
            high_risk_prefixes = [
                '900', '976', '809', '284', '649', '767', '664',  # Caribbean/Premium
                '011', '00',  # International
            ]
        
        alerts = []
        
        # 1. International calls analysis - using safe matching
        intl_mask = self._match_prefixes(df['finalCalledPartyNumber'], international_prefixes)
        intl_calls = df[intl_mask]
        
        if not intl_calls.empty:
            # Group by caller
            intl_by_caller = intl_calls.groupby('callingPartyNumber').agg({
                'globalCallID_callId': 'count',
                'duration': 'sum',
                'finalCalledPartyNumber': lambda x: list(x.unique())[:10],
            }).reset_index()
            
            intl_by_caller.columns = ['caller', 'intl_calls', 'total_duration', 'destinations']
            
            # Flag high-volume international callers
            suspicious_intl = intl_by_caller[
                (intl_by_caller['intl_calls'] > calls_threshold) |
                (intl_by_caller['total_duration'] > duration_threshold * 2)
            ]
            
            if not suspicious_intl.empty:
                alerts.append({
                    'type': 'high_volume_international',
                    'severity': 'high',
                    'description': f'{len(suspicious_intl)} callers with high international call volume',
                    'affected_callers': suspicious_intl.to_dict('records'),
                })
        
        # 2. High-risk destinations - using safe matching
        risk_mask = self._match_prefixes(df['finalCalledPartyNumber'], high_risk_prefixes)
        risk_calls = df[risk_mask]
        
        if not risk_calls.empty:
            risk_by_caller = risk_calls.groupby('callingPartyNumber').agg({
                'globalCallID_callId': 'count',
                'duration': 'sum',
            }).reset_index()
            
            risk_by_caller.columns = ['caller', 'risk_calls', 'total_duration']
            
            alerts.append({
                'type': 'high_risk_destinations',
                'severity': 'medium',
                'description': f'{len(risk_calls)} calls to high-risk destinations',
                'unique_callers': len(risk_by_caller),
                'top_callers': risk_by_caller.head(10).to_dict('records'),
            })
        
        # 3. Long duration calls
        long_calls = df[df['duration'] > duration_threshold]
        
        if not long_calls.empty:
            long_outbound = long_calls[long_calls['call_type'] == 'outbound']
            
            if not long_outbound.empty:
                alerts.append({
                    'type': 'long_duration_outbound',
                    'severity': 'medium',
                    'description': f'{len(long_outbound)} outbound calls over {duration_threshold}s',
                    'max_duration': int(long_outbound['duration'].max()),
                    'callers': long_outbound['callingPartyNumber'].value_counts().head(5).to_dict(),
                })
        
        # 4. After-hours international
        if 'is_business_hours' in df.columns:
            after_hours_intl = intl_calls[~intl_calls['is_business_hours']]
            
            if not after_hours_intl.empty and len(after_hours_intl) > 5:
                alerts.append({
                    'type': 'after_hours_international',
                    'severity': 'high',
                    'description': f'{len(after_hours_intl)} international calls outside business hours',
                    'callers': after_hours_intl['callingPartyNumber'].value_counts().head(10).to_dict(),
                })
        
        # 5. Unusual call patterns (same destination many times)
        dest_counts = df.groupby(['callingPartyNumber', 'finalCalledPartyNumber']).size().reset_index(name='count')
        repeated_calls = dest_counts[dest_counts['count'] > 20]  # Same caller-called pair >20 times
        
        if not repeated_calls.empty:
            alerts.append({
                'type': 'repeated_destination_pattern',
                'severity': 'low',
                'description': f'{len(repeated_calls)} caller-destination pairs with >20 calls',
                'patterns': repeated_calls.head(10).to_dict('records'),
            })
        
        return {
            'analysis_timestamp': datetime.now().isoformat(),
            'total_calls_analyzed': len(df),
            'international_calls': len(intl_calls),
            'high_risk_calls': len(risk_calls) if not risk_calls.empty else 0,
            'alert_count': len(alerts),
            'alerts': alerts,
            'risk_level': 'high' if any(a['severity'] == 'high' for a in alerts) else 
                         ('medium' if any(a['severity'] == 'medium' for a in alerts) else 'low'),
        }
    
    # ==================== AFTER-HOURS ANALYSIS ====================
    
    def detect_after_hours_anomalies(
        self,
        threshold_calls: int = 10,
        sensitive_extensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Detect suspicious after-hours activity
        
        :param threshold_calls: Minimum after-hours calls to flag
        :param sensitive_extensions: List of sensitive/executive extensions
        :return: Dictionary with after-hours anomalies
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        if 'is_business_hours' not in df.columns:
            return {'error': 'Business hours not configured'}
        
        after_hours = df[~df['is_business_hours']]
        
        if after_hours.empty:
            return {
                'total_after_hours_calls': 0,
                'message': 'No after-hours calls detected'
            }
        
        anomalies = []
        
        # 1. Users with high after-hours activity
        user_after_hours = after_hours.groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
            'call_type': lambda x: (x == 'outbound').sum(),
        }).reset_index()
        
        user_after_hours.columns = ['user', 'after_hours_calls', 'total_duration', 'outbound_calls']
        
        suspicious_users = user_after_hours[user_after_hours['after_hours_calls'] > threshold_calls]
        
        if not suspicious_users.empty:
            anomalies.append({
                'type': 'high_after_hours_activity',
                'severity': 'medium',
                'description': f'{len(suspicious_users)} users with >{threshold_calls} after-hours calls',
                'users': suspicious_users.to_dict('records'),
            })
        
        # 2. Check sensitive extensions
        if sensitive_extensions:
            sensitive_after_hours = after_hours[
                after_hours['callingPartyNumber'].isin(sensitive_extensions) |
                after_hours['finalCalledPartyNumber'].isin(sensitive_extensions)
            ]
            
            if not sensitive_after_hours.empty:
                anomalies.append({
                    'type': 'sensitive_extension_after_hours',
                    'severity': 'high',
                    'description': f'{len(sensitive_after_hours)} after-hours calls involving sensitive extensions',
                    'extensions_involved': list(set(
                        list(sensitive_after_hours['callingPartyNumber'].unique()) +
                        list(sensitive_after_hours['finalCalledPartyNumber'].unique())
                    ) & set(sensitive_extensions)),
                    'call_count': len(sensitive_after_hours),
                })
        
        # 3. Weekend activity
        weekend_calls = after_hours[after_hours['is_weekend']] if 'is_weekend' in after_hours.columns else pd.DataFrame()
        
        if not weekend_calls.empty:
            weekend_by_user = weekend_calls.groupby('callingPartyNumber').size()
            heavy_weekend_users = weekend_by_user[weekend_by_user > 5]
            
            if not heavy_weekend_users.empty:
                anomalies.append({
                    'type': 'weekend_activity',
                    'severity': 'low',
                    'description': f'{len(heavy_weekend_users)} users with >5 weekend calls',
                    'users': heavy_weekend_users.head(10).to_dict(),
                })
        
        # 4. Late night calls (midnight to 5 AM)
        if 'hour' in after_hours.columns:
            late_night = after_hours[after_hours['hour'].isin([0, 1, 2, 3, 4, 5])]
            
            if not late_night.empty:
                anomalies.append({
                    'type': 'late_night_activity',
                    'severity': 'medium',
                    'description': f'{len(late_night)} calls between midnight and 5 AM',
                    'callers': late_night['callingPartyNumber'].value_counts().head(10).to_dict(),
                    'destinations': late_night['finalCalledPartyNumber'].value_counts().head(10).to_dict(),
                })
        
        # 5. Outbound after-hours
        outbound_after_hours = after_hours[after_hours['call_type'] == 'outbound']
        
        return {
            'analysis_timestamp': datetime.now().isoformat(),
            'total_after_hours_calls': len(after_hours),
            'after_hours_pct': round(len(after_hours) / len(df) * 100, 2),
            'outbound_after_hours': len(outbound_after_hours),
            'unique_after_hours_callers': after_hours['callingPartyNumber'].nunique(),
            'anomaly_count': len(anomalies),
            'anomalies': anomalies,
        }
    
    # ==================== UNAUTHORIZED EXTENSIONS ====================
    
    def get_unauthorized_extensions(
        self,
        authorized_extensions: Optional[List[str]] = None,
        authorized_patterns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Identify calls from unknown/unauthorized extensions
        
        :param authorized_extensions: List of authorized extension numbers
        :param authorized_patterns: List of regex patterns for authorized extensions
        :return: Dictionary with unauthorized extension analysis
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        all_callers = set(df['callingPartyNumber'].unique())
        
        unauthorized = all_callers.copy()
        
        # Remove authorized by exact match
        if authorized_extensions:
            unauthorized = unauthorized - set(authorized_extensions)
        
        # Remove authorized by pattern
        if authorized_patterns:
            for pattern in authorized_patterns:
                try:
                    compiled = re.compile(pattern)
                    unauthorized = {
                        ext for ext in unauthorized 
                        if not compiled.match(str(ext))
                    }
                except re.error as e:
                    logger.warning(f"Invalid regex pattern '{pattern}': {e}")
        
        # If no authorized list provided, try to detect internal extensions
        if authorized_extensions is None and authorized_patterns is None:
            # Assume internal extensions are 3-6 digits
            def is_likely_internal(ext):
                ext_str = str(ext)
                return ext_str.isdigit() and 3 <= len(ext_str) <= 6
            
            unauthorized = {ext for ext in unauthorized if not is_likely_internal(ext)}
        
        unauthorized_calls = df[df['callingPartyNumber'].isin(unauthorized)]
        
        if unauthorized_calls.empty:
            return {
                'unauthorized_extensions_found': 0,
                'message': 'No unauthorized extensions detected'
            }
        
        # Analyze unauthorized calls
        unauth_summary = unauthorized_calls.groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
            'origDeviceName': 'first',
            'call_type': lambda x: x.mode().iloc[0] if not x.empty else 'unknown',
        }).reset_index()
        
        unauth_summary.columns = ['extension', 'total_calls', 'total_duration', 
                                  'device', 'primary_call_type']
        
        return {
            'unauthorized_extensions_found': len(unauthorized),
            'unauthorized_calls': len(unauthorized_calls),
            'unauthorized_calls_pct': round(len(unauthorized_calls) / len(df) * 100, 2),
            'extensions': unauth_summary.sort_values('total_calls', ascending=False).to_dict('records'),
            'recommendation': 'Review these extensions and add to authorized list if valid',
        }
    
    # ==================== LONG DURATION CALLS ====================
    
    def get_long_duration_calls(
        self,
        threshold_seconds: int = 3600,
        include_internal: bool = False
    ) -> pd.DataFrame:
        """
        Get unusually long calls
        
        :param threshold_seconds: Duration threshold
        :param include_internal: Include internal calls
        :return: DataFrame with long calls
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        long_calls = df[df['duration'] > threshold_seconds]
        
        if not include_internal:
            long_calls = long_calls[long_calls['call_type'] != 'internal']
        
        if long_calls.empty:
            return pd.DataFrame()
        
        # Select relevant columns
        columns = [
            'dateTimeOrigination_dt', 'callingPartyNumber', 'finalCalledPartyNumber',
            'duration', 'call_type', 'origDeviceName', 'destDeviceName'
        ]
        available_cols = [c for c in columns if c in long_calls.columns]
        
        result = long_calls[available_cols].copy()
        result['duration_formatted'] = result['duration'].apply(
            lambda x: f"{int(x//3600)}h {int((x%3600)//60)}m {int(x%60)}s"
        )
        
        return result.sort_values('duration', ascending=False)
    
    # ==================== HIGH FREQUENCY CALLERS ====================
    
    def get_high_frequency_callers(
        self,
        calls_per_hour_threshold: int = 30,
        time_window_hours: int = 1
    ) -> Dict[str, Any]:
        """
        Detect callers with unusually high call frequency
        
        :param calls_per_hour_threshold: Maximum calls per hour threshold
        :param time_window_hours: Time window for frequency calculation
        :return: Dictionary with high frequency analysis
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        # Create time windows - FIXED: was 'f' instead of 'df'
        df['time_window'] = df['dateTimeOrigination_dt'].dt.floor(f'{time_window_hours}h')
        
        # Count calls per user per window
        frequency = df.groupby(['callingPartyNumber', 'time_window']).size().reset_index(name='call_count')
        
        # Find high frequency instances
        high_freq = frequency[frequency['call_count'] > calls_per_hour_threshold]
        
        if high_freq.empty:
            return {
                'high_frequency_instances': 0,
                'message': f'No callers exceeded {calls_per_hour_threshold} calls per {time_window_hours}h window'
            }
        
        # Get unique callers with high frequency
        suspicious_callers = high_freq.groupby('callingPartyNumber').agg({
            'call_count': ['max', 'sum', 'count'],
            'time_window': ['min', 'max'],
        }).reset_index()
        
        suspicious_callers.columns = ['caller', 'max_calls_in_window', 'total_calls_in_high_freq_windows',
                                     'num_high_freq_windows', 'first_occurrence', 'last_occurrence']
        
        return {
            'threshold': {
                'calls_per_window': calls_per_hour_threshold,
                'window_hours': time_window_hours,
            },
            'high_frequency_instances': len(high_freq),
            'unique_suspicious_callers': len(suspicious_callers),
            'callers': suspicious_callers.sort_values('max_calls_in_window', ascending=False).to_dict('records'),
            'severity': 'high' if suspicious_callers['max_calls_in_window'].max() > calls_per_hour_threshold * 2 else 'medium',
        }
    
    # ==================== BLOCKED CALLS ====================
    
    def get_blocked_calls_report(self) -> Dict[str, Any]:
        """
        Analyze blocked/rejected calls
        
        :return: Dictionary with blocked calls analysis
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        # Identify blocked calls by cause codes
        blocked_cause_codes = [21, 52, 54, 57, 63, 79]  # Rejection, barred, etc.
        
        blocked = pd.DataFrame()
        
        if 'origCause_value' in df.columns:
            blocked = df[df['origCause_value'].isin(blocked_cause_codes)]
        elif 'destCause_value' in df.columns:
            blocked = df[df['destCause_value'].isin(blocked_cause_codes)]
        
        if blocked.empty:
            return {
                'blocked_calls': 0,
                'message': 'No blocked calls detected (or cause codes not available)'
            }
        
        # Analyze blocked calls
        blocked_by_caller = blocked.groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'finalCalledPartyNumber': lambda x: list(x.unique())[:5],
        }).reset_index()
        
        blocked_by_caller.columns = ['caller', 'blocked_attempts', 'destinations_attempted']
        
        blocked_by_dest = blocked.groupby('finalCalledPartyNumber').size().reset_index(name='block_count')
        
        return {
            'total_blocked_calls': len(blocked),
            'blocked_pct': round(len(blocked) / len(df) * 100, 2),
            'by_cause_code': blocked['origCause_value'].value_counts().to_dict() if 'origCause_value' in blocked.columns else {},
            'top_blocked_callers': blocked_by_caller.sort_values('blocked_attempts', ascending=False).head(10).to_dict('records'),
            'top_blocked_destinations': blocked_by_dest.sort_values('block_count', ascending=False).head(10).to_dict('records'),
            'by_hour': blocked['hour'].value_counts().sort_index().to_dict() if 'hour' in blocked.columns else {},
        }
    
    # ==================== COMPLIANCE REPORTING ====================
    
    def get_compliance_report(
        self,
        rules: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check calls against compliance rules
        
        :param rules: Dictionary with compliance rules
        :return: Dictionary with compliance report
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        # Default rules
        if rules is None:
            rules = {
                'max_call_duration_sec': 7200,         # 2 hours
                'blocked_prefixes': ['900', '976'],    # Premium rate
                'require_business_hours': False,
                'max_calls_per_user_per_day': 200,
                'require_internal_extension': True,
            }
        
        violations = []
        compliant_calls = len(df)
        
        # Rule 1: Max call duration
        if 'max_call_duration_sec' in rules:
            long_calls = df[df['duration'] > rules['max_call_duration_sec']]
            if not long_calls.empty:
                violations.append({
                    'rule': 'max_call_duration',
                    'threshold': rules['max_call_duration_sec'],
                    'violation_count': len(long_calls),
                    'details': f'{len(long_calls)} calls exceeded max duration',
                })
                compliant_calls -= len(long_calls)
        
        # Rule 2: Blocked prefixes - using safe matching
        if 'blocked_prefixes' in rules:
            blocked_mask = self._match_prefixes(
                df['finalCalledPartyNumber'], 
                rules['blocked_prefixes']
            )
            blocked_dest_calls = df[blocked_mask]
            if not blocked_dest_calls.empty:
                violations.append({
                    'rule': 'blocked_prefixes',
                    'blocked_prefixes': rules['blocked_prefixes'],
                    'violation_count': len(blocked_dest_calls),
                    'details': f'{len(blocked_dest_calls)} calls to blocked prefixes',
                    'callers': blocked_dest_calls['callingPartyNumber'].value_counts().head(5).to_dict(),
                })
                compliant_calls -= len(blocked_dest_calls)
        
        # Rule 3: Business hours only
        if rules.get('require_business_hours') and 'is_business_hours' in df.columns:
            after_hours = df[~df['is_business_hours']]
            outbound_after = after_hours[after_hours['call_type'] == 'outbound']
            if not outbound_after.empty:
                violations.append({
                    'rule': 'business_hours_only',
                    'violation_count': len(outbound_after),
                    'details': f'{len(outbound_after)} outbound calls outside business hours',
                })
                compliant_calls -= len(outbound_after)
        
        # Rule 4: Max calls per user per day
        if 'max_calls_per_user_per_day' in rules:
            daily_counts = df.groupby(['callingPartyNumber', 'date']).size().reset_index(name='count')
            over_limit = daily_counts[daily_counts['count'] > rules['max_calls_per_user_per_day']]
            if not over_limit.empty:
                violations.append({
                    'rule': 'max_calls_per_user_per_day',
                    'threshold': rules['max_calls_per_user_per_day'],
                    'violation_count': len(over_limit),
                    'details': f'{over_limit["callingPartyNumber"].nunique()} users exceeded daily limit',
                    'violators': over_limit.groupby('callingPartyNumber')['count'].max().head(10).to_dict(),
                })
        
        compliance_rate = (compliant_calls / len(df) * 100) if len(df) > 0 else 100
        
        return {
            'report_timestamp': datetime.now().isoformat(),
            'total_calls_analyzed': len(df),
            'rules_checked': list(rules.keys()),
            'compliant_calls': compliant_calls,
            'compliance_rate': round(compliance_rate, 2),
            'violation_count': len(violations),
            'violations': violations,
            'status': 'COMPLIANT' if not violations else 'NON-COMPLIANT',
        }
    
    # ==================== CALL RECORDING STATUS ====================
    
    def get_call_recording_status(
        self,
        recording_indicator_col: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Check call recording compliance
        
        :param recording_indicator_col: Column indicating recording status
        :return: Dictionary with recording status
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        # Common recording indicator columns
        possible_cols = ['isRecorded', 'recordingFlag', 'recorded', 'callRecording']
        
        if recording_indicator_col:
            rec_col = recording_indicator_col
        else:
            rec_col = None
            for col in possible_cols:
                if col in df.columns:
                    rec_col = col
                    break
        
        if rec_col is None:
            # If no recording column, provide general stats
            return {
                'recording_data_available': False,
                'message': 'No recording indicator column found in CDR data',
                'total_calls': len(df),
                'recommendation': 'Enable call recording tracking in CDM configuration',
            }
        
        recorded = df[df[rec_col] == True] if df[rec_col].dtype == bool else df[df[rec_col] == 1]
        not_recorded = df[~df.index.isin(recorded.index)]
        
        return {
            'recording_data_available': True,
            'recording_column': rec_col,
            'total_calls': len(df),
            'recorded_calls': len(recorded),
            'not_recorded_calls': len(not_recorded),
            'recording_rate': round(len(recorded) / len(df) * 100, 2),
            'recorded_by_type': recorded['call_type'].value_counts().to_dict() if not recorded.empty else {},
            'not_recorded_by_type': not_recorded['call_type'].value_counts().to_dict() if not not_recorded.empty else {},
        }
    
    # ==================== USER AUDIT ====================
    
    def audit_user_activity(
        self,
        user: str,
        days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Full audit trail for a specific user
        
        :param user: Phone number or user ID
        :param days: Optional limit to last N days
        :return: Dictionary with user audit
        """
        if not self._check_cdr_loaded():
            return {'error': 'CDR data not loaded'}
        
        df = self.cdr.copy()
        
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['dateTimeOrigination_dt'] >= cutoff]
        
        # Get user's calls
        user_calls = df[
            (df['callingPartyNumber'] == user) |
            (df['finalCalledPartyNumber'] == user) |
            (df['callingPartyUnicodeLoginUserID'] == user)
        ]
        
        if user_calls.empty:
            return {'user': user, 'error': 'No calls found for this user'}
        
        outgoing = user_calls[user_calls['callingPartyNumber'] == user]
        incoming = user_calls[user_calls['finalCalledPartyNumber'] == user]
        
        # Build audit report
        audit = {
            'user': user,
            'audit_period': {
                'start': user_calls['dateTimeOrigination_dt'].min().isoformat(),
                'end': user_calls['dateTimeOrigination_dt'].max().isoformat(),
                'days': days or 'all',
            },
            'summary': {
                'total_calls': len(user_calls),
                'outgoing_calls': len(outgoing),
                'incoming_calls': len(incoming),
                'answered_calls': int(user_calls['answered'].sum()) if 'answered' in user_calls.columns else 0,
                'missed_calls': len(user_calls) - int(user_calls['answered'].sum()) if 'answered' in user_calls.columns else 0,
                'total_duration_sec': int(user_calls['duration'].sum()),
                'avg_duration_sec': round(user_calls[user_calls['answered']]['duration'].mean(), 1) if 'answered' in user_calls.columns and user_calls['answered'].any() else 0,
            },
            'call_types': user_calls['call_type'].value_counts().to_dict() if 'call_type' in user_calls.columns else {},
            'devices_used': outgoing['origDeviceName'].unique().tolist() if not outgoing.empty and 'origDeviceName' in outgoing.columns else [],
        }
        
        # Time patterns
        if 'hour' in user_calls.columns:
            audit['activity_by_hour'] = user_calls['hour'].value_counts().sort_index().to_dict()
        
        if 'day_name' in user_calls.columns:
            audit['activity_by_day'] = user_calls['day_name'].value_counts().to_dict()
        
        # Business hours compliance
        if 'is_business_hours' in user_calls.columns:
            audit['business_hours_compliance'] = {
                'business_hours_calls': int(user_calls['is_business_hours'].sum()),
                'after_hours_calls': int((~user_calls['is_business_hours']).sum()),
                'after_hours_outgoing': int((~outgoing['is_business_hours']).sum()) if not outgoing.empty and 'is_business_hours' in outgoing.columns else 0,
            }
        
        # Top contacts
        if not outgoing.empty:
            audit['top_called'] = outgoing['finalCalledPartyNumber'].value_counts().head(10).to_dict()
        
        if not incoming.empty:
            audit['top_callers'] = incoming['callingPartyNumber'].value_counts().head(10).to_dict()
        
        # Potential concerns
        concerns = []
        
        # After-hours activity
        if audit.get('business_hours_compliance', {}).get('after_hours_outgoing', 0) > 20:
            concerns.append({
                'type': 'high_after_hours_activity',
                'detail': f"{audit['business_hours_compliance']['after_hours_outgoing']} outgoing calls after hours",
            })
        
        # High volume
        days_active = user_calls['date'].nunique() if 'date' in user_calls.columns else 1
        calls_per_day = len(user_calls) / days_active if days_active > 0 else 0
        if calls_per_day > 100:
            concerns.append({
                'type': 'high_call_volume',
                'detail': f"Average {calls_per_day:.1f} calls per day",
            })
        
        # Long calls
        long_calls = user_calls[user_calls['duration'] > 3600]
        if not long_calls.empty:
            concerns.append({
                'type': 'long_duration_calls',
                'detail': f"{len(long_calls)} calls over 1 hour",
            })
        
        audit['concerns'] = concerns
        audit['risk_level'] = 'high' if len(concerns) > 2 else ('medium' if concerns else 'low')
        
        # Recent calls
        cols_for_recent = ['dateTimeOrigination_dt', 'callingPartyNumber', 'finalCalledPartyNumber', 'duration']
        if 'answered' in user_calls.columns:
            cols_for_recent.append('answered')
        if 'call_type' in user_calls.columns:
            cols_for_recent.append('call_type')
        
        available_cols = [c for c in cols_for_recent if c in user_calls.columns]
        recent = user_calls.sort_values('dateTimeOrigination_dt', ascending=False).head(20)
        audit['recent_calls'] = recent[available_cols].to_dict('records')
        
        return audit
    
    # ==================== SECURITY SUMMARY ====================
    
    def get_security_summary(self) -> Dict[str, Any]:
        """
        Get overall security summary
        
        :return: Dictionary with security summary
        """
        fraud = self.detect_toll_fraud()
        after_hours = self.detect_after_hours_anomalies()
        high_freq = self.get_high_frequency_callers()
        
        alerts = []
        
        # Collect all alerts
        if 'alerts' in fraud:
            alerts.extend(fraud['alerts'])
        if 'anomalies' in after_hours:
            alerts.extend(after_hours['anomalies'])
        
        # Determine overall risk level
        high_severity = sum(1 for a in alerts if a.get('severity') == 'high')
        medium_severity = sum(1 for a in alerts if a.get('severity') == 'medium')
        
        if high_severity > 0:
            overall_risk = 'HIGH'
        elif medium_severity > 0:
            overall_risk = 'MEDIUM'
        else:
            overall_risk = 'LOW'
        
        return {
            'summary_timestamp': datetime.now().isoformat(),
            'overall_risk_level': overall_risk,
            'total_alerts': len(alerts),
            'high_severity_alerts': high_severity,
            'medium_severity_alerts': medium_severity,
            'low_severity_alerts': len(alerts) - high_severity - medium_severity,
            'fraud_indicators': fraud.get('alert_count', 0),
            'after_hours_anomalies': len(after_hours.get('anomalies', [])),
            'high_frequency_callers': high_freq.get('unique_suspicious_callers', 0),
            'recommendations': self._generate_security_recommendations(alerts),
        }
    
    def _generate_security_recommendations(
        self, 
        alerts: List[Dict]
    ) -> List[str]:
        """Generate security recommendations based on alerts"""
        recommendations = []
        
        alert_types = {a.get('type') for a in alerts}
        
        if 'high_volume_international' in alert_types or 'after_hours_international' in alert_types:
            recommendations.append(
                "Review and restrict international calling permissions"
            )
        
        if 'high_after_hours_activity' in alert_types:
            recommendations.append(
                "Implement after-hours call restrictions or monitoring"
            )
        
        if 'late_night_activity' in alert_types:
            recommendations.append(
                "Investigate late-night calling patterns for potential unauthorized access"
            )
        
        if 'repeated_destination_pattern' in alert_types:
            recommendations.append(
                "Review unusual repeated call patterns for potential autodialers"
            )
        
        if not recommendations:
            recommendations.append(
                "Continue monitoring - no critical security issues detected"
            )
        
        return recommendations