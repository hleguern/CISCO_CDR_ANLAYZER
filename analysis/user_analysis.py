"""
User-based analysis for CDR data
Includes user activity, call history, comparisons, and department stats
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import logging

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class UserAnalyzer(BaseAnalyzer):
    """User-based analysis of call data"""
    
    # ==================== USER LISTING ====================
    
    def get_all_users(self) -> List[str]:
        """
        Get all unique users/phone numbers
        
        :return: Sorted list of unique phone numbers
        """
        if not self._check_cdr_loaded():
            return []
        
        callers = set(self.cdr['callingPartyNumber'].unique())
        called = set(self.cdr['finalCalledPartyNumber'].unique())
        all_users = callers | called
        
        # Filter out empty strings and special values
        all_users = {u for u in all_users if u and u not in ['', 'nan', '\\']}
        
        return sorted(list(all_users))
    
    def get_internal_users(self) -> List[str]:
        """
        Get internal users (based on device patterns)
        
        :return: List of internal extension numbers
        """
        if not self._check_cdr_loaded():
            return []
        
        df = self.cdr.copy()
        
        # Internal calls typically from SEP/CSF devices
        internal_mask = (
            df['origDeviceName'].str.startswith('SEP') |
            df['origDeviceName'].str.startswith('CSF') |
            df['origDeviceName'].str.startswith('TCT')
        )
        
        internal_users = set(df[internal_mask]['callingPartyNumber'].unique())
        internal_users = {u for u in internal_users if u and len(u) <= 6}  # Extensions typically short
        
        return sorted(list(internal_users))
    
    # ==================== USER RECORDS ====================
    
    def get_user_records(
        self, 
        user: str,
        days: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get all call records for a specific user
        
        :param user: Phone number or user ID
        :param days: Optional - limit to last N days
        :return: DataFrame with user's call records
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Filter by days if specified
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['dateTimeOrigination_dt'] >= cutoff]
        
        mask = (
            (df['callingPartyNumber'] == user) |
            (df['finalCalledPartyNumber'] == user) |
            (df['callingPartyUnicodeLoginUserID'] == user)
        )
        
        return df[mask].copy()
    
    def get_user_call_history(
        self, 
        user: str, 
        days: int = 30
    ) -> pd.DataFrame:
        """
        Get detailed call history for a user
        
        :param user: Phone number or user ID
        :param days: Number of days to look back
        :return: DataFrame with call history
        """
        records = self.get_user_records(user, days=days)
        
        if records.empty:
            return pd.DataFrame()
        
        # Select relevant columns
        columns = [
            'dateTimeOrigination_dt',
            'callingPartyNumber',
            'finalCalledPartyNumber',
            'duration',
            'answered',
            'call_type',
            'origDeviceName',
            'destDeviceName',
        ]
        
        available_cols = [c for c in columns if c in records.columns]
        history = records[available_cols].copy()
        
        # Add direction indicator
        history['direction'] = np.where(
            history['callingPartyNumber'] == user,
            'outbound',
            'inbound'
        )
        
        # Add other party
        history['other_party'] = np.where(
            history['callingPartyNumber'] == user,
            history['finalCalledPartyNumber'],
            history['callingPartyNumber']
        )
        
        return history.sort_values('dateTimeOrigination_dt', ascending=False)
    
    # ==================== USER STATISTICS ====================
    
    def get_user_statistics(self, user: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific user
        
        :param user: Phone number or user ID
        :return: Dictionary with user statistics
        """
        records = self.get_user_records(user)
        
        if records.empty:
            return {'user': user, 'error': 'User not found or no records'}
        
        outgoing = records[records['callingPartyNumber'] == user]
        incoming = records[records['finalCalledPartyNumber'] == user]
        
        out_answered = outgoing[outgoing['answered']]
        in_answered = incoming[incoming['answered']]
        
        stats = {
            'user': user,
            'total_calls': len(records),
            'outgoing': {
                'total': len(outgoing),
                'answered': len(out_answered),
                'missed': len(outgoing) - len(out_answered),
                'answer_rate': round(len(out_answered) / len(outgoing) * 100, 2) if len(outgoing) > 0 else 0,
                'total_duration': int(outgoing['duration'].sum()),
                'avg_duration': round(out_answered['duration'].mean(), 1) if len(out_answered) > 0 else 0,
            },
            'incoming': {
                'total': len(incoming),
                'answered': len(in_answered),
                'missed': len(incoming) - len(in_answered),
                'answer_rate': round(len(in_answered) / len(incoming) * 100, 2) if len(incoming) > 0 else 0,
                'total_duration': int(incoming['duration'].sum()),
                'avg_duration': round(in_answered['duration'].mean(), 1) if len(in_answered) > 0 else 0,
            },
            'total_duration_sec': int(records['duration'].sum()),
            'avg_call_duration_sec': round(records[records['answered']]['duration'].mean(), 1),
            'devices_used': outgoing['origDeviceName'].unique().tolist(),
            'call_types': records['call_type'].value_counts().to_dict(),
        }
        
        # Date range
        if 'dateTimeOrigination_dt' in records.columns:
            stats['first_call'] = records['dateTimeOrigination_dt'].min().isoformat()
            stats['last_call'] = records['dateTimeOrigination_dt'].max().isoformat()
        
        return stats
    
    def get_user_activity_pattern(self, user: str) -> Dict[str, Any]:
        """
        Analyze when a user is most active
        
        :param user: Phone number or user ID
        :return: Dictionary with activity patterns
        """
        records = self.get_user_records(user)
        
        if records.empty:
            return {'user': user, 'error': 'No records found'}
        
        # Hourly pattern
        hourly = records['hour'].value_counts().sort_index()
        peak_hour = hourly.idxmax() if not hourly.empty else None
        
        # Daily pattern
        daily = records['day_name'].value_counts()
        peak_day = daily.idxmax() if not daily.empty else None
        
        # Business hours activity
        business_hours = records[records['is_business_hours']]
        after_hours = records[~records['is_business_hours']]
        
        return {
            'user': user,
            'hourly_distribution': hourly.to_dict(),
            'daily_distribution': daily.to_dict(),
            'peak_hour': peak_hour,
            'peak_hour_label': f"{peak_hour:02d}:00-{peak_hour:02d}:59" if peak_hour is not None else None,
            'peak_day': peak_day,
            'business_hours_calls': len(business_hours),
            'after_hours_calls': len(after_hours),
            'business_hours_pct': round(len(business_hours) / len(records) * 100, 2),
            'avg_calls_per_day': round(len(records) / records['date'].nunique(), 2),
            'active_days': records['date'].nunique(),
        }
    
    # ==================== INACTIVE USERS ====================
    
    def get_inactive_users(
        self, 
        days_threshold: int = 30,
        user_list: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        Find users with no activity for specified days
        
        :param days_threshold: Days of inactivity threshold
        :param user_list: Optional list of users to check
        :return: DataFrame with inactive users
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        # Get all users if not provided
        if user_list is None:
            user_list = self.get_all_users()
        
        # Get last activity for each user
        last_activity = []
        
        for user in user_list:
            user_records = df[
                (df['callingPartyNumber'] == user) |
                (df['finalCalledPartyNumber'] == user)
            ]
            
            if user_records.empty:
                last_activity.append({
                    'user': user,
                    'last_activity': None,
                    'days_inactive': None,
                    'status': 'never_active'
                })
            else:
                last_date = user_records['dateTimeOrigination_dt'].max()
                days_since = (datetime.now() - last_date).days
                
                if last_date < cutoff_date:
                    last_activity.append({
                        'user': user,
                        'last_activity': last_date.isoformat(),
                        'days_inactive': days_since,
                        'total_calls': len(user_records),
                        'status': 'inactive'
                    })
        
        result = pd.DataFrame(last_activity)
        if not result.empty:
            result = result.sort_values('days_inactive', ascending=False, na_position='first')
        
        return result
    
    def get_user_activity_summary(
        self, 
        days: int = 30
    ) -> pd.DataFrame:
        """
        Get activity summary for all users
        
        :param days: Number of days to analyze
        :return: DataFrame with user activity summary
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df['dateTimeOrigination_dt'] >= cutoff]
        
        # Aggregate caller stats
        caller_stats = df.groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
            'answered': 'sum',
            'dateTimeOrigination_dt': 'max',
        }).reset_index()
        
        caller_stats.columns = ['user', 'outgoing_calls', 'outgoing_duration',
                               'outgoing_answered', 'last_outgoing']
        
        # Aggregate called stats
        called_stats = df.groupby('finalCalledPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
            'answered': 'sum',
            'dateTimeOrigination_dt': 'max',
        }).reset_index()
        
        called_stats.columns = ['user', 'incoming_calls', 'incoming_duration',
                               'incoming_answered', 'last_incoming']
        
        # Merge
        activity = pd.merge(caller_stats, called_stats, on='user', how='outer').fillna(0)
        
        activity['total_calls'] = activity['outgoing_calls'] + activity['incoming_calls']
        activity['total_duration'] = activity['outgoing_duration'] + activity['incoming_duration']
        activity['last_activity'] = activity[['last_outgoing', 'last_incoming']].max(axis=1)
        
        return activity.sort_values('total_calls', ascending=False)
    
    # ==================== USER COMPARISON ====================
    
    def get_user_comparison(
        self, 
        users: List[str]
    ) -> pd.DataFrame:
        """
        Compare statistics across multiple users
        
        :param users: List of user phone numbers to compare
        :return: DataFrame with comparison data
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        comparisons = []
        
        for user in users:
            records = self.get_user_records(user)
            
            if records.empty:
                comparisons.append({
                    'user': user,
                    'total_calls': 0,
                    'status': 'no_records'
                })
                continue
            
            outgoing = records[records['callingPartyNumber'] == user]
            incoming = records[records['finalCalledPartyNumber'] == user]
            answered = records[records['answered']]
            
            comparisons.append({
                'user': user,
                'total_calls': len(records),
                'outgoing_calls': len(outgoing),
                'incoming_calls': len(incoming),
                'answered_calls': len(answered),
                'answer_rate': round(len(answered) / len(records) * 100, 2),
                'total_duration_sec': int(records['duration'].sum()),
                'avg_duration_sec': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
                'unique_contacts': len(set(
                    list(records['callingPartyNumber'].unique()) +
                    list(records['finalCalledPartyNumber'].unique())
                ) - {user}),
                'active_days': records['date'].nunique(),
                'calls_per_day': round(len(records) / max(records['date'].nunique(), 1), 2),
            })
        
        return pd.DataFrame(comparisons)
    
    # ==================== CONTACTS ANALYSIS ====================
    
    def get_connected_users(self, user: str) -> List[str]:
        """
        Get all users that have communicated with the specified user
        
        :param user: Phone number or user ID
        :return: List of connected phone numbers
        """
        records = self.get_user_records(user)
        
        if records.empty:
            return []
        
        connected = set()
        connected.update(records['callingPartyNumber'].unique())
        connected.update(records['finalCalledPartyNumber'].unique())
        connected.discard(user)
        connected.discard('')
        connected.discard('nan')
        
        return sorted(list(connected))
    
    def get_close_contacts(
        self, 
        user: str, 
        top_n: int = 10
    ) -> pd.DataFrame:
        """
        Get the most frequently contacted numbers for a user
        
        :param user: Phone number or user ID
        :param top_n: Number of top contacts to return
        :return: DataFrame with contact statistics
        """
        records = self.get_user_records(user)
        
        if records.empty:
            return pd.DataFrame()
        
        # Outgoing contacts
        outgoing = records[records['callingPartyNumber'] == user].groupby('finalCalledPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
            'answered': 'sum',
        }).reset_index()
        outgoing.columns = ['contact', 'outgoing_calls', 'outgoing_duration', 'outgoing_answered']
        
        # Incoming contacts
        incoming = records[records['finalCalledPartyNumber'] == user].groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
            'answered': 'sum',
        }).reset_index()
        incoming.columns = ['contact', 'incoming_calls', 'incoming_duration', 'incoming_answered']
        
        # Merge
        contacts = pd.merge(outgoing, incoming, on='contact', how='outer').fillna(0)
        
        contacts['total_calls'] = contacts['outgoing_calls'] + contacts['incoming_calls']
        contacts['total_duration'] = contacts['outgoing_duration'] + contacts['incoming_duration']
        contacts['total_answered'] = contacts['outgoing_answered'] + contacts['incoming_answered']
        
        return contacts.sort_values('total_calls', ascending=False).head(top_n)
    
    def get_records_between_users(
        self, 
        user1: str, 
        user2: str
    ) -> pd.DataFrame:
        """
        Get call records between two specific users
        
        :param user1: First phone number
        :param user2: Second phone number
        :return: DataFrame with calls between the users
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        mask = (
            ((df['callingPartyNumber'] == user1) & (df['finalCalledPartyNumber'] == user2)) |
            ((df['callingPartyNumber'] == user2) & (df['finalCalledPartyNumber'] == user1))
        )
        
        return df[mask].sort_values('dateTimeOrigination_dt', ascending=False)
    
    # ==================== DEPARTMENT ANALYSIS ====================
    
    def get_department_stats(
        self, 
        dept_mapping: Dict[str, List[str]]
    ) -> pd.DataFrame:
        """
        Get statistics grouped by department
        
        :param dept_mapping: Dictionary mapping department names to lists of extensions
        :return: DataFrame with department statistics
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        dept_stats = []
        
        for dept_name, extensions in dept_mapping.items():
            # Get calls where department extensions are involved
            dept_calls = df[
                (df['callingPartyNumber'].isin(extensions)) |
                (df['finalCalledPartyNumber'].isin(extensions))
            ]
            
            if dept_calls.empty:
                dept_stats.append({
                    'department': dept_name,
                    'total_calls': 0,
                })
                continue
            
            # Outgoing from department
            outgoing = dept_calls[dept_calls['callingPartyNumber'].isin(extensions)]
            # Incoming to department
            incoming = dept_calls[dept_calls['finalCalledPartyNumber'].isin(extensions)]
            
            answered = dept_calls[dept_calls['answered']]
            
            dept_stats.append({
                'department': dept_name,
                'extension_count': len(extensions),
                'total_calls': len(dept_calls),
                'outgoing_calls': len(outgoing),
                'incoming_calls': len(incoming),
                'answered_calls': len(answered),
                'answer_rate': round(len(answered) / len(dept_calls) * 100, 2),
                'total_duration_sec': int(dept_calls['duration'].sum()),
                'avg_duration_sec': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
                'calls_per_extension': round(len(dept_calls) / len(extensions), 1),
            })
        
        result = pd.DataFrame(dept_stats)
        return result.sort_values('total_calls', ascending=False)
    
    def get_inter_department_calls(
        self, 
        dept_mapping: Dict[str, List[str]]
    ) -> pd.DataFrame:
        """
        Analyze calls between departments
        
        :param dept_mapping: Dictionary mapping department names to extensions
        :return: DataFrame with inter-department call matrix
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Create extension to department mapping
        ext_to_dept = {}
        for dept, extensions in dept_mapping.items():
            for ext in extensions:
                ext_to_dept[ext] = dept
        
        # Map departments
        df['calling_dept'] = df['callingPartyNumber'].map(ext_to_dept)
        df['called_dept'] = df['finalCalledPartyNumber'].map(ext_to_dept)
        
        # Filter to only inter-department calls
        dept_calls = df.dropna(subset=['calling_dept', 'called_dept'])
        
        # Create matrix
        matrix = pd.crosstab(
            dept_calls['calling_dept'],
            dept_calls['called_dept'],
            values=dept_calls['globalCallID_callId'],
            aggfunc='count'
        ).fillna(0).astype(int)
        
        return matrix
    
    # ==================== USER TRENDS ====================
    
    def get_user_call_duration_trend(
        self, 
        user: str,
        period: str = 'daily'
    ) -> pd.DataFrame:
        """
        Get call duration trend over time for a user
        
        :param user: Phone number or user ID
        :param period: 'daily', 'weekly', or 'monthly'
        :return: DataFrame with duration trend
        """
        records = self.get_user_records(user)
        
        if records.empty:
            return pd.DataFrame()
        
        records = records.copy()
        
        if period == 'daily':
            group_col = 'date'
        elif period == 'weekly':
            records['period'] = records['dateTimeOrigination_dt'].dt.to_period('W')
            group_col = 'period'
        elif period == 'monthly':
            records['period'] = records['dateTimeOrigination_dt'].dt.to_period('M')
            group_col = 'period'
        else:
            group_col = 'date'
        
        trend = records.groupby(group_col).agg({
            'duration': ['sum', 'mean', 'max', 'count'],
        }).reset_index()
        
        trend.columns = [group_col, 'total_duration', 'avg_duration', 
                        'max_duration', 'call_count']
        
        # Calculate rolling average
        trend['duration_rolling_avg'] = trend['avg_duration'].rolling(
            window=7, min_periods=1
        ).mean().round(1)
        
        return trend
    
    def get_user_quality_trend(
        self, 
        user: str,
        period: str = 'daily'
    ) -> pd.DataFrame:
        """
        Get quality metrics trend for a user
        
        :param user: Phone number or user ID
        :param period: 'daily', 'weekly', or 'monthly'
        :return: DataFrame with quality trend
        """
        if self.merged is None:
            logger.warning("Merged data not available, attempting to use CMR")
            return pd.DataFrame()
        
        df = self.merged.copy()
        
        # Filter for user
        user_data = df[
            (df['callingPartyNumber'] == user) |
            (df['finalCalledPartyNumber'] == user)
        ]
        
        if user_data.empty:
            return pd.DataFrame()
        
        if period == 'daily':
            group_col = 'date'
        elif period == 'weekly':
            user_data['period'] = user_data['dateTimeOrigination_dt'].dt.to_period('W')
            group_col = 'period'
        else:
            user_data['period'] = user_data['dateTimeOrigination_dt'].dt.to_period('M')
            group_col = 'period'
        
        # Aggregate quality metrics
        quality_cols = ['origjitter', 'destjitter', 'origlatency', 'destlatency',
                       'orig_packet_loss_pct', 'dest_packet_loss_pct']
        available_cols = [c for c in quality_cols if c in user_data.columns]
        
        if not available_cols:
            return pd.DataFrame()
        
        agg_dict = {col: 'mean' for col in available_cols}
        agg_dict['globalCallID_callId'] = 'count'
        
        if 'avg_mos' in user_data.columns:
            agg_dict['avg_mos'] = 'mean'
        
        trend = user_data.groupby(group_col).agg(agg_dict).reset_index()
        trend = trend.rename(columns={'globalCallID_callId': 'call_count'})
        
        return trend
    
    # ==================== TOP USERS ====================
    
    def get_top_callers(self, n: int = 10) -> pd.DataFrame:
        """
        Get top N callers by number of calls
        
        :param n: Number of top callers
        :return: DataFrame with caller statistics
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        caller_stats = self.cdr.groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
        }).reset_index()
        
        caller_stats.columns = ['caller', 'total_calls', 'total_duration',
                               'avg_duration', 'answered_calls']
        
        caller_stats['answer_rate'] = (
            caller_stats['answered_calls'] / caller_stats['total_calls'] * 100
        ).round(2)
        
        return caller_stats.sort_values('total_calls', ascending=False).head(n)
    
    def get_top_called(self, n: int = 10) -> pd.DataFrame:
        """
        Get top N called numbers
        
        :param n: Number of top called numbers
        :return: DataFrame with statistics
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        called_stats = self.cdr.groupby('finalCalledPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
        }).reset_index()
        
        called_stats.columns = ['called_number', 'total_calls', 'total_duration',
                               'avg_duration', 'answered_calls']
        
        called_stats['answer_rate'] = (
            called_stats['answered_calls'] / called_stats['total_calls'] * 100
        ).round(2)
        
        return called_stats.sort_values('total_calls', ascending=False).head(n)
    
    def get_top_call_pairs(self, n: int = 10) -> pd.DataFrame:
        """
        Get most frequent caller-called pairs
        
        :param n: Number of top pairs
        :return: DataFrame with pair statistics
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        # Create pair identifier
        df = self.cdr.copy()
        df['pair'] = df.apply(
            lambda x: tuple(sorted([x['callingPartyNumber'], x['finalCalledPartyNumber']])),
            axis=1
        )
        
        pairs = df.groupby('pair').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
        }).reset_index()
        
        pairs.columns = ['pair', 'total_calls', 'total_duration', 
                        'avg_duration', 'answered_calls']
        
        # Split pair tuple
        pairs['user1'] = pairs['pair'].apply(lambda x: x[0])
        pairs['user2'] = pairs['pair'].apply(lambda x: x[1])
        pairs = pairs.drop('pair', axis=1)
        
        return pairs.sort_values('total_calls', ascending=False).head(n)
    
    # ==================== EXTENSION DIRECTORY ====================
    
    def get_extension_directory_mapping(
        self, 
        name_column: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Map extensions to available identifying information
        
        :param name_column: Optional column containing user names
        :return: DataFrame with extension mappings
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Get unique callers with their devices
        directory = df.groupby('callingPartyNumber').agg({
            'origDeviceName': lambda x: list(x.unique()),
            'callingPartyUnicodeLoginUserID': 'first',
            'globalCallID_callId': 'count',
            'dateTimeOrigination_dt': ['min', 'max'],
        }).reset_index()
        
        directory.columns = ['extension', 'devices', 'login_user_id',
                            'total_calls', 'first_seen', 'last_seen']
        
        # Extract device type from first device
        directory['primary_device'] = directory['devices'].apply(
            lambda x: x[0] if x else None
        )
        
        directory['device_count'] = directory['devices'].apply(len)
        
        # Determine if extension is internal
        directory['is_internal'] = directory['extension'].apply(
            lambda x: len(str(x)) <= 6
        )
        
        return directory.sort_values('total_calls', ascending=False)
    
    def get_connection_matrix(
        self, 
        users: Optional[List[str]] = None,
        min_calls: int = 1
    ) -> pd.DataFrame:
        """
        Get a connection matrix showing call counts between users
        
        :param users: Optional list of users to include
        :param min_calls: Minimum calls to include in matrix
        :return: DataFrame with connection matrix
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        if users:
            df = df[
                (df['callingPartyNumber'].isin(users)) &
                (df['finalCalledPartyNumber'].isin(users))
            ]
        
        matrix = pd.crosstab(
            df['callingPartyNumber'],
            df['finalCalledPartyNumber'],
            values=df['globalCallID_callId'],
            aggfunc='count'
        ).fillna(0).astype(int)
        
        # Filter by minimum calls
        if min_calls > 1:
            matrix = matrix.where(matrix >= min_calls, 0)
        
        return matrix
    
    # ==================== MISSED CALLS ====================
    
    def get_missed_calls(
        self, 
        user: Optional[str] = None,
        days: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Get missed/unanswered calls
        
        :param user: Optional user filter
        :param days: Optional days filter
        :return: DataFrame with missed calls
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        if days:
            cutoff = datetime.now() - timedelta(days=days)
            df = df[df['dateTimeOrigination_dt'] >= cutoff]
        
        if user:
            df = df[df['finalCalledPartyNumber'] == user]
        
        missed = df[~df['answered']].copy()
        
        return missed.sort_values('dateTimeOrigination_dt', ascending=False)
    
    def get_missed_call_analysis(
        self, 
        user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze missed call patterns
        
        :param user: Optional user filter
        :return: Dictionary with analysis
        """
        missed = self.get_missed_calls(user)
        
        if missed.empty:
            return {'total_missed': 0}
        
        return {
            'total_missed': len(missed),
            'by_hour': missed['hour'].value_counts().sort_index().to_dict(),
            'by_day': missed['day_name'].value_counts().to_dict(),
            'by_type': missed['call_type'].value_counts().to_dict(),
            'top_callers': missed['callingPartyNumber'].value_counts().head(10).to_dict(),
            'peak_missed_hour': missed['hour'].mode().iloc[0] if not missed.empty else None,
            'business_hours_missed': len(missed[missed['is_business_hours']]),
            'after_hours_missed': len(missed[~missed['is_business_hours']]),
        }
        