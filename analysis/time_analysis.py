"""
Time-based analysis for CDR data
Includes daily, weekly, monthly trends, peak hours, business hours analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Union
from collections import defaultdict
import logging

from .base import BaseAnalyzer

logger = logging.getLogger(__name__)


class TimeAnalyzer(BaseAnalyzer):
    """Time-based analysis of call data"""
    
    # ==================== DAILY ANALYSIS ====================
    
    def get_daily_call_volume(
        self, 
        start_date: Optional[Union[str, date]] = None,
        end_date: Optional[Union[str, date]] = None,
        call_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get call volume per day
        
        :param start_date: Optional start date filter
        :param end_date: Optional end date filter
        :param call_type: Optional filter by call type
        :return: DataFrame with daily call volumes
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Apply filters
        if start_date:
            start_date = pd.to_datetime(start_date).date()
            df = df[df['date'] >= start_date]
        if end_date:
            end_date = pd.to_datetime(end_date).date()
            df = df[df['date'] <= end_date]
        if call_type:
            df = df[df['call_type'] == call_type]
        
        # Aggregate by date
        daily = df.groupby('date').agg({
            'globalCallID_callId': 'count',
            'answered': 'sum',
            'duration': ['sum', 'mean'],
        }).reset_index()
        
        daily.columns = ['date', 'total_calls', 'answered_calls', 
                        'total_duration', 'avg_duration']
        
        daily['missed_calls'] = daily['total_calls'] - daily['answered_calls']
        daily['answer_rate'] = (daily['answered_calls'] / daily['total_calls'] * 100).round(2)
        daily['date'] = pd.to_datetime(daily['date'])
        daily['day_name'] = daily['date'].dt.day_name()
        
        return daily.sort_values('date')
    
    def get_daily_stats(self, target_date: Union[str, date]) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific day
        
        :param target_date: The date to analyze
        :return: Dictionary with daily statistics
        """
        if not self._check_cdr_loaded():
            return {}
        
        target_date = pd.to_datetime(target_date).date()
        df = self.cdr[self.cdr['date'] == target_date]
        
        if df.empty:
            return {'error': f'No data for {target_date}'}
        
        answered = df[df['answered']]
        
        return {
            'date': str(target_date),
            'day_name': pd.to_datetime(target_date).day_name(),
            'total_calls': len(df),
            'answered_calls': len(answered),
            'missed_calls': len(df) - len(answered),
            'answer_rate': round(len(answered) / len(df) * 100, 2),
            'total_duration_sec': int(df['duration'].sum()),
            'avg_duration_sec': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
            'peak_hour': df['hour'].mode().iloc[0] if not df.empty else None,
            'calls_by_hour': df['hour'].value_counts().sort_index().to_dict(),
            'calls_by_type': df['call_type'].value_counts().to_dict(),
            'unique_callers': df['callingPartyNumber'].nunique(),
            'unique_called': df['finalCalledPartyNumber'].nunique(),
            'busiest_caller': df['callingPartyNumber'].mode().iloc[0] if not df.empty else None,
        }
    
    # ==================== WEEKLY ANALYSIS ====================
    
    def get_weekly_trends(
        self, 
        weeks: int = 12
    ) -> pd.DataFrame:
        """
        Get week-over-week comparison
        
        :param weeks: Number of weeks to analyze
        :return: DataFrame with weekly trends
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        df['year_week'] = df['dateTimeOrigination_dt'].dt.strftime('%Y-W%U')
        
        weekly = df.groupby('year_week').agg({
            'globalCallID_callId': 'count',
            'answered': 'sum',
            'duration': ['sum', 'mean'],
            'date': ['min', 'max']
        }).reset_index()
        
        weekly.columns = ['year_week', 'total_calls', 'answered_calls',
                         'total_duration', 'avg_duration', 'week_start', 'week_end']
        
        weekly['missed_calls'] = weekly['total_calls'] - weekly['answered_calls']
        weekly['answer_rate'] = (weekly['answered_calls'] / weekly['total_calls'] * 100).round(2)
        
        # Calculate week-over-week changes
        weekly['calls_change'] = weekly['total_calls'].diff()
        weekly['calls_change_pct'] = weekly['total_calls'].pct_change() * 100
        weekly['duration_change_pct'] = weekly['total_duration'].pct_change() * 100
        
        # Get last N weeks
        weekly = weekly.sort_values('year_week', ascending=False).head(weeks)
        
        return weekly.sort_values('year_week')
    
    def get_week_comparison(
        self, 
        week1: str, 
        week2: str
    ) -> Dict[str, Any]:
        """
        Compare two specific weeks
        
        :param week1: First week in format 'YYYY-WNN'
        :param week2: Second week in format 'YYYY-WNN'
        :return: Comparison dictionary
        """
        if not self._check_cdr_loaded():
            return {}
        
        df = self.cdr.copy()
        df['year_week'] = df['dateTimeOrigination_dt'].dt.strftime('%Y-W%U')
        
        w1_data = df[df['year_week'] == week1]
        w2_data = df[df['year_week'] == week2]
        
        def week_stats(data, name):
            if data.empty:
                return {'error': f'No data for {name}'}
            answered = data[data['answered']]
            return {
                'week': name,
                'total_calls': len(data),
                'answered_calls': len(answered),
                'answer_rate': round(len(answered) / len(data) * 100, 2),
                'total_duration': int(data['duration'].sum()),
                'avg_duration': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
            }
        
        stats1 = week_stats(w1_data, week1)
        stats2 = week_stats(w2_data, week2)
        
        comparison = {
            'week1': stats1,
            'week2': stats2,
            'changes': {}
        }
        
        if 'error' not in stats1 and 'error' not in stats2:
            comparison['changes'] = {
                'calls_diff': stats2['total_calls'] - stats1['total_calls'],
                'calls_pct_change': round(
                    (stats2['total_calls'] - stats1['total_calls']) / stats1['total_calls'] * 100, 2
                ) if stats1['total_calls'] > 0 else 0,
                'answer_rate_diff': round(stats2['answer_rate'] - stats1['answer_rate'], 2),
                'duration_pct_change': round(
                    (stats2['total_duration'] - stats1['total_duration']) / stats1['total_duration'] * 100, 2
                ) if stats1['total_duration'] > 0 else 0,
            }
        
        return comparison
    
    # ==================== MONTHLY ANALYSIS ====================
    
    def get_monthly_trends(
        self, 
        months: int = 12
    ) -> pd.DataFrame:
        """
        Get month-over-month comparison
        
        :param months: Number of months to analyze
        :return: DataFrame with monthly trends
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        df['year_month'] = df['dateTimeOrigination_dt'].dt.to_period('M')
        
        monthly = df.groupby('year_month').agg({
            'globalCallID_callId': 'count',
            'answered': 'sum',
            'duration': ['sum', 'mean'],
            'callingPartyNumber': 'nunique',
        }).reset_index()
        
        monthly.columns = ['year_month', 'total_calls', 'answered_calls',
                          'total_duration', 'avg_duration', 'unique_callers']
        
        monthly['missed_calls'] = monthly['total_calls'] - monthly['answered_calls']
        monthly['answer_rate'] = (monthly['answered_calls'] / monthly['total_calls'] * 100).round(2)
        monthly['avg_calls_per_day'] = (monthly['total_calls'] / 
                                        monthly['year_month'].dt.days_in_month).round(1)
        
        # Calculate month-over-month changes
        monthly['calls_change'] = monthly['total_calls'].diff()
        monthly['calls_change_pct'] = (monthly['total_calls'].pct_change() * 100).round(2)
        monthly['duration_change_pct'] = (monthly['total_duration'].pct_change() * 100).round(2)
        
        # Convert period to string for JSON serialization
        monthly['year_month'] = monthly['year_month'].astype(str)
        
        return monthly.tail(months)
    
    def get_monthly_comparison(
        self, 
        month1: str, 
        month2: str
    ) -> Dict[str, Any]:
        """
        Compare two specific months
        
        :param month1: First month in format 'YYYY-MM'
        :param month2: Second month in format 'YYYY-MM'
        :return: Comparison dictionary
        """
        if not self._check_cdr_loaded():
            return {}
        
        df = self.cdr.copy()
        df['year_month'] = df['dateTimeOrigination_dt'].dt.strftime('%Y-%m')
        
        m1_data = df[df['year_month'] == month1]
        m2_data = df[df['year_month'] == month2]
        
        def month_stats(data, name):
            if data.empty:
                return {'error': f'No data for {name}'}
            answered = data[data['answered']]
            return {
                'month': name,
                'total_calls': len(data),
                'answered_calls': len(answered),
                'answer_rate': round(len(answered) / len(data) * 100, 2),
                'total_duration': int(data['duration'].sum()),
                'avg_duration': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
                'unique_callers': data['callingPartyNumber'].nunique(),
                'calls_by_type': data['call_type'].value_counts().to_dict(),
            }
        
        stats1 = month_stats(m1_data, month1)
        stats2 = month_stats(m2_data, month2)
        
        comparison = {
            'month1': stats1,
            'month2': stats2,
            'changes': {}
        }
        
        if 'error' not in stats1 and 'error' not in stats2:
            comparison['changes'] = {
                'calls_diff': stats2['total_calls'] - stats1['total_calls'],
                'calls_pct_change': round(
                    (stats2['total_calls'] - stats1['total_calls']) / stats1['total_calls'] * 100, 2
                ) if stats1['total_calls'] > 0 else 0,
                'answer_rate_diff': round(stats2['answer_rate'] - stats1['answer_rate'], 2),
            }
        
        return comparison
    
    # ==================== DAY OF WEEK ANALYSIS ====================
    
    def get_calls_by_day_of_week(
        self, 
        call_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get call distribution by day of week (Mon-Sun)
        
        :param call_type: Optional filter by call type
        :return: DataFrame with day of week statistics
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        if call_type:
            df = df[df['call_type'] == call_type]
        
        # Aggregate by day of week
        dow_stats = df.groupby(['day_of_week', 'day_name']).agg({
            'globalCallID_callId': 'count',
            'answered': ['sum', 'mean'],
            'duration': ['sum', 'mean'],
        }).reset_index()
        
        dow_stats.columns = ['day_of_week', 'day_name', 'total_calls', 
                            'answered_calls', 'answer_rate', 
                            'total_duration', 'avg_duration']
        
        dow_stats['answer_rate'] = (dow_stats['answer_rate'] * 100).round(2)
        dow_stats['missed_calls'] = dow_stats['total_calls'] - dow_stats['answered_calls']
        
        # Calculate percentage of weekly calls
        total = dow_stats['total_calls'].sum()
        dow_stats['pct_of_total'] = (dow_stats['total_calls'] / total * 100).round(2)
        
        # Sort by day of week (Monday=0)
        dow_stats = dow_stats.sort_values('day_of_week')
        
        return dow_stats
    
    def get_weekday_vs_weekend(self) -> Dict[str, Any]:
        """
        Compare weekday vs weekend call patterns
        
        :return: Dictionary with comparison
        """
        if not self._check_cdr_loaded():
            return {}
        
        df = self.cdr.copy()
        
        weekday = df[~df['is_weekend']]
        weekend = df[df['is_weekend']]
        
        def get_stats(data, name):
            if data.empty:
                return {'name': name, 'total_calls': 0}
            answered = data[data['answered']]
            return {
                'name': name,
                'total_calls': len(data),
                'answered_calls': len(answered),
                'answer_rate': round(len(answered) / len(data) * 100, 2),
                'total_duration': int(data['duration'].sum()),
                'avg_duration': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
                'avg_calls_per_day': round(len(data) / data['date'].nunique(), 1),
            }
        
        return {
            'weekday': get_stats(weekday, 'Weekday'),
            'weekend': get_stats(weekend, 'Weekend'),
        }
    
    # ==================== HOURLY ANALYSIS ====================
    
    def get_peak_hours(
        self, 
        top_n: int = 5
    ) -> pd.DataFrame:
        """
        Identify busiest hours
        
        :param top_n: Number of top hours to return
        :return: DataFrame with peak hours
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        hourly = df.groupby('hour').agg({
            'globalCallID_callId': 'count',
            'answered': 'sum',
            'duration': ['sum', 'mean'],
        }).reset_index()
        
        hourly.columns = ['hour', 'total_calls', 'answered_calls', 
                         'total_duration', 'avg_duration']
        
        hourly['hour_label'] = hourly['hour'].apply(lambda h: f"{h:02d}:00-{h:02d}:59")
        hourly['answer_rate'] = (hourly['answered_calls'] / hourly['total_calls'] * 100).round(2)
        
        # Calculate percentage
        total = hourly['total_calls'].sum()
        hourly['pct_of_total'] = (hourly['total_calls'] / total * 100).round(2)
        
        return hourly.sort_values('total_calls', ascending=False).head(top_n)
    
    def get_hourly_distribution(self) -> pd.DataFrame:
        """
        Get complete hourly distribution (0-23)
        
        :return: DataFrame with hourly statistics
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Create complete hour range
        hourly = df.groupby('hour').agg({
            'globalCallID_callId': 'count',
            'answered': 'sum',
            'duration': ['sum', 'mean'],
        }).reindex(range(24), fill_value=0).reset_index()
        
        hourly.columns = ['hour', 'total_calls', 'answered_calls', 
                         'total_duration', 'avg_duration']
        
        hourly['hour_label'] = hourly['hour'].apply(lambda h: f"{h:02d}:00")
        hourly['answer_rate'] = np.where(
            hourly['total_calls'] > 0,
            (hourly['answered_calls'] / hourly['total_calls'] * 100).round(2),
            0
        )
        
        return hourly
    
    # ==================== BUSINESS HOURS ANALYSIS ====================
    
    def get_business_hours_stats(self) -> Dict[str, Any]:
        """
        Compare business hours vs after-hours call patterns
        
        :return: Dictionary with comparison
        """
        if not self._check_cdr_loaded():
            return {}
        
        df = self.cdr.copy()
        bh = self.settings.business_hours
        
        business = df[df['is_business_hours']]
        after_hours = df[~df['is_business_hours']]
        
        def get_stats(data, name):
            if data.empty:
                return {'name': name, 'total_calls': 0}
            answered = data[data['answered']]
            return {
                'name': name,
                'total_calls': len(data),
                'answered_calls': len(answered),
                'missed_calls': len(data) - len(answered),
                'answer_rate': round(len(answered) / len(data) * 100, 2),
                'total_duration': int(data['duration'].sum()),
                'avg_duration': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
                'calls_by_type': data['call_type'].value_counts().to_dict(),
            }
        
        business_stats = get_stats(business, 'Business Hours')
        after_stats = get_stats(after_hours, 'After Hours')
        
        total_calls = len(df)
        
        return {
            'business_hours_config': {
                'start': bh.start_hour,
                'end': bh.end_hour,
                'business_days': bh.business_days,
            },
            'business_hours': business_stats,
            'after_hours': after_stats,
            'business_hours_pct': round(business_stats['total_calls'] / total_calls * 100, 2) if total_calls > 0 else 0,
            'after_hours_pct': round(after_stats['total_calls'] / total_calls * 100, 2) if total_calls > 0 else 0,
        }
    
    # ==================== HEATMAP DATA ====================
    
    def get_hourly_heatmap_data(self) -> pd.DataFrame:
        """
        Get Hour x Day heatmap data
        
        :return: DataFrame with heatmap data (pivot table)
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Create pivot table: rows=hour, columns=day of week
        heatmap = pd.crosstab(
            df['hour'],
            df['day_name'],
            values=df['globalCallID_callId'],
            aggfunc='count'
        ).fillna(0)
        
        # Reorder columns to Monday-Sunday
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                    'Friday', 'Saturday', 'Sunday']
        available_days = [d for d in day_order if d in heatmap.columns]
        heatmap = heatmap[available_days]
        
        return heatmap
    
    def get_hourly_heatmap_by_metric(
        self, 
        metric: str = 'count'
    ) -> pd.DataFrame:
        """
        Get Hour x Day heatmap for different metrics
        
        :param metric: 'count', 'duration', 'answer_rate'
        :return: DataFrame with heatmap data
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        if metric == 'count':
            heatmap = pd.crosstab(
                df['hour'], df['day_name'],
                values=df['globalCallID_callId'], aggfunc='count'
            )
        elif metric == 'duration':
            heatmap = pd.crosstab(
                df['hour'], df['day_name'],
                values=df['duration'], aggfunc='mean'
            )
        elif metric == 'answer_rate':
            heatmap = pd.crosstab(
                df['hour'], df['day_name'],
                values=df['answered'], aggfunc='mean'
            ) * 100
        else:
            return pd.DataFrame()
        
        # Reorder columns
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 
                    'Friday', 'Saturday', 'Sunday']
        available_days = [d for d in day_order if d in heatmap.columns]
        
        return heatmap[available_days].fillna(0)
    
    # ==================== TREND ANALYSIS ====================
    
    def get_call_volume_trend(
        self, 
        period: str = 'daily',
        rolling_window: int = 7
    ) -> pd.DataFrame:
        """
        Get call volume trend over time with rolling average
        
        :param period: 'daily', 'weekly', or 'monthly'
        :param rolling_window: Window size for rolling average
        :return: DataFrame with trend data
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        if period == 'daily':
            group_col = 'date'
        elif period == 'weekly':
            df['period'] = df['dateTimeOrigination_dt'].dt.to_period('W')
            group_col = 'period'
        elif period == 'monthly':
            df['period'] = df['dateTimeOrigination_dt'].dt.to_period('M')
            group_col = 'period'
        else:
            group_col = 'date'
        
        trend = df.groupby(group_col).agg({
            'globalCallID_callId': 'count',
            'answered': 'sum',
            'duration': 'sum',
        }).reset_index()
        
        trend.columns = [group_col, 'total_calls', 'answered_calls', 'total_duration']
        
        # Calculate rolling averages
        trend['calls_rolling_avg'] = trend['total_calls'].rolling(
            window=rolling_window, min_periods=1
        ).mean().round(1)
        
        trend['duration_rolling_avg'] = trend['total_duration'].rolling(
            window=rolling_window, min_periods=1
        ).mean().round(1)
        
        # Calculate trend direction
        trend['trend'] = np.where(
            trend['total_calls'] > trend['calls_rolling_avg'],
            'above_average',
            'below_average'
        )
        
        return trend
    
    def compare_periods(
        self, 
        period1_start: Union[str, date],
        period1_end: Union[str, date],
        period2_start: Union[str, date],
        period2_end: Union[str, date]
    ) -> Dict[str, Any]:
        """
        Compare two arbitrary time periods
        
        :param period1_start: Start of first period
        :param period1_end: End of first period
        :param period2_start: Start of second period
        :param period2_end: End of second period
        :return: Dictionary with comparison
        """
        if not self._check_cdr_loaded():
            return {}
        
        df = self.cdr.copy()
        
        p1_start = pd.to_datetime(period1_start).date()
        p1_end = pd.to_datetime(period1_end).date()
        p2_start = pd.to_datetime(period2_start).date()
        p2_end = pd.to_datetime(period2_end).date()
        
        p1_data = df[(df['date'] >= p1_start) & (df['date'] <= p1_end)]
        p2_data = df[(df['date'] >= p2_start) & (df['date'] <= p2_end)]
        
        def period_stats(data, start, end):
            if data.empty:
                return {
                    'start': str(start),
                    'end': str(end),
                    'days': (end - start).days + 1,
                    'total_calls': 0
                }
            
            answered = data[data['answered']]
            days = (end - start).days + 1
            
            return {
                'start': str(start),
                'end': str(end),
                'days': days,
                'total_calls': len(data),
                'answered_calls': len(answered),
                'missed_calls': len(data) - len(answered),
                'answer_rate': round(len(answered) / len(data) * 100, 2),
                'total_duration': int(data['duration'].sum()),
                'avg_duration': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
                'avg_calls_per_day': round(len(data) / days, 1),
                'unique_callers': data['callingPartyNumber'].nunique(),
                'calls_by_type': data['call_type'].value_counts().to_dict(),
                'calls_by_hour': data['hour'].value_counts().sort_index().to_dict(),
            }
        
        stats1 = period_stats(p1_data, p1_start, p1_end)
        stats2 = period_stats(p2_data, p2_start, p2_end)
        
        result = {
            'period1': stats1,
            'period2': stats2,
            'comparison': {}
        }
        
        if stats1['total_calls'] > 0 and stats2['total_calls'] > 0:
            result['comparison'] = {
                'calls_diff': stats2['total_calls'] - stats1['total_calls'],
                'calls_pct_change': round(
                    (stats2['total_calls'] - stats1['total_calls']) / stats1['total_calls'] * 100, 2
                ),
                'avg_calls_per_day_diff': round(
                    stats2['avg_calls_per_day'] - stats1['avg_calls_per_day'], 1
                ),
                'answer_rate_diff': round(stats2['answer_rate'] - stats1['answer_rate'], 2),
                'duration_pct_change': round(
                    (stats2['total_duration'] - stats1['total_duration']) / stats1['total_duration'] * 100, 2
                ) if stats1['total_duration'] > 0 else 0,
            }
        
        return result
    
    # ==================== CONCURRENT CALLS ====================
    
    def get_concurrent_calls(
        self, 
        interval_minutes: int = 15
    ) -> pd.DataFrame:
        """
        Calculate concurrent call statistics
        
        :param interval_minutes: Time interval for bucketing
        :return: DataFrame with concurrent call data
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Create time intervals
        # df['time_bucket'] = df['dateTimeOrigination_dt'].dt.floor(f'{interval_minutes}T')
        df['time_bucket'] = df['dateTimeOrigination_dt'].dt.floor(f'{interval_minutes}min')
        
        concurrent = df.groupby('time_bucket').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
        }).reset_index()
        
        concurrent.columns = ['time_bucket', 'concurrent_calls', 'total_duration']
        
        # Find peak concurrent calls
        concurrent['is_peak'] = concurrent['concurrent_calls'] == concurrent['concurrent_calls'].max()
        
        return concurrent
    
    def get_peak_concurrent_calls(self) -> Dict[str, Any]:
        """
        Get peak concurrent call information
        
        :return: Dictionary with peak concurrent call data
        """
        concurrent = self.get_concurrent_calls(interval_minutes=5)
        
        if concurrent.empty:
            return {}
        
        peak_row = concurrent.loc[concurrent['concurrent_calls'].idxmax()]
        
        return {
            'peak_concurrent': int(peak_row['concurrent_calls']),
            'peak_time': str(peak_row['time_bucket']),
            'avg_concurrent': round(concurrent['concurrent_calls'].mean(), 1),
            'median_concurrent': int(concurrent['concurrent_calls'].median()),
            'p95_concurrent': int(concurrent['concurrent_calls'].quantile(0.95)),
            'p99_concurrent': int(concurrent['concurrent_calls'].quantile(0.99)),
        }