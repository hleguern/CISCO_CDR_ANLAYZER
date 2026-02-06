#!/usr/bin/env python3
"""
Advanced Example Usage of the Cisco CDR/CMR Analyzer

This comprehensive script demonstrates ALL analysis capabilities of the
CDR/CMR Analyzer including:
- Data loading and processing
- Time-based analysis (daily, weekly, monthly, hourly trends)
- User analysis (statistics, patterns, comparisons)
- Device analysis (utilization, health, quality)
- Quality analysis (MOS, jitter, latency, packet loss)
- Hunt group analysis (queues, wait times, abandonment)
- Security analysis (fraud detection, compliance)
- Visualization (charts, heatmaps, interactive plots)
- Report generation (HTML, JSON, Excel)

Author: CDR Analyzer Team
Version: 2.0
"""

import os
import sys
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add package to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cisco_cdr_analyzer import CiscoCDRAnalyzer
from cisco_cdr_analyzer.config.settings import Settings, QualityThresholds, BusinessHours


def print_section(title: str, char: str = "="):
    """Print formatted section header"""
    print(f"\n{char * 70}")
    print(f"  {title}")
    print(f"{char * 70}\n")


def print_subsection(title: str):
    """Print formatted subsection header"""
    print(f"\n  {title}")
    print(f"  {'-' * 50}")


def print_dict(data: Dict, indent: int = 4):
    """Pretty print dictionary"""
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{' ' * indent}{key}:")
            print_dict(value, indent + 4)
        elif isinstance(value, list):
            print(f"{' ' * indent}{key}: [{len(value)} items]")
        else:
            print(f"{' ' * indent}{key}: {value}")


def example_data_loading(analyzer: CiscoCDRAnalyzer, cdr_file: str, cmr_file: str):
    """Demonstrate data loading capabilities"""
    print_section("1. DATA LOADING & PROCESSING")
    
    # Load CDR
    print("  Loading CDR Data...")
    print(f"     Source: {cdr_file}")
    
    if os.path.exists(cdr_file):
        analyzer.load_cdr(cdr_file)
        print(f"     ✓ Loaded {len(analyzer.cdr_df):,} CDR records")
        print(f"     ✓ Columns: {len(analyzer.cdr_df.columns)}")
        print(f"     ✓ Date range: {analyzer.cdr_df['dateTimeOrigination_dt'].min()} to {analyzer.cdr_df['dateTimeOrigination_dt'].max()}")
    else:
        print(f"     File not found: {cdr_file}")
        return False
    
    # Load CMR
    print("\n  Loading CMR Data...")
    print(f"     Source: {cmr_file}")
    
    if os.path.exists(cmr_file):
        analyzer.load_cmr(cmr_file)
        print(f"     ✓ Loaded {len(analyzer.cmr_df):,} CMR records")
        print(f"     ✓ Quality columns available: origjitter, destjitter, origlatency, etc.")
        
        # Merge data
        print("\n  Merging CDR and CMR Data...")
        analyzer.merge_data()
        print(f"     ✓ Merged {len(analyzer.merged_df):,} records")
    else:
        print(f"     ℹCMR file not found (quality analysis will be limited)")
        analyzer.merge_data()  # Will use CDR only
    
    # Print basic info
    print("\n  Data Overview:")
    print(f"     • Total calls: {len(analyzer.cdr_df):,}")
    print(f"     • Unique callers: {analyzer.cdr_df['callingPartyNumber'].nunique():,}")
    print(f"     • Unique called: {analyzer.cdr_df['finalCalledPartyNumber'].nunique():,}")
    print(f"     • Unique devices: {analyzer.cdr_df['origDeviceName'].nunique():,}")
    
    return True


def example_call_summary(analyzer: CiscoCDRAnalyzer):
    """Demonstrate call summary functionality"""
    print_section("2. CALL SUMMARY")
    
    summary = analyzer.get_call_summary()
    
    print("  Overall Statistics:")
    print(f"     • Total Calls:        {summary['total_calls']:,}")
    print(f"     • Answered Calls:     {summary['answered_calls']:,}")
    print(f"     • Missed Calls:       {summary['missed_calls']:,}")
    print(f"     • Answer Rate:        {summary['answer_rate_pct']}%")
    print(f"     • Total Duration:     {summary['total_duration_formatted']}")
    print(f"     • Avg Duration:       {summary['avg_duration_sec']}s")
    print(f"     • Max Duration:       {summary['max_duration_sec']}s")
    print(f"     • Avg Ring Time:      {summary['avg_ring_time_sec']}s")
    
    print("\n  Call Types Distribution:")
    for call_type, count in summary.get('call_types', {}).items():
        pct = count / summary['total_calls'] * 100
        bar = "" * int(pct / 2) + "" * (50 - int(pct / 2))
        print(f"     • {call_type:12s}: {count:>8,} ({pct:>5.1f}%) {bar[:30]}")
    
    if 'date_range' in summary:
        print(f"\n  Date Range:")
        print(f"     • Start: {summary['date_range']['start']}")
        print(f"     • End:   {summary['date_range']['end']}")
        print(f"     • Days:  {summary['date_range']['days']}")
    
    return summary


def example_time_analysis(analyzer: CiscoCDRAnalyzer):
    """Demonstrate all time-based analysis functions"""
    print_section("3. TIME-BASED ANALYSIS")
    
    # ===== Daily Analysis =====
    print_subsection("3.1 Daily Call Volume")
    
    daily = analyzer.time.get_daily_call_volume()
    if not daily.empty:
        print(f"     Days analyzed: {len(daily)}")
        print(f"     Avg calls/day: {daily['total_calls'].mean():.0f}")
        print(f"     Max calls/day: {daily['total_calls'].max():,} on {daily.loc[daily['total_calls'].idxmax(), 'date']}")
        print(f"     Min calls/day: {daily['total_calls'].min():,} on {daily.loc[daily['total_calls'].idxmin(), 'date']}")
        
        print("\n     Last 7 days:")
        for _, row in daily.tail(7).iterrows():
            print(f"       {row['date']} ({row['day_name'][:3]}): {row['total_calls']:>5,} calls, {row['answer_rate']:.1f}% answered")
    
    # Get stats for a specific day
    if not daily.empty:
        sample_date = daily.iloc[-1]['date']
        day_stats = analyzer.time.get_daily_stats(sample_date)
        print(f"\n     Detailed stats for {sample_date}:")
        print(f"       Peak hour: {day_stats.get('peak_hour', 'N/A')}:00")
        print(f"       Unique callers: {day_stats.get('unique_callers', 0)}")
    
    # ===== Weekly Analysis =====
    print_subsection("3.2 Weekly Trends")
    
    weekly = analyzer.time.get_weekly_trends(weeks=8)
    if not weekly.empty:
        print(f"     Weeks analyzed: {len(weekly)}")
        print(f"     Avg calls/week: {weekly['total_calls'].mean():.0f}")
        
        print("\n     Week-over-week comparison:")
        for _, row in weekly.tail(4).iterrows():
            change = row.get('calls_change_pct', 0)
            change_indicator = "" if change > 0 else "" if change < 0 else ""
            print(f"       {row['year_week']}: {row['total_calls']:>6,} calls {change_indicator} ({change:+.1f}%)")
    
    # Compare two weeks
    if len(weekly) >= 2:
        week1 = weekly.iloc[-2]['year_week']
        week2 = weekly.iloc[-1]['year_week']
        comparison = analyzer.time.get_week_comparison(week1, week2)
        print(f"\n     Comparison {week1} vs {week2}:")
        if 'changes' in comparison and comparison['changes']:
            print(f"       Calls change: {comparison['changes'].get('calls_diff', 0):+,}")
            print(f"       Percentage change: {comparison['changes'].get('calls_pct_change', 0):+.1f}%")
    
    # ===== Monthly Analysis =====
    print_subsection("3.3 Monthly Trends")
    
    monthly = analyzer.time.get_monthly_trends(months=6)
    if not monthly.empty:
        print(f"     Months analyzed: {len(monthly)}")
        
        print("\n     Monthly breakdown:")
        for _, row in monthly.iterrows():
            print(f"       {row['year_month']}: {row['total_calls']:>7,} calls, "
                  f"{row['answer_rate']:.1f}% answered, "
                  f"{row['avg_calls_per_day']:.0f} avg/day")
    
    # ===== Day of Week Analysis =====
    print_subsection("3.4 Day of Week Distribution")
    
    dow = analyzer.time.get_calls_by_day_of_week()
    if not dow.empty:
        print("     Call distribution by day:")
        for _, row in dow.iterrows():
            bar = "█" * int(row['pct_of_total'] / 2)
            print(f"       {row['day_name']:9s}: {row['total_calls']:>6,} ({row['pct_of_total']:>5.1f}%) {bar}")
    
    # Weekday vs Weekend
    weekday_weekend = analyzer.time.get_weekday_vs_weekend()
    if weekday_weekend:
        print("\n     Weekday vs Weekend:")
        print(f"       Weekday avg: {weekday_weekend['weekday'].get('avg_calls_per_day', 0):.0f} calls/day")
        print(f"       Weekend avg: {weekday_weekend['weekend'].get('avg_calls_per_day', 0):.0f} calls/day")
    
    # ===== Hourly Analysis =====
    print_subsection("3.5 Hourly Distribution & Peak Hours")
    
    hourly = analyzer.time.get_hourly_distribution()
    peak_hours = analyzer.time.get_peak_hours(top_n=5)
    
    if not peak_hours.empty:
        print("     Top 5 busiest hours:")
        for _, row in peak_hours.iterrows():
            bar = "█" * int(row['pct_of_total'])
            print(f"       {row['hour_label']}: {row['total_calls']:>6,} calls ({row['pct_of_total']:.1f}%) {bar}")
    
    # ===== Business Hours Analysis =====
    print_subsection("3.6 Business Hours Analysis")
    
    bh_stats = analyzer.time.get_business_hours_stats()
    if bh_stats:
        print(f"     Business hours config: {bh_stats['business_hours_config']['start']}:00 - {bh_stats['business_hours_config']['end']}:00")
        print(f"\n     Business Hours:")
        print(f"       Calls: {bh_stats['business_hours']['total_calls']:,} ({bh_stats['business_hours_pct']}%)")
        print(f"       Answer rate: {bh_stats['business_hours']['answer_rate']}%")
        print(f"\n     After Hours:")
        print(f"       Calls: {bh_stats['after_hours']['total_calls']:,} ({bh_stats['after_hours_pct']}%)")
        print(f"       Answer rate: {bh_stats['after_hours']['answer_rate']}%")
    
    # ===== Heatmap Data =====
    print_subsection("3.7 Hourly Heatmap Data (Hour x Day)")
    
    heatmap = analyzer.time.get_hourly_heatmap_data()
    if not heatmap.empty:
        print(f"     Heatmap dimensions: {heatmap.shape[0]} hours x {heatmap.shape[1]} days")
        print(f"     Peak cell: Hour {heatmap.values.argmax() // 7}, {heatmap.columns[heatmap.values.argmax() % 7]}")
        print(f"     Max calls in single hour/day: {heatmap.values.max():.0f}")
    
    # ===== Call Volume Trend =====
    print_subsection("3.8 Call Volume Trend with Rolling Average")
    
    trend = analyzer.time.get_call_volume_trend(period='daily', rolling_window=7)
    if not trend.empty:
        print(f"     Trend data points: {len(trend)}")
        latest = trend.iloc[-1]
        print(f"     Latest period: {latest['date']}")
        print(f"       Calls: {latest['total_calls']:,}")
        print(f"       7-day avg: {latest['calls_rolling_avg']:.0f}")
        print(f"       Trend: {latest['trend']}")
    
    # ===== Period Comparison =====
    print_subsection("3.9 Compare Two Time Periods")
    
    # Compare last week to week before
    end_date = datetime.now().date()
    period2_start = end_date - timedelta(days=7)
    period1_end = period2_start - timedelta(days=1)
    period1_start = period1_end - timedelta(days=6)
    
    comparison = analyzer.time.compare_periods(
        period1_start, period1_end,
        period2_start, end_date
    )
    
    if 'comparison' in comparison and comparison['comparison']:
        print(f"     Period 1: {comparison['period1']['start']} to {comparison['period1']['end']}")
        print(f"       Calls: {comparison['period1'].get('total_calls', 0):,}")
        print(f"     Period 2: {comparison['period2']['start']} to {comparison['period2']['end']}")
        print(f"       Calls: {comparison['period2'].get('total_calls', 0):,}")
        print(f"\n     Changes:")
        print(f"       Call difference: {comparison['comparison'].get('calls_diff', 0):+,}")
        print(f"       Percentage change: {comparison['comparison'].get('calls_pct_change', 0):+.1f}%")
    
    # ===== Concurrent Calls =====
    print_subsection("3.10 Concurrent Calls Analysis")
    
    peak_concurrent = analyzer.time.get_peak_concurrent_calls()
    if peak_concurrent:
        print(f"     Peak concurrent calls: {peak_concurrent.get('peak_concurrent', 0)}")
        print(f"     Peak time: {peak_concurrent.get('peak_time', 'N/A')}")
        print(f"     Average concurrent: {peak_concurrent.get('avg_concurrent', 0):.1f}")
        print(f"     95th percentile: {peak_concurrent.get('p95_concurrent', 0)}")


def example_user_analysis(analyzer: CiscoCDRAnalyzer):
    """Demonstrate all user-based analysis functions"""
    print_section("4. USER-BASED ANALYSIS")
    
    # ===== User Listing =====
    print_subsection("4.1 User Listing")
    
    all_users = analyzer.users.get_all_users()
    internal_users = analyzer.users.get_internal_users()
    
    print(f"     Total unique users: {len(all_users):,}")
    print(f"     Internal extensions: {len(internal_users):,}")
    print(f"     Sample users: {', '.join(all_users[:5])}")
    
    # ===== Top Callers/Called =====
    print_subsection("4.2 Top Callers & Called Numbers")
    
    top_callers = analyzer.users.get_top_callers(10)
    print("     Top 10 Callers:")
    for i, (_, row) in enumerate(top_callers.iterrows(), 1):
        print(f"       {i:2d}. {row['caller']:15s} - {int(row['total_calls']):>5,} calls, "
              f"{row['answer_rate']:.1f}% answered, {int(row['total_duration']):>6,}s total")
    
    top_called = analyzer.users.get_top_called(10)
    print("\n     Top 10 Called Numbers:")
    for i, (_, row) in enumerate(top_called.iterrows(), 1):
        print(f"       {i:2d}. {row['called_number']:15s} - {int(row['total_calls']):>5,} calls")
    
    # ===== Top Call Pairs =====
    print_subsection("4.3 Top Call Pairs (Most Frequent Connections)")
    
    top_pairs = analyzer.users.get_top_call_pairs(5)
    if not top_pairs.empty:
        print("     Most frequent caller-called pairs:")
        for _, row in top_pairs.iterrows():
            print(f"       {row['user1']} ↔ {row['user2']}: {int(row['total_calls']):,} calls")
    
    # ===== User Statistics (detailed) =====
    print_subsection("4.4 Detailed User Statistics")
    
    if not top_callers.empty:
        sample_user = top_callers.iloc[0]['caller']
        user_stats = analyzer.users.get_user_statistics(sample_user)
        
        print(f"     Detailed stats for: {sample_user}")
        if 'error' not in user_stats:
            print(f"       Total calls: {user_stats['total_calls']:,}")
            print(f"       Outgoing: {user_stats['outgoing']['total']:,} "
                  f"({user_stats['outgoing']['answered']} answered, {user_stats['outgoing']['answer_rate']}%)")
            print(f"       Incoming: {user_stats['incoming']['total']:,} "
                  f"({user_stats['incoming']['answered']} answered, {user_stats['incoming']['answer_rate']}%)")
            print(f"       Total duration: {user_stats['total_duration_sec']:,}s")
            print(f"       Avg duration: {user_stats['avg_call_duration_sec']}s")
            print(f"       Devices: {', '.join(user_stats['devices_used'][:3])}")
    
    # ===== User Activity Pattern =====
    print_subsection("4.5 User Activity Pattern")
    
    if not top_callers.empty:
        sample_user = top_callers.iloc[0]['caller']
        activity = analyzer.users.get_user_activity_pattern(sample_user)
        
        if activity and 'error' not in activity:
            print(f"     Activity pattern for: {sample_user}")
            print(f"       Peak hour: {activity.get('peak_hour_label', 'N/A')}")
            print(f"       Peak day: {activity.get('peak_day', 'N/A')}")
            print(f"       Business hours: {activity.get('business_hours_pct', 0)}%")
            print(f"       After hours: {activity.get('after_hours_calls', 0)} calls")
            print(f"       Avg calls/day: {activity.get('avg_calls_per_day', 0):.1f}")
            print(f"       Active days: {activity.get('active_days', 0)}")
    
    # ===== User Call History =====
    print_subsection("4.6 User Call History")
    
    if not top_callers.empty:
        sample_user = top_callers.iloc[0]['caller']
        history = analyzer.users.get_user_call_history(sample_user, days=7)
        
        if not history.empty:
            print(f"     Recent call history for {sample_user} (last 7 days):")
            print(f"       Total calls: {len(history)}")
            print(f"       Inbound: {(history['direction'] == 'inbound').sum()}")
            print(f"       Outbound: {(history['direction'] == 'outbound').sum()}")
            print("\n       Last 5 calls:")
            for _, row in history.head(5).iterrows():
                direction = "→" if row['direction'] == 'outbound' else "←"
                print(f"         {row['dateTimeOrigination_dt']} {direction} {row['other_party']} "
                      f"({row['duration']}s, {'answered' if row['answered'] else 'missed'})")
    
    # ===== Connected Users =====
    print_subsection("4.7 Connected Users & Close Contacts")
    
    if not top_callers.empty:
        sample_user = top_callers.iloc[0]['caller']
        connected = analyzer.users.get_connected_users(sample_user)
        
        print(f"     {sample_user} has communicated with {len(connected)} unique numbers")
        
        close_contacts = analyzer.users.get_close_contacts(sample_user, top_n=5)
        if not close_contacts.empty:
            print(f"\n     Top 5 close contacts:")
            for _, row in close_contacts.iterrows():
                print(f"       {row['contact']}: {int(row['total_calls']):,} calls "
                      f"({int(row['outgoing_calls'])} out, {int(row['incoming_calls'])} in)")
    
    # ===== Records Between Users =====
    print_subsection("4.8 Calls Between Specific Users")
    
    if len(all_users) >= 2:
        user1, user2 = all_users[0], all_users[1]
        between = analyzer.users.get_records_between_users(user1, user2)
        
        print(f"     Calls between {user1} and {user2}: {len(between)}")
        if not between.empty:
            print(f"       Total duration: {between['duration'].sum():,}s")
            print(f"       Answered: {between['answered'].sum()}")
    
    # ===== Inactive Users =====
    print_subsection("4.9 Inactive Users Detection")
    
    # Check for users inactive for 7+ days
    inactive = analyzer.users.get_inactive_users(days_threshold=7, user_list=internal_users[:50])
    if not inactive.empty:
        print(f"     Users inactive for 7+ days: {len(inactive)}")
        print("     Sample inactive users:")
        for _, row in inactive.head(5).iterrows():
            print(f"       {row['user']}: {row.get('days_inactive', 'N/A')} days, "
                  f"last active: {row.get('last_activity', 'never')}")
    else:
        print("     No inactive users found (all users active within 7 days)")
    
    # ===== User Comparison =====
    print_subsection("4.10 Compare Multiple Users")
    
    if len(all_users) >= 3:
        users_to_compare = all_users[:3]
        comparison = analyzer.users.get_user_comparison(users_to_compare)
        
        if not comparison.empty:
            print(f"     Comparing {len(users_to_compare)} users:")
            print(f"     {'User':<15} {'Calls':>8} {'Out':>6} {'In':>6} {'Ans%':>6} {'Duration':>10}")
            print(f"     {'-'*55}")
            for _, row in comparison.iterrows():
                print(f"     {row['user']:<15} {row['total_calls']:>8,} "
                      f"{row['outgoing_calls']:>6,} {row['incoming_calls']:>6,} "
                      f"{row['answer_rate']:>5.1f}% {row['total_duration_sec']:>10,}s")
    
    # ===== Department Statistics =====
    print_subsection("4.11 Department Statistics")
    
    # Example department mapping (customize for your organization)
    dept_mapping = {
        'Sales': [ext for ext in internal_users[:5]],
        'Support': [ext for ext in internal_users[5:10]] if len(internal_users) > 5 else [],
        'Admin': [ext for ext in internal_users[10:15]] if len(internal_users) > 10 else [],
    }
    
    # Filter empty departments
    dept_mapping = {k: v for k, v in dept_mapping.items() if v}
    
    if dept_mapping:
        dept_stats = analyzer.users.get_department_stats(dept_mapping)
        if not dept_stats.empty:
            print("     Department Statistics:")
            for _, row in dept_stats.iterrows():
                print(f"       {row['department']}:")
                print(f"         Extensions: {row['extension_count']}")
                print(f"         Total calls: {row['total_calls']:,}")
                print(f"         Answer rate: {row['answer_rate']}%")
                print(f"         Calls/extension: {row['calls_per_extension']:.1f}")
    
    # ===== Inter-Department Calls =====
    if dept_mapping and len(dept_mapping) > 1:
        inter_dept = analyzer.users.get_inter_department_calls(dept_mapping)
        if not inter_dept.empty:
            print("\n     Inter-Department Call Matrix:")
            print(inter_dept.to_string())
    
    # ===== User Duration Trend =====
    print_subsection("4.12 User Call Duration Trend")
    
    if not top_callers.empty:
        sample_user = top_callers.iloc[0]['caller']
        duration_trend = analyzer.users.get_user_call_duration_trend(sample_user, period='daily')
        
        if not duration_trend.empty:
            print(f"     Duration trend for {sample_user} (last 5 days):")
            for _, row in duration_trend.tail(5).iterrows():
                print(f"       {row['date']}: {row['call_count']} calls, "
                      f"avg {row['avg_duration']:.0f}s, total {row['total_duration']:.0f}s")
    
    # ===== Missed Calls Analysis =====
    print_subsection("4.13 Missed Calls Analysis")
    
    missed_analysis = analyzer.users.get_missed_call_analysis()
    if missed_analysis.get('total_missed', 0) > 0:
        print(f"     Total missed calls: {missed_analysis['total_missed']:,}")
        print(f"     Business hours missed: {missed_analysis.get('business_hours_missed', 0):,}")
        print(f"     After hours missed: {missed_analysis.get('after_hours_missed', 0):,}")
        print(f"     Peak missed hour: {missed_analysis.get('peak_missed_hour', 'N/A')}:00")
        
        if missed_analysis.get('top_callers'):
            print("\n     Top callers with missed calls:")
            for caller, count in list(missed_analysis['top_callers'].items())[:5]:
                print(f"       {caller}: {count} missed")
    
    # ===== Extension Directory =====
    print_subsection("4.14 Extension Directory Mapping")
    
    directory = analyzer.users.get_extension_directory_mapping()
    if not directory.empty:
        print(f"     Total extensions mapped: {len(directory)}")
        print("\n     Sample extensions:")
        for _, row in directory.head(5).iterrows():
            devices = row['devices'][:2] if row['devices'] else []
            print(f"       {row['extension']}: {row['total_calls']} calls, "
                  f"devices: {', '.join(str(d) for d in devices)}")
    
    # ===== Connection Matrix =====
    print_subsection("4.15 User Connection Matrix")
    
    top_5_users = all_users[:5]
    matrix = analyzer.users.get_connection_matrix(users=top_5_users, min_calls=1)
    if not matrix.empty:
        print(f"     Connection matrix for top 5 users:")
        print(matrix.to_string())


def example_device_analysis(analyzer: CiscoCDRAnalyzer):
    """Demonstrate all device-based analysis functions"""
    print_section("5. DEVICE-BASED ANALYSIS")
    
    # ===== Device Listing =====
    print_subsection("5.1 Device Listing & Types")
    
    all_devices = analyzer.devices.get_all_devices()
    devices_by_type = analyzer.devices.get_devices_by_type()
    
    print(f"     Total unique devices: {len(all_devices)}")
    print("\n     Devices by type:")
    for device_type, devices in devices_by_type.items():
        print(f"       {device_type}: {len(devices)} devices")
        if len(devices) <= 3:
            for d in devices:
                print(f"         - {d}")
    
    # ===== Device Type Summary =====
    print_subsection("5.2 Device Type Summary Statistics")
    
    type_summary = analyzer.devices.get_device_type_summary()
    if not type_summary.empty:
        print(f"     {'Device Type':<20} {'Originated':>10} {'Received':>10} {'Ans Rate':>10}")
        print(f"     {'-'*55}")
        for _, row in type_summary.iterrows():
            print(f"     {row['device_type']:<20} {int(row['originated_calls']):>10,} "
                  f"{int(row['received_calls']):>10,} {row['answer_rate']:>9.1f}%")
    
    # ===== Device Summary =====
    print_subsection("5.3 Device Summary (Top 10 by calls)")
    
    device_summary = analyzer.devices.get_device_summary()
    if not device_summary.empty:
        print(f"     {'Device':<20} {'Type':<12} {'Calls':>8} {'Duration':>10} {'Rate':>6}")
        print(f"     {'-'*60}")
        for _, row in device_summary.head(10).iterrows():
            device_short = row['device'][:18] + '..' if len(row['device']) > 20 else row['device']
            print(f"     {device_short:<20} {row['device_type']:<12} "
                  f"{int(row['total_calls']):>8,} {int(row['total_duration']):>10,}s "
                  f"{row['answer_rate']:>5.1f}%")
    
    # ===== Device Statistics =====
    print_subsection("5.4 Detailed Device Statistics")
    
    if not device_summary.empty:
        sample_device = device_summary.iloc[0]['device']
        device_stats = analyzer.devices.get_device_statistics(sample_device)
        
        if 'error' not in device_stats:
            print(f"     Device: {device_stats['device']}")
            print(f"       Type: {device_stats['device_type']}")
            print(f"       Total calls: {device_stats['total_calls']:,}")
            print(f"       Originated: {device_stats['originated_calls']:,}")
            print(f"       Received: {device_stats['received_calls']:,}")
            print(f"       Answer rate: {device_stats['answer_rate']}%")
            print(f"       Total duration: {device_stats['total_duration_sec']:,}s")
            print(f"       Avg duration: {device_stats['avg_duration_sec']}s")
            print(f"       Users: {device_stats['user_count']} ({', '.join(device_stats['associated_users'][:3])}...)")
            print(f"       Active days: {device_stats.get('active_days', 'N/A')}")
    
    # ===== Device Utilization =====
    print_subsection("5.5 Device Utilization Over Time")
    
    if not device_summary.empty:
        sample_device = device_summary.iloc[0]['device']
        utilization = analyzer.devices.get_device_utilization(sample_device, period='daily')
        
        if not utilization.empty:
            print(f"     Daily utilization for {sample_device[:30]}...")
            print(f"     Last 5 days:")
            for _, row in utilization.tail(5).iterrows():
                print(f"       {row['date']}: {row['total_calls']} calls, "
                      f"{row['total_duration']:.0f}s, {row['answer_rate']:.1f}%")
    
    # ===== Device Hourly Usage =====
    print_subsection("5.6 Device Hourly Usage Pattern")
    
    if not device_summary.empty:
        sample_device = device_summary.iloc[0]['device']
        hourly = analyzer.devices.get_device_hourly_usage(sample_device)
        
        if not hourly.empty:
            peak_hour = hourly.loc[hourly['total_calls'].idxmax()]
            print(f"     Hourly usage for {sample_device[:30]}...")
            print(f"       Peak hour: {peak_hour['hour_label']} ({int(peak_hour['total_calls'])} calls)")
            print(f"       Total daily calls: {hourly['total_calls'].sum():.0f}")
    
    # ===== Device Quality Report =====
    print_subsection("5.7 Device Quality Report")
    
    if analyzer.cmr_df is not None and not device_summary.empty:
        sample_device = device_summary.iloc[0]['device']
        quality = analyzer.devices.get_device_quality_report(sample_device)
        
        if 'error' not in quality:
            print(f"     Quality report for {sample_device[:30]}...")
            print(f"       Records: {quality['total_records']}")
            print(f"       As Originator:")
            print(f"         Avg jitter: {quality['as_originator']['avg_jitter']:.2f}ms")
            print(f"         Avg latency: {quality['as_originator']['avg_latency']:.2f}ms")
            print(f"         Packets lost: {quality['as_originator']['total_packets_lost']:,}")
            if 'avg_mos' in quality:
                print(f"       Avg MOS: {quality['avg_mos']:.2f}")
    
    # ===== Compare Device Quality =====
    print_subsection("5.8 Compare Device Quality")
    
    if analyzer.cmr_df is not None and len(all_devices) >= 3:
        devices_to_compare = all_devices[:5]
        comparison = analyzer.devices.compare_device_quality(devices_to_compare)
        
        if not comparison.empty:
            print("     Quality comparison:")
            for _, row in comparison.iterrows():
                if row.get('status') != 'no_data':
                    print(f"       {row['device'][:25]:<25}: "
                          f"jitter={row.get('avg_jitter_orig', 0):.1f}ms, "
                          f"latency={row.get('avg_latency_orig', 0):.1f}ms")
    
    # ===== Device Health Status =====
    print_subsection("5.9 Device Health Status")
    
    if analyzer.cmr_df is not None:
        health = analyzer.devices.get_device_health_status()
        
        if not health.empty:
            status_counts = health['status'].value_counts()
            print("     Device health overview:")
            for status, count in status_counts.items():
                emoji = "✅" if status == 'healthy' else "⚠️" if status == 'warning' else "❌"
                print(f"       {emoji} {status}: {count} devices")
            
            # Show problematic devices
            critical = health[health['status'] == 'critical']
            if not critical.empty:
                print("\n     Critical devices:")
                for _, row in critical.head(5).iterrows():
                    print(f"       {row['device'][:25]}: {row['issues']}")
    
    # ===== Device Registration Status =====
    print_subsection("5.10 Device Registration Status (Activity-based)")
    
    reg_status = analyzer.devices.get_device_registration_status(inactive_hours=24)
    if not reg_status.empty:
        online = (reg_status['status'] == 'online').sum()
        offline = (reg_status['status'] == 'offline').sum()
        
        print(f"     Online (active in last 24h): {online}")
        print(f"     Offline (inactive 24h+): {offline}")
        
        if offline > 0:
            print("\n     Recently offline devices:")
            offline_devices = reg_status[reg_status['status'] == 'offline'].head(5)
            for _, row in offline_devices.iterrows():
                print(f"       {row['device'][:25]}: {row['hours_inactive']:.1f}h inactive")
    
    # ===== Trunk Analysis =====
    print_subsection("5.11 Trunk/Gateway Analysis")
    
    trunks = analyzer.devices.get_trunk_devices()
    print(f"     Trunk/Gateway devices found: {len(trunks)}")
    
    if trunks:
        trunk_util = analyzer.devices.get_trunk_utilization()
        if not trunk_util.empty:
            print("\n     Trunk utilization:")
            for _, row in trunk_util.iterrows():
                print(f"       {row['trunk'][:30]}:")
                print(f"         Total: {int(row['total_calls']):,} (in: {int(row['inbound_calls']):,}, "
                      f"out: {int(row['outbound_calls']):,})")
                print(f"         Answer rate: {row['answer_rate']:.1f}%")


def example_quality_analysis(analyzer: CiscoCDRAnalyzer):
    """Demonstrate all quality analysis functions"""
    print_section("6. QUALITY ANALYSIS")
    
    if analyzer.cmr_df is None:
        print("  ⚠️ CMR data not loaded - quality analysis requires CMR data")
        return
    
    # ===== Quality Summary =====
    print_subsection("6.1 Quality Summary")
    
    quality_summary = analyzer.get_quality_summary()
    
    print("     Quality Metrics Overview:")
    print(f"       Records analyzed: {quality_summary['total_records']:,}")
    
    metrics = quality_summary.get('metrics', {})
    print("\n     Jitter (ms):")
    print(f"       Origin:      avg={metrics['jitter']['orig_avg']:.2f}, max={metrics['jitter']['orig_max']:.2f}")
    print(f"       Destination: avg={metrics['jitter']['dest_avg']:.2f}, max={metrics['jitter']['dest_max']:.2f}")
    
    print("\n     Latency (ms):")
    print(f"       Origin:      avg={metrics['latency']['orig_avg']:.2f}, max={metrics['latency']['orig_max']:.2f}")
    print(f"       Destination: avg={metrics['latency']['dest_avg']:.2f}, max={metrics['latency']['dest_max']:.2f}")
    
    print("\n     Packet Loss:")
    print(f"       Origin:      {metrics['packet_loss']['orig_total']:,} packets ({metrics['packet_loss']['orig_avg_pct']:.4f}%)")
    print(f"       Destination: {metrics['packet_loss']['dest_total']:,} packets ({metrics['packet_loss']['dest_avg_pct']:.4f}%)")
    
    if 'mos' in quality_summary:
        print(f"\n     MOS Score:")
        print(f"       Average: {quality_summary['mos']['average']:.2f}")
        print(f"       Min: {quality_summary['mos']['min']:.2f}")
        print(f"       Max: {quality_summary['mos']['max']:.2f}")
    
    # ===== MOS Distribution =====
    print_subsection("6.2 MOS Score Distribution")
    
    mos_dist = analyzer.quality.get_mos_distribution()
    if 'error' not in mos_dist:
        print(f"     Total calls: {mos_dist['total_calls']:,}")
        print(f"     Average MOS: {mos_dist['average']:.2f}")
        print(f"     Median MOS: {mos_dist['median']:.2f}")
        print(f"     Std Dev: {mos_dist['std_dev']:.2f}")
        
        print("\n     Quality breakdown:")
        for quality_level, count in mos_dist.get('quality_breakdown', {}).items():
            pct = count / mos_dist['total_calls'] * 100
            bar = "█" * int(pct / 2)
            print(f"       {quality_level:<20}: {count:>6,} ({pct:>5.1f}%) {bar}")
        
        print("\n     Percentiles:")
        for p, val in mos_dist.get('percentiles', {}).items():
            print(f"       {p}: {val:.2f}")
    
    # ===== Quality Trend =====
    print_subsection("6.3 Quality Trend Over Time")
    
    # MOS trend
    mos_trend = analyzer.quality.get_quality_trend_over_time(period='daily', metric='mos')
    if not mos_trend.empty:
        print("     Daily MOS trend (last 7 days):")
        for _, row in mos_trend.tail(7).iterrows():
            mos_val = row.get('avg_mos_mean', 0)
            status = "✅" if mos_val >= 4.0 else "⚠️" if mos_val >= 3.5 else "❌"
            print(f"       {row['period']}: {mos_val:.2f} {status}")
    
    # Jitter trend
    jitter_trend = analyzer.quality.get_quality_trend_over_time(period='daily', metric='jitter')
    if not jitter_trend.empty:
        print("\n     Daily jitter trend (last 7 days):")
        for _, row in jitter_trend.tail(7).iterrows():
            jitter_val = row.get('origjitter_mean', 0)
            status = "✅" if jitter_val < 20 else "⚠️" if jitter_val < 30 else "❌"
            print(f"       {row['period']}: {jitter_val:.1f}ms {status}")
    
    # ===== Quality by Hour =====
    print_subsection("6.4 Quality by Hour of Day")
    
    hourly_quality = analyzer.quality.get_quality_by_hour()
    if not hourly_quality.empty and 'avg_mos' in hourly_quality.columns:
        best_hour = hourly_quality.loc[hourly_quality['avg_mos'].idxmax()]
        worst_hour = hourly_quality.loc[hourly_quality['avg_mos'].idxmin()]
        
        print(f"     Best quality hour:  {best_hour['hour_label']} (MOS: {best_hour['avg_mos']:.2f})")
        print(f"     Worst quality hour: {worst_hour['hour_label']} (MOS: {worst_hour['avg_mos']:.2f})")
    
    # ===== Quality by Codec =====
    print_subsection("6.5 Quality by Codec")
    
    codec_quality = analyzer.quality.get_quality_by_codec()
    if not codec_quality.empty:
        print("     Quality metrics by codec:")
        for _, row in codec_quality.head(5).iterrows():
            mos = row.get('avg_mos', 'N/A')
            mos_str = f"{mos:.2f}" if isinstance(mos, float) else mos
            print(f"       {row['codec_name']:<15}: {row['call_count']:>5} calls, MOS: {mos_str}")
    
    # Codec usage stats
    codec_usage = analyzer.quality.get_codec_usage_stats()
    if not codec_usage.empty:
        print("\n     Codec usage distribution:")
        for _, row in codec_usage.head(5).iterrows():
            print(f"       {row['codec']:<15}: {row['count']:>6,} ({row['percentage']:.1f}%)")
    
    # ===== Quality by Route =====
    print_subsection("6.6 Quality by Route/Trunk")
    
    route_quality = analyzer.quality.get_quality_by_route()
    if not route_quality.empty:
        print("     Quality by route:")
        for _, row in route_quality.head(5).iterrows():
            route = row['route'][:25] + '..' if len(row['route']) > 25 else row['route']
            mos = row.get('avg_mos', 'N/A')
            mos_str = f"{mos:.2f}" if isinstance(mos, float) else 'N/A'
            print(f"       {route:<27}: {int(row['call_count']):>5} calls, MOS: {mos_str}")
    
    # ===== Packet Loss Analysis =====
    print_subsection("6.7 Packet Loss Analysis")
    
    pl_analysis = analyzer.quality.get_packet_loss_analysis()
    if 'error' not in pl_analysis:
        print(f"     Total packets sent: {pl_analysis['total_packets_sent']:,}")
        print(f"     Total packets lost: {pl_analysis['total_packets_lost']:,}")
        print(f"     Overall loss rate: {pl_analysis['overall_loss_pct']:.4f}%")
        print(f"     Calls with any loss: {pl_analysis['calls_with_loss']:,} ({pl_analysis['calls_with_loss_pct']:.1f}%)")
        print(f"     High loss calls (>1%): {pl_analysis['high_loss_calls']:,} ({pl_analysis['high_loss_calls_pct']:.1f}%)")
        
        if 'loss_distribution' in pl_analysis:
            print("\n     Loss distribution:")
            for category, count in pl_analysis['loss_distribution'].items():
                print(f"       {category}: {count:,}")
    
    # ===== Jitter Analysis =====
    print_subsection("6.8 Jitter Analysis")
    
    jitter_analysis = analyzer.quality.get_jitter_analysis()
    if 'error' not in jitter_analysis:
        print("     Origin jitter:")
        print(f"       Mean: {jitter_analysis['origin']['mean']:.2f}ms")
        print(f"       Median: {jitter_analysis['origin']['median']:.2f}ms")
        print(f"       Max: {jitter_analysis['origin']['max']:.2f}ms")
        print(f"       P95: {jitter_analysis['origin']['p95']:.2f}ms")
        
        print("\n     Jitter thresholds:")
        for threshold, count in jitter_analysis['thresholds'].items():
            print(f"       {threshold}: {count:,}")
    
    # ===== Latency Analysis =====
    print_subsection("6.9 Latency Analysis")
    
    latency_analysis = analyzer.quality.get_latency_analysis()
    if 'error' not in latency_analysis:
        print("     Origin latency:")
        print(f"       Mean: {latency_analysis['origin']['mean']:.2f}ms")
        print(f"       Median: {latency_analysis['origin']['median']:.2f}ms")
        print(f"       Max: {latency_analysis['origin']['max']:.2f}ms")
        print(f"       P95: {latency_analysis['origin']['p95']:.2f}ms")
        
        print("\n     Latency thresholds:")
        for threshold, count in latency_analysis['thresholds'].items():
            print(f"       {threshold}: {count:,}")
    
    # ===== Bandwidth Utilization =====
    print_subsection("6.10 Bandwidth Utilization")
    
    bandwidth = analyzer.quality.get_bandwidth_utilization()
    if 'error' not in bandwidth:
        print(f"     Total packets: {bandwidth['total_packets']:,}")
        print(f"     Total data: {bandwidth['total_data_mb']:.2f} MB ({bandwidth['total_data_gb']:.3f} GB)")
        print(f"     Avg bandwidth: {bandwidth['avg_bandwidth_mbph']:.2f} MB/hour")
    
    # ===== Network Issues =====
    print_subsection("6.11 Identified Network Issues")
    
    issues = analyzer.quality.identify_network_issues()
    if not issues.empty:
        print(f"     {len(issues)} potential issues identified:")
        for _, row in issues.iterrows():
            emoji = "❌" if row['severity'] == 'critical' else "⚠️" if row['severity'] == 'warning' else "ℹ️"
            print(f"       {emoji} {row['issue_type']}: {row['description']}")
            print(f"          Recommendation: {row['recommendation']}")
    else:
        print("     ✅ No significant network issues detected")
    
    # ===== SLA Compliance =====
    print_subsection("6.12 SLA Compliance Check")
    
    sla = analyzer.quality.get_quality_sla_compliance()
    if 'error' not in sla:
        print(f"     Calls analyzed: {sla['total_calls_analyzed']:,}")
        print(f"     Overall status: {sla['summary']['status']}")
        print(f"     Passing metrics: {sla['summary']['passing_metrics']}/{sla['summary']['total_metrics']}")
        
        print("\n     Metric compliance:")
        for metric_name, metric_data in sla['metrics'].items():
            status_emoji = "✅" if metric_data['status'] == 'pass' else "❌"
            print(f"       {status_emoji} {metric_name}: {metric_data['compliance_pct']:.1f}% compliant "
                  f"(threshold: {metric_data['threshold']})")
    
    # ===== Quality Issues =====
    print_subsection("6.13 Calls with Quality Issues")
    
    quality_issues = analyzer.quality.get_quality_issues()
    if not quality_issues.empty:
        print(f"     Total calls with issues: {len(quality_issues):,}")
        
        # Count by issue type
        if 'issue_types' in quality_issues.columns:
            print("\n     Issues breakdown:")
            for issue_type in ['jitter', 'latency', 'packet_loss']:
                count = quality_issues['issue_types'].str.contains(issue_type).sum()
                print(f"       {issue_type}: {count:,}")
    
    # ===== Worst Quality Calls =====
    print_subsection("6.14 Worst Quality Calls")
    
    worst_calls = analyzer.quality.get_worst_quality_calls(n=5, metric='mos')
    if not worst_calls.empty:
        print("     5 worst calls by MOS:")
        for i, (_, row) in enumerate(worst_calls.iterrows(), 1):
            mos = row.get('avg_mos', 'N/A')
            print(f"       {i}. MOS: {mos:.2f} - {row.get('callingPartyNumber', 'N/A')} → "
                  f"{row.get('finalCalledPartyNumber', 'N/A')}")


def example_hunt_group_analysis(analyzer: CiscoCDRAnalyzer):
    """Demonstrate all hunt group analysis functions"""
    print_section("7. HUNT GROUP & QUEUE ANALYSIS")
    
    # ===== Hunt Group Listing =====
    print_subsection("7.1 Hunt Group Discovery")
    
    hunt_groups = analyzer.hunt_groups.get_all_hunt_groups()
    
    if not hunt_groups:
        print("     No hunt groups found in CDR data")
        print("     (Hunt groups are identified by huntPilotDN column)")
        return
    
    print(f"     Hunt groups found: {len(hunt_groups)}")
    for hg in hunt_groups[:10]:
        print(f"       • {hg}")
    
    # ===== Hunt Group Summary =====
    print_subsection("7.2 Hunt Group Summary")
    
    hg_summary = analyzer.hunt_groups.get_hunt_group_summary()
    if not hg_summary.empty:
        print(f"     {'Hunt DN':<15} {'Calls':>8} {'Answered':>10} {'Abandoned':>10} {'Ans%':>8}")
        print(f"     {'-'*55}")
        for _, row in hg_summary.iterrows():
            print(f"     {row['hunt_dn']:<15} {row['total_calls']:>8,} "
                  f"{row['answered_calls']:>10,} {row['abandoned_calls']:>10,} "
                  f"{row['answer_rate']:>7.1f}%")
    
    # ===== Hunt Group Statistics =====
    print_subsection("7.3 Detailed Hunt Group Statistics")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        hg_stats = analyzer.hunt_groups.get_hunt_group_stats(sample_hg)
        
        if 'error' not in hg_stats:
            print(f"     Hunt Group: {hg_stats['hunt_dn']}")
            print(f"       Total calls: {hg_stats['total_calls']:,}")
            print(f"       Answered: {hg_stats['answered_calls']:,}")
            print(f"       Abandoned: {hg_stats['abandoned_calls']:,}")
            print(f"       Answer rate: {hg_stats['answer_rate']}%")
            print(f"       Abandonment rate: {hg_stats['abandonment_rate']}%")
            print(f"       Avg duration: {hg_stats['avg_duration_sec']}s")
            print(f"       Unique members: {hg_stats.get('unique_members', 'N/A')}")
            print(f"       Avg calls/day: {hg_stats.get('avg_calls_per_day', 'N/A')}")
            
            if 'wait_time' in hg_stats:
                print(f"\n       Wait time analysis:")
                print(f"         Average: {hg_stats['wait_time']['avg_sec']}s")
                print(f"         Median: {hg_stats['wait_time']['median_sec']}s")
                print(f"         P90: {hg_stats['wait_time']['p90_sec']}s")
                print(f"         Max: {hg_stats['wait_time']['max_sec']}s")
    
    # ===== Member Statistics =====
    print_subsection("7.4 Hunt Group Member Statistics")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        member_stats = analyzer.hunt_groups.get_hunt_group_member_stats(sample_hg)
        
        if not member_stats.empty:
            print(f"     Members of {sample_hg}:")
            print(f"     {'Device':<25} {'Calls':>8} {'Handle%':>10} {'Avg Dur':>10}")
            print(f"     {'-'*55}")
            for _, row in member_stats.head(10).iterrows():
                device = row['device'][:23] + '..' if len(row['device']) > 25 else row['device']
                print(f"     {device:<25} {int(row['calls_handled']):>8,} "
                      f"{row['handle_pct']:>9.1f}% {row['avg_duration']:>9.1f}s")
    
    # ===== Member Performance =====
    print_subsection("7.5 Member Performance Comparison")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        performance = analyzer.hunt_groups.get_member_performance_comparison(sample_hg)
        
        if 'error' not in performance:
            print(f"     Performance comparison for {sample_hg}:")
            print(f"       Total members: {performance['total_members']}")
            print(f"       Top performer: {performance['top_performer']['device'][:20]}... "
                  f"({performance['top_performer']['calls_handled']} calls)")
            print(f"\n       Workload distribution:")
            print(f"         Mean calls: {performance['workload_distribution']['mean_calls']:.1f}")
            print(f"         Std dev: {performance['workload_distribution']['std_dev']:.1f}")
            print(f"         Min: {performance['workload_distribution']['min_calls']}")
            print(f"         Max: {performance['workload_distribution']['max_calls']}")
    
    # ===== Queue Wait Times =====
    print_subsection("7.6 Queue Wait Time Analysis")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        wait_times = analyzer.hunt_groups.get_queue_wait_times(sample_hg)
        
        if 'error' not in wait_times:
            print(f"     Wait time analysis for {sample_hg}:")
            print(f"       Total calls: {wait_times['total_calls']:,}")
            
            overall = wait_times['overall']
            print(f"\n       Overall wait time:")
            print(f"         Mean: {overall['mean']}s")
            print(f"         Median: {overall['median']}s")
            print(f"         P90: {overall['p90']}s")
            print(f"         P95: {overall['p95']}s")
            print(f"         Max: {overall['max']}s")
            
            print(f"\n       Wait time distribution:")
            for bucket, count in wait_times['distribution'].items():
                pct = count / wait_times['total_calls'] * 100
                bar = "█" * int(pct / 2)
                print(f"         {bucket:<12}: {count:>5} ({pct:>5.1f}%) {bar}")
            
            print(f"\n       Service levels:")
            for key, val in wait_times.items():
                if key.startswith('service_level_'):
                    threshold = key.replace('service_level_', '').replace('s', '')
                    status = "✅" if val >= 80 else "⚠️" if val >= 60 else "❌"
                    print(f"         {status} Within {threshold}s: {val:.1f}%")
    
    # ===== Abandoned Calls =====
    print_subsection("7.7 Abandoned Calls Analysis")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        abandoned = analyzer.hunt_groups.get_abandoned_calls_analysis(sample_hg)
        
        if abandoned.get('abandoned_calls', 0) > 0:
            print(f"     Abandoned calls for {sample_hg}:")
            print(f"       Total calls: {abandoned['total_calls']:,}")
            print(f"       Abandoned: {abandoned['abandoned_calls']:,}")
            print(f"       Abandonment rate: {abandoned['abandonment_rate']:.1f}%")
            print(f"       Unique abandoners: {abandoned.get('unique_abandoners', 'N/A')}")
            
            if 'wait_before_abandon' in abandoned:
                print(f"\n       Wait before abandon:")
                print(f"         Mean: {abandoned['wait_before_abandon']['mean']}s")
                print(f"         Median: {abandoned['wait_before_abandon']['median']}s")
            
            print(f"\n       Short abandons (<5s): {abandoned.get('short_abandons', 0)} "
                  f"({abandoned.get('short_abandon_pct', 0):.1f}%)")
        else:
            print("     No abandoned calls found")
    
    # ===== Overflow Analysis =====
    print_subsection("7.8 Hunt Group Overflow Analysis")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        overflow = analyzer.hunt_groups.get_hunt_overflow_analysis(sample_hg)
        
        if 'error' not in overflow:
            print(f"     Overflow analysis for {sample_hg}:")
            print(f"       Total calls: {overflow['total_hunt_calls']:,}")
            print(f"       Answered: {overflow['answered']:,}")
            print(f"       Unanswered: {overflow['unanswered']:,}")
            print(f"       Long wait (>60s): {overflow.get('long_wait_calls', 0):,} "
                  f"({overflow.get('long_wait_pct', 0):.1f}%)")
            print(f"       Very long wait (>120s): {overflow.get('very_long_wait_calls', 0):,}")
    
    # ===== Service Level Trend =====
    print_subsection("7.9 Service Level Trend")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        sl_trend = analyzer.hunt_groups.get_service_level_trend(sample_hg, threshold_seconds=20, period='daily')
        
        if not sl_trend.empty:
            print(f"     Service level trend (20s threshold) for {sample_hg}:")
            for _, row in sl_trend.tail(5).iterrows():
                status = "✅" if row['service_level'] >= 80 else "⚠️" if row['service_level'] >= 60 else "❌"
                print(f"       {row['date']}: {row['service_level']:.1f}% {status} "
                      f"({int(row['within_threshold'])}/{int(row['total_answered'])})")
    
    # ===== First Call Resolution =====
    print_subsection("7.10 First Call Resolution (Estimated)")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        fcr = analyzer.hunt_groups.get_first_call_resolution(sample_hg, callback_window_minutes=60)
        
        if 'error' not in fcr:
            print(f"     FCR analysis for {sample_hg}:")
            print(f"       Calls analyzed: {fcr['calls_analyzed']:,}")
            print(f"       Estimated callbacks: {fcr['estimated_callbacks']:,}")
            print(f"       Estimated FCR rate: {fcr['estimated_fcr_rate']:.1f}%")
            print(f"       Note: {fcr['note']}")
    
    # ===== Hunt Group KPIs =====
    print_subsection("7.11 Hunt Group KPIs")
    
    if hunt_groups:
        sample_hg = hunt_groups[0]
        kpis = analyzer.hunt_groups.get_hunt_group_kpis(sample_hg, service_level_threshold=20)
        
        if 'error' not in kpis:
            print(f"     KPIs for {sample_hg}:")
            print(f"       Answer rate: {kpis['answer_rate']}%")
            print(f"       Abandonment rate: {kpis['abandonment_rate']}%")
            if kpis['asa_seconds']:
                print(f"       ASA (Avg Speed of Answer): {kpis['asa_seconds']}s")
            if kpis['aht_seconds']:
                print(f"       AHT (Avg Handle Time): {kpis['aht_seconds']}s")
            if 'service_level' in kpis:
                print(f"       Service Level ({kpis['service_level']['threshold_seconds']}s): "
                      f"{kpis['service_level']['service_level_pct']}%")
            if kpis.get('longest_wait_seconds'):
                print(f"       Longest wait: {kpis['longest_wait_seconds']}s")


def example_security_analysis(analyzer: CiscoCDRAnalyzer):
    """Demonstrate all security analysis functions"""
    print_section("8. SECURITY & FRAUD ANALYSIS")
    
    # ===== Toll Fraud Detection =====
    print_subsection("8.1 Toll Fraud Detection")
    
    fraud = analyzer.security.detect_toll_fraud()
    
    print(f"     Calls analyzed: {fraud['total_calls_analyzed']:,}")
    print(f"     International calls: {fraud['international_calls']:,}")
    print(f"     High-risk calls: {fraud['high_risk_calls']:,}")
    print(f"     Risk level: {fraud['risk_level'].upper()}")
    print(f"     Alerts generated: {fraud['alert_count']}")
    
    if fraud['alerts']:
        print("\n     Alerts:")
        for alert in fraud['alerts'][:5]:
            severity_emoji = "❌" if alert['severity'] == 'high' else "⚠️" if alert['severity'] == 'medium' else "ℹ️"
            print(f"       {severity_emoji} [{alert['severity'].upper()}] {alert['type']}")
            print(f"          {alert['description']}")
    
    # ===== After-Hours Anomalies =====
    print_subsection("8.2 After-Hours Anomaly Detection")
    
    after_hours = analyzer.security.detect_after_hours_anomalies(threshold_calls=10)
    
    print(f"     Total after-hours calls: {after_hours['total_after_hours_calls']:,}")
    print(f"     After-hours percentage: {after_hours['after_hours_pct']:.1f}%")
    print(f"     Outbound after-hours: {after_hours['outbound_after_hours']:,}")
    print(f"     Anomalies detected: {after_hours['anomaly_count']}")
    
    if after_hours.get('anomalies'):
        print("\n     Anomalies:")
        for anomaly in after_hours['anomalies'][:5]:
            severity_emoji = "❌" if anomaly['severity'] == 'high' else "⚠️" if anomaly['severity'] == 'medium' else "ℹ️"
            print(f"       {severity_emoji} {anomaly['type']}: {anomaly['description']}")
    
    # ===== Unauthorized Extensions =====
    print_subsection("8.3 Unauthorized Extensions Check")
    
    # Get internal users as authorized list
    internal_users = analyzer.users.get_internal_users()
    
    unauthorized = analyzer.security.get_unauthorized_extensions(
        authorized_extensions=internal_users[:100] if internal_users else None
    )
    
    if unauthorized.get('unauthorized_extensions_found', 0) > 0:
        print(f"     Unauthorized extensions found: {unauthorized['unauthorized_extensions_found']}")
        print(f"     Unauthorized calls: {unauthorized['unauthorized_calls']:,} "
              f"({unauthorized['unauthorized_calls_pct']:.1f}%)")
        
        if unauthorized.get('extensions'):
            print("\n     Top unauthorized extensions:")
            for ext in unauthorized['extensions'][:5]:
                print(f"       {ext['extension']}: {ext['total_calls']} calls, "
                      f"device: {ext.get('device', 'N/A')[:30]}")
    else:
        print("     ✅ No unauthorized extensions detected")
    
    # ===== Long Duration Calls =====
    print_subsection("8.4 Long Duration Call Analysis")
    
    long_calls = analyzer.security.get_long_duration_calls(threshold_seconds=3600)
    
    if not long_calls.empty:
        print(f"     Calls over 1 hour: {len(long_calls)}")
        print("\n     Longest calls:")
        for _, row in long_calls.head(5).iterrows():
            print(f"       {row['duration_formatted']}: {row['callingPartyNumber']} → "
                  f"{row['finalCalledPartyNumber']} ({row['call_type']})")
    else:
        print("     No calls exceeding 1 hour threshold")
    
    # ===== High Frequency Callers =====
    print_subsection("8.5 High Frequency Caller Detection")
    
    high_freq = analyzer.security.get_high_frequency_callers(calls_per_hour_threshold=30)
    
    if high_freq.get('high_frequency_instances', 0) > 0:
        print(f"     High frequency instances: {high_freq['high_frequency_instances']}")
        print(f"     Suspicious callers: {high_freq['unique_suspicious_callers']}")
        print(f"     Severity: {high_freq['severity']}")
        
        if high_freq.get('callers'):
            print("\n     Top high-frequency callers:")
            for caller in high_freq['callers'][:5]:
                print(f"       {caller['caller']}: max {caller['max_calls_in_window']} calls/hour, "
                      f"{caller['num_high_freq_windows']} occurrences")
    else:
        print("     ✅ No high-frequency callers detected")
    
    # ===== Blocked Calls =====
    print_subsection("8.6 Blocked/Rejected Calls Report")
    
    blocked = analyzer.security.get_blocked_calls_report()
    
    if blocked.get('blocked_calls', 0) > 0:
        print(f"     Blocked calls: {blocked['total_blocked_calls']:,} ({blocked['blocked_pct']:.1f}%)")
        
        if blocked.get('by_cause_code'):
            print("\n     By cause code:")
            for code, count in list(blocked['by_cause_code'].items())[:5]:
                print(f"       Code {code}: {count}")
        
        if blocked.get('top_blocked_callers'):
            print("\n     Top blocked callers:")
            for caller in blocked['top_blocked_callers'][:5]:
                print(f"       {caller['caller']}: {caller['blocked_attempts']} attempts")
    else:
        print("     No blocked calls detected (or cause codes not available)")
    
    # ===== Compliance Report =====
    print_subsection("8.7 Compliance Check")
    
    compliance_rules = {
        'max_call_duration_sec': 7200,
        'blocked_prefixes': ['900', '976'],
        'require_business_hours': False,
        'max_calls_per_user_per_day': 200,
    }
    
    compliance = analyzer.security.get_compliance_report(rules=compliance_rules)
    
    print(f"     Compliance Status: {compliance['status']}")
    print(f"     Rules checked: {len(compliance['rules_checked'])}")
    print(f"     Violations: {compliance['violation_count']}")
    print(f"     Compliance rate: {compliance['compliance_rate']:.1f}%")
    
    if compliance.get('violations'):
        print("\n     Violations:")
        for v in compliance['violations']:
            print(f"       ❌ {v['rule']}: {v['details']}")
    
    # ===== User Audit =====
    print_subsection("8.8 User Activity Audit")
    
    top_callers = analyzer.users.get_top_callers(1)
    if not top_callers.empty:
        sample_user = top_callers.iloc[0]['caller']
        audit = analyzer.security.audit_user_activity(sample_user, days=30)
        
        if 'error' not in audit:
            print(f"     Audit for: {audit['user']}")
            print(f"       Period: {audit['audit_period']['start']} to {audit['audit_period']['end']}")
            print(f"       Total calls: {audit['summary']['total_calls']:,}")
            print(f"       Outgoing: {audit['summary']['outgoing_calls']:,}")
            print(f"       Incoming: {audit['summary']['incoming_calls']:,}")
            print(f"       Duration: {audit['summary']['total_duration_sec']:,}s")
            
            if 'business_hours_compliance' in audit:
                print(f"\n       Business hours compliance:")
                print(f"         Business hours: {audit['business_hours_compliance']['business_hours_calls']}")
                print(f"         After hours: {audit['business_hours_compliance']['after_hours_calls']}")
            
            print(f"\n       Risk level: {audit['risk_level'].upper()}")
            
            if audit.get('concerns'):
                print("       Concerns:")
                for concern in audit['concerns']:
                    print(f"         ⚠️ {concern['type']}: {concern['detail']}")
    
    # ===== Security Summary =====
    print_subsection("8.9 Overall Security Summary")
    
    security_summary = analyzer.security.get_security_summary()
    
    risk_emoji = "🔴" if security_summary['overall_risk_level'] == 'HIGH' else \
                 "🟡" if security_summary['overall_risk_level'] == 'MEDIUM' else "🟢"
    
    print(f"     {risk_emoji} Overall Risk Level: {security_summary['overall_risk_level']}")
    print(f"     Total alerts: {security_summary['total_alerts']}")
    print(f"       High severity: {security_summary['high_severity_alerts']}")
    print(f"       Medium severity: {security_summary['medium_severity_alerts']}")
    print(f"       Low severity: {security_summary['low_severity_alerts']}")
    
    print("\n     Recommendations:")
    for rec in security_summary['recommendations']:
        print(f"       • {rec}")


def example_visualizations(analyzer: CiscoCDRAnalyzer, output_dir: str):
    """Demonstrate visualization capabilities"""
    print_section("9. VISUALIZATION GENERATION")
    
    charts_dir = os.path.join(output_dir, 'charts')
    os.makedirs(charts_dir, exist_ok=True)
    
    # Import visualization modules
    from cisco_cdr_analyzer.visualization.charts import ChartGenerator
    from cisco_cdr_analyzer.visualization.heatmaps import HeatmapGenerator
    
    chart_gen = ChartGenerator(analyzer)
    heatmap_gen = HeatmapGenerator(analyzer)
    
    print("  📊 Generating static charts...")
    
    # ===== Basic Charts =====
    print_subsection("9.1 Basic Charts")
    
    # Calls by hour
    fig = chart_gen.plot_calls_by_hour()
    if fig:
        path = os.path.join(charts_dir, 'calls_by_hour.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: calls_by_hour.png")
        import matplotlib.pyplot as plt
        plt.close(fig)
    
    # Daily trend
    fig = chart_gen.plot_daily_trend(days=30)
    if fig:
        path = os.path.join(charts_dir, 'daily_trend.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: daily_trend.png")
        plt.close(fig)
    
    # Weekly comparison
        # Weekly comparison
    fig = chart_gen.plot_weekly_comparison(weeks=8)
    if fig:
        path = os.path.join(charts_dir, 'weekly_comparison.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: weekly_comparison.png")
        plt.close(fig)
    
    # Monthly comparison
    fig = chart_gen.plot_monthly_comparison(months=12)
    if fig:
        path = os.path.join(charts_dir, 'monthly_comparison.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: monthly_comparison.png")
        plt.close(fig)
    
    # Call types pie chart
    fig = chart_gen.plot_call_types()
    if fig:
        path = os.path.join(charts_dir, 'call_types.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: call_types.png")
        plt.close(fig)
    
    # Call duration distribution
    fig = chart_gen.plot_call_duration_distribution(bins=50)
    if fig:
        path = os.path.join(charts_dir, 'duration_distribution.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: duration_distribution.png")
        plt.close(fig)
    
    # ===== Top Callers/Called Charts =====
    print_subsection("9.2 Top Callers & Called Charts")
    
    # Top callers
    fig = chart_gen.plot_top_callers(n=15)
    if fig:
        path = os.path.join(charts_dir, 'top_callers.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: top_callers.png")
        plt.close(fig)
    
    # Top called numbers
    fig = chart_gen.plot_top_called(n=15)
    if fig:
        path = os.path.join(charts_dir, 'top_called.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: top_called.png")
        plt.close(fig)
    
    # ===== Quality Charts =====
    print_subsection("9.3 Quality Charts")
    
    if analyzer.cmr_df is not None:
        # Quality metrics dashboard
        fig = chart_gen.plot_quality_metrics()
        if fig:
            path = os.path.join(charts_dir, 'quality_metrics.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            print(f"     ✓ Saved: quality_metrics.png")
            plt.close(fig)
        
        # Quality trend (MOS)
        fig = chart_gen.plot_quality_trend(metric='mos', period='daily', days=30)
        if fig:
            path = os.path.join(charts_dir, 'mos_trend.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            print(f"     ✓ Saved: mos_trend.png")
            plt.close(fig)
        
        # Jitter trend
        fig = chart_gen.plot_quality_trend(metric='jitter', period='daily', days=30)
        if fig:
            path = os.path.join(charts_dir, 'jitter_trend.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            print(f"     ✓ Saved: jitter_trend.png")
            plt.close(fig)
    else:
        print("     ⚠️ Quality charts skipped (CMR data not loaded)")
    
    # ===== User Activity Charts =====
    print_subsection("9.4 User Activity Charts")
    
    top_callers = analyzer.users.get_top_callers(1)
    if not top_callers.empty:
        sample_user = top_callers.iloc[0]['caller']
        fig = chart_gen.plot_user_activity_timeline(user=sample_user, days=30)
        if fig:
            path = os.path.join(charts_dir, f'user_timeline_{sample_user}.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            print(f"     ✓ Saved: user_timeline_{sample_user}.png")
            plt.close(fig)
    
    # ===== Trunk & Device Charts =====
    print_subsection("9.5 Trunk & Device Charts")
    
    # Trunk utilization
    fig = chart_gen.plot_trunk_utilization()
    if fig:
        path = os.path.join(charts_dir, 'trunk_utilization.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: trunk_utilization.png")
        plt.close(fig)
    
    # Concurrent calls
    fig = chart_gen.plot_concurrent_calls(interval_minutes=15)
    if fig:
        path = os.path.join(charts_dir, 'concurrent_calls.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: concurrent_calls.png")
        plt.close(fig)
    
    # Codec distribution
    fig = chart_gen.plot_codec_distribution()
    if fig:
        path = os.path.join(charts_dir, 'codec_distribution.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: codec_distribution.png")
        plt.close(fig)
    
    # ===== Heatmaps =====
    print_subsection("9.6 Heatmap Visualizations")
    
    # Hourly heatmap (call volume)
    fig = heatmap_gen.plot_hourly_heatmap(metric='count')
    if fig:
        path = os.path.join(charts_dir, 'heatmap_hourly_volume.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: heatmap_hourly_volume.png")
        plt.close(fig)
    
    # Hourly heatmap (answer rate)
    fig = heatmap_gen.plot_hourly_heatmap(metric='answer_rate')
    if fig:
        path = os.path.join(charts_dir, 'heatmap_hourly_answer_rate.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: heatmap_hourly_answer_rate.png")
        plt.close(fig)
    
    # Quality heatmap (if CMR loaded)
    if analyzer.cmr_df is not None:
        fig = heatmap_gen.plot_quality_heatmap(metric='mos')
        if fig:
            path = os.path.join(charts_dir, 'heatmap_quality_mos.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            print(f"     ✓ Saved: heatmap_quality_mos.png")
            plt.close(fig)
        
        fig = heatmap_gen.plot_quality_heatmap(metric='jitter')
        if fig:
            path = os.path.join(charts_dir, 'heatmap_quality_jitter.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            print(f"     ✓ Saved: heatmap_quality_jitter.png")
            plt.close(fig)
    
    # Connection heatmap
    fig = heatmap_gen.plot_connection_heatmap(max_users=15)
    if fig:
        path = os.path.join(charts_dir, 'heatmap_connections.png')
        fig.savefig(path, dpi=150, bbox_inches='tight')
        print(f"     ✓ Saved: heatmap_connections.png")
        plt.close(fig)
    
    # Device quality heatmap (if CMR loaded)
    if analyzer.cmr_df is not None:
        fig = heatmap_gen.plot_device_quality_heatmap(max_devices=10)
        if fig:
            path = os.path.join(charts_dir, 'heatmap_device_quality.png')
            fig.savefig(path, dpi=150, bbox_inches='tight')
            print(f"     ✓ Saved: heatmap_device_quality.png")
            plt.close(fig)
    
    # ===== Interactive Charts =====
    print_subsection("9.7 Interactive Charts (Plotly)")
    
    try:
        from cisco_cdr_analyzer.visualization.interactive import InteractiveVisualizer
        
        interactive_dir = os.path.join(output_dir, 'interactive')
        os.makedirs(interactive_dir, exist_ok=True)
        
        interactive = InteractiveVisualizer(analyzer)
        
        # Daily trend interactive
        fig = interactive.plot_daily_trend_interactive(days=60)
        if fig:
            path = os.path.join(interactive_dir, 'daily_trend.html')
            fig.write_html(path)
            print(f"     ✓ Saved: interactive/daily_trend.html")
        
        # Hourly heatmap interactive
        fig = interactive.plot_hourly_heatmap_interactive(metric='count')
        if fig:
            path = os.path.join(interactive_dir, 'hourly_heatmap.html')
            fig.write_html(path)
            print(f"     ✓ Saved: interactive/hourly_heatmap.html")
        
        # Call flow Sankey diagram
        fig = interactive.plot_call_flow_sankey(top_n=10)
        if fig:
            path = os.path.join(interactive_dir, 'call_flow_sankey.html')
            fig.write_html(path)
            print(f"     ✓ Saved: interactive/call_flow_sankey.html")
        
        # Network topology
        fig = interactive.plot_network_topology(max_nodes=30, min_calls=5)
        if fig:
            path = os.path.join(interactive_dir, 'network_topology.html')
            fig.write_html(path)
            print(f"     ✓ Saved: interactive/network_topology.html")
        
        # Quality dashboard
        if analyzer.cmr_df is not None:
            fig = interactive.plot_quality_dashboard()
            if fig:
                path = os.path.join(interactive_dir, 'quality_dashboard.html')
                fig.write_html(path)
                print(f"     ✓ Saved: interactive/quality_dashboard.html")
        
        # KPI gauges
        fig = interactive.plot_kpi_gauges()
        if fig:
            path = os.path.join(interactive_dir, 'kpi_gauges.html')
            fig.write_html(path)
            print(f"     ✓ Saved: interactive/kpi_gauges.html")
        
        # Sunburst chart
        fig = interactive.plot_call_type_sunburst()
        if fig:
            path = os.path.join(interactive_dir, 'call_type_sunburst.html')
            fig.write_html(path)
            print(f"     ✓ Saved: interactive/call_type_sunburst.html")
        
    except ImportError:
        print("     ⚠️ Interactive charts skipped (Plotly not installed)")
        print("        Install with: pip install plotly")
    
    print(f"\n     📁 All charts saved to: {output_dir}")


def example_report_generation(analyzer: CiscoCDRAnalyzer, output_dir: str):
    """Demonstrate report generation capabilities"""
    print_section("10. REPORT GENERATION")
    
    from cisco_cdr_analyzer.visualization.reports import ReportGenerator
    
    report_gen = ReportGenerator(analyzer)
    reports_dir = os.path.join(output_dir, 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    # ===== HTML Report =====
    print_subsection("10.1 HTML Report Generation")
    
    html_path = report_gen.generate_report(
        output_dir=reports_dir,
        title='Comprehensive CDR Analysis Report',
        include_charts=True,
        include_quality=analyzer.cmr_df is not None,
        include_security=True,
        format='html'
    )
    print(f"     ✓ Generated: {html_path}")
    
    # ===== JSON Report =====
    print_subsection("10.2 JSON Report Generation")
    
    json_path = report_gen.generate_report(
        output_dir=reports_dir,
        title='CDR Analysis Data Export',
        include_quality=analyzer.cmr_df is not None,
        include_security=True,
        format='json'
    )
    print(f"     ✓ Generated: {json_path}")
    
    # ===== Excel Report =====
    print_subsection("10.3 Excel Report Generation")
    
    try:
        excel_path = report_gen.generate_report(
            output_dir=reports_dir,
            title='CDR Analysis Report',
            include_quality=analyzer.cmr_df is not None,
            format='xlsx'
        )
        print(f"     ✓ Generated: {excel_path}")
    except ImportError:
        print("     ⚠️ Excel report skipped (openpyxl not installed)")
        print("        Install with: pip install openpyxl")
    
    # ===== Export Raw Data =====
    print_subsection("10.4 Export Raw Processed Data")
    
    data_dir = os.path.join(output_dir, 'data_export')
    exported = report_gen.export_raw_data(output_dir=data_dir, format='csv')
    
    for name, path in exported.items():
        print(f"     ✓ Exported {name}: {path}")
    
    print(f"\n     📁 All reports saved to: {reports_dir}")


def example_advanced_scenarios(analyzer: CiscoCDRAnalyzer):
    """Demonstrate advanced analysis scenarios"""
    print_section("11. ADVANCED ANALYSIS SCENARIOS")
    
    # ===== Scenario 1: Capacity Planning =====
    print_subsection("11.1 Capacity Planning Analysis")
    
    # Get concurrent call data
    peak_concurrent = analyzer.time.get_peak_concurrent_calls()
    
    if peak_concurrent:
        print("     Capacity Planning Metrics:")
        print(f"       Peak concurrent calls: {peak_concurrent.get('peak_concurrent', 0)}")
        print(f"       Average concurrent: {peak_concurrent.get('avg_concurrent', 0):.1f}")
        print(f"       95th percentile: {peak_concurrent.get('p95_concurrent', 0)}")
        print(f"       99th percentile: {peak_concurrent.get('p99_concurrent', 0)}")
        
        # Calculate recommended trunk capacity
        p99 = peak_concurrent.get('p99_concurrent', 0)
        recommended = int(p99 * 1.2)  # 20% buffer
        print(f"\n     Recommended minimum trunks: {recommended}")
        print(f"     (Based on P99 + 20% buffer)")
    
    # Get busiest hours for staffing
    peak_hours = analyzer.time.get_peak_hours(top_n=3)
    if not peak_hours.empty:
        print("\n     Peak Hours (for staffing):")
        for _, row in peak_hours.iterrows():
            print(f"       {row['hour_label']}: {row['total_calls']:,} calls ({row['pct_of_total']:.1f}%)")
    
    # ===== Scenario 2: Problem User Detection =====
    print_subsection("11.2 Problem User/Device Detection")
    
    # Find users with low answer rates
    top_callers = analyzer.users.get_top_callers(50)
    if not top_callers.empty:
        low_answer_rate = top_callers[top_callers['answer_rate'] < 70]
        if not low_answer_rate.empty:
            print("     Users with low answer rate (<70%):")
            for _, row in low_answer_rate.head(5).iterrows():
                print(f"       {row['caller']}: {row['answer_rate']:.1f}% "
                      f"({int(row['answered_calls'])}/{int(row['total_calls'])} answered)")
        else:
            print("     ✅ No users with low answer rate")
    
    # Find devices with quality issues
    if analyzer.cmr_df is not None:
        health = analyzer.devices.get_device_health_status()
        if not health.empty:
            problematic = health[health['status'].isin(['warning', 'critical'])]
            if not problematic.empty:
                print(f"\n     Devices with quality issues: {len(problematic)}")
                for _, row in problematic.head(5).iterrows():
                    print(f"       {row['device'][:30]}: {row['status']} - {row['issues']}")
            else:
                print("\n     ✅ No devices with quality issues")
    
    # ===== Scenario 3: Trend Analysis =====
    print_subsection("11.3 Trend Detection & Forecasting")
    
    # Get weekly trends
    weekly = analyzer.time.get_weekly_trends(weeks=12)
    if len(weekly) >= 4:
        # Calculate trend direction
        recent_avg = weekly.tail(4)['total_calls'].mean()
        older_avg = weekly.head(4)['total_calls'].mean()
        
        if recent_avg > older_avg * 1.1:
            trend = "📈 INCREASING"
            change = ((recent_avg / older_avg) - 1) * 100
        elif recent_avg < older_avg * 0.9:
            trend = "📉 DECREASING"
            change = ((recent_avg / older_avg) - 1) * 100
        else:
            trend = "➡️ STABLE"
            change = 0
        
        print(f"     Call Volume Trend: {trend}")
        print(f"       Recent 4-week avg: {recent_avg:,.0f} calls/week")
        print(f"       Older 4-week avg: {older_avg:,.0f} calls/week")
        if change != 0:
            print(f"       Change: {change:+.1f}%")
    
    # ===== Scenario 4: SLA Monitoring =====
    print_subsection("11.4 SLA Monitoring Dashboard")
    
    # Define SLA targets
    sla_targets = {
        'answer_rate_target': 95.0,
        'avg_duration_max': 300,
        'quality_mos_min': 3.5,
        'service_level_target': 80.0,  # % answered within 20 seconds
    }
    
    summary = analyzer.get_call_summary()
    
    print("     SLA Compliance Status:")
    
    # Answer Rate SLA
    answer_rate = summary.get('answer_rate_pct', 0)
    ar_status = "✅ PASS" if answer_rate >= sla_targets['answer_rate_target'] else "❌ FAIL"
    print(f"       Answer Rate: {answer_rate}% (target: {sla_targets['answer_rate_target']}%) {ar_status}")
    
    # Average Duration
    avg_duration = summary.get('avg_duration_sec', 0)
    ad_status = "✅ PASS" if avg_duration <= sla_targets['avg_duration_max'] else "⚠️ WARNING"
    print(f"       Avg Duration: {avg_duration}s (max: {sla_targets['avg_duration_max']}s) {ad_status}")
    
    # Quality SLA (if CMR loaded)
    if analyzer.cmr_df is not None:
        quality_summary = analyzer.get_quality_summary()
        if 'mos' in quality_summary:
            avg_mos = quality_summary['mos']['average']
            mos_status = "✅ PASS" if avg_mos >= sla_targets['quality_mos_min'] else "❌ FAIL"
            print(f"       Avg MOS: {avg_mos:.2f} (min: {sla_targets['quality_mos_min']}) {mos_status}")
    
    # ===== Scenario 5: Cost Analysis =====
    print_subsection("11.5 Call Cost Estimation")
    
    # Example cost rates (customize for your organization)
    cost_rates = {
        'internal': 0.00,       # Free internal calls
        'inbound': 0.01,        # $0.01 per minute inbound
        'outbound': 0.03,       # $0.03 per minute outbound
        'other': 0.02,          # $0.02 per minute other
    }
    
    call_types = analyzer.time.get_calls_by_type() if hasattr(analyzer.time, 'get_calls_by_type') else None
    
    # Calculate costs by type
    df = analyzer.cdr_df.copy()
    total_cost = 0
    
    print("     Estimated Call Costs:")
    for call_type, rate in cost_rates.items():
        type_calls = df[df['call_type'] == call_type]
        if not type_calls.empty:
            duration_minutes = type_calls['duration'].sum() / 60
            cost = duration_minutes * rate
            total_cost += cost
            print(f"       {call_type:12s}: {duration_minutes:>10,.0f} min × ${rate:.2f} = ${cost:>10,.2f}")
    
    print(f"       {'─' * 50}")
    print(f"       {'TOTAL':12s}: ${total_cost:>43,.2f}")
    
    # ===== Scenario 6: Anomaly Detection =====
    print_subsection("11.6 Anomaly Detection")
    
    # Detect unusual patterns
    daily = analyzer.time.get_daily_call_volume()
    if not daily.empty and len(daily) >= 14:
        # Calculate mean and std for anomaly detection
        mean_calls = daily['total_calls'].mean()
        std_calls = daily['total_calls'].std()
        
        # Find days with call volume > 2 standard deviations
        high_threshold = mean_calls + (2 * std_calls)
        low_threshold = mean_calls - (2 * std_calls)
        
        anomalies = daily[
            (daily['total_calls'] > high_threshold) |
            (daily['total_calls'] < low_threshold)
        ]
        
        if not anomalies.empty:
            print(f"     Detected {len(anomalies)} anomalous days:")
            for _, row in anomalies.iterrows():
                deviation = (row['total_calls'] - mean_calls) / std_calls
                direction = "HIGH" if deviation > 0 else "LOW"
                print(f"       {row['date']}: {row['total_calls']:,} calls "
                      f"({direction}, {abs(deviation):.1f}σ from mean)")
        else:
            print("     ✅ No anomalous days detected")
        
        print(f"\n     Baseline: {mean_calls:.0f} ± {std_calls:.0f} calls/day")


def example_custom_analysis(analyzer: CiscoCDRAnalyzer):
    """Demonstrate custom analysis using raw DataFrames"""
    print_section("12. CUSTOM ANALYSIS EXAMPLES")
    
    print_subsection("12.1 Direct DataFrame Access")
    
    # Access raw DataFrames
    cdr = analyzer.cdr_df
    cmr = analyzer.cmr_df
    merged = analyzer.merged_df
    
    print(f"     CDR DataFrame: {cdr.shape[0]} rows × {cdr.shape[1]} columns")
    if cmr is not None:
        print(f"     CMR DataFrame: {cmr.shape[0]} rows × {cmr.shape[1]} columns")
    if merged is not None:
        print(f"     Merged DataFrame: {merged.shape[0]} rows × {merged.shape[1]} columns")
    
    print("\n     CDR Columns available:")
    for i, col in enumerate(cdr.columns[:20]):
        print(f"       {col}", end="  ")
        if (i + 1) % 4 == 0:
            print()
    print("...")
    
    # ===== Custom Query Examples =====
    print_subsection("12.2 Custom Query Examples")
    
    # Example 1: Find all calls to a specific area code
    print("     Example 1: Calls to area code '212'")
    area_code_calls = cdr[cdr['finalCalledPartyNumber'].str.startswith('212', na=False)]
    print(f"       Found: {len(area_code_calls)} calls")
    
    # Example 2: Average call duration by device type
    print("\n     Example 2: Average duration by device type")
    if 'orig_device_type' in cdr.columns:
        avg_by_type = cdr.groupby('orig_device_type')['duration'].mean().sort_values(ascending=False)
        for device_type, avg_dur in avg_by_type.head(5).items():
            print(f"       {device_type}: {avg_dur:.1f}s")
    
    # Example 3: Calls during specific time range
    print("\n     Example 3: Calls between 12:00-13:00 (lunch hour)")
    lunch_calls = cdr[cdr['hour'] == 12]
    print(f"       Found: {len(lunch_calls)} calls during lunch hour")
    print(f"       Answer rate: {lunch_calls['answered'].mean()*100:.1f}%")
    
    # Example 4: Longest calls
    print("\n     Example 4: Top 5 longest calls")
    longest = cdr.nlargest(5, 'duration')[['callingPartyNumber', 'finalCalledPartyNumber', 'duration', 'dateTimeOrigination_dt']]
    for _, row in longest.iterrows():
        duration_mins = row['duration'] / 60
        print(f"       {row['callingPartyNumber']} → {row['finalCalledPartyNumber']}: {duration_mins:.1f} min")
    
    # Example 5: Most active day
    print("\n     Example 5: Most active day")
    daily_counts = cdr.groupby('date').size()
    busiest_day = daily_counts.idxmax()
    print(f"       {busiest_day}: {daily_counts[busiest_day]:,} calls")
    
    # ===== Custom Aggregations =====
    print_subsection("12.3 Custom Aggregation Example")
    
    # Create custom summary by day of week and call type
    print("     Calls by Day of Week × Call Type:")
    pivot = cdr.pivot_table(
        values='globalCallID_callId',
        index='day_name',
        columns='call_type',
        aggfunc='count',
        fill_value=0
    )
    
    # Reorder days
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    pivot = pivot.reindex([d for d in day_order if d in pivot.index])
    
    print(pivot.to_string())
    
    # ===== Export Custom Analysis =====
    print_subsection("12.4 Export Custom Analysis Results")
    
    # Create custom analysis DataFrame
    custom_analysis = cdr.groupby(['date', 'call_type']).agg({
        'globalCallID_callId': 'count',
        'duration': ['sum', 'mean'],
        'answered': 'sum'
    }).reset_index()
    
    custom_analysis.columns = ['date', 'call_type', 'total_calls', 'total_duration', 'avg_duration', 'answered']
    
    print(f"     Custom analysis DataFrame created: {custom_analysis.shape}")
    print("     (Can be exported using: custom_analysis.to_csv('custom_analysis.csv'))")


def main():
    """Main function demonstrating all analyzer capabilities"""
    
    print("\n" + "=" * 70)
    print("        CISCO CDR/CMR ANALYZER - COMPREHENSIVE EXAMPLE")
    print("=" * 70)
    print(f"\n  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  This script demonstrates ALL analysis features.\n")
    
    # ==================== CONFIGURATION ====================
    
    # File paths - customize these for your environment
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try multiple possible data locations
    possible_data_dirs = [
        os.path.join(script_dir, 'data'),
        os.path.join(script_dir, '..', 'data'),
        script_dir,
    ]
    
    cdr_file = None
    cmr_file = None
    
    for data_dir in possible_data_dirs:
        test_cdr = os.path.join(data_dir, 'cdr.csv')
        test_cmr = os.path.join(data_dir, 'cmr.csv')
        
        if os.path.exists(test_cdr):
            cdr_file = test_cdr
            cmr_file = test_cmr if os.path.exists(test_cmr) else None
            break
    
    if cdr_file is None:
        # Default paths
        cdr_file = os.path.join(script_dir, 'data', 'cdr.csv')
        cmr_file = os.path.join(script_dir, 'data', 'cmr.csv')
    
    output_dir = os.path.join(script_dir, 'output')
    
    print(f"  Configuration:")
    print(f"    CDR file: {cdr_file}")
    print(f"    CMR file: {cmr_file}")
    print(f"    Output:   {output_dir}")
    
    # ==================== INITIALIZE ANALYZER ====================
    
    # Create custom settings
    settings = Settings()
    settings.output_dir = output_dir
    
    # Customize business hours
    settings.business_hours.start_hour = 8
    settings.business_hours.end_hour = 18
    settings.business_hours.business_days = [0, 1, 2, 3, 4]  # Mon-Fri
    
    # Customize quality thresholds
    settings.quality.jitter_warning = 30
    settings.quality.jitter_critical = 50
    settings.quality.latency_warning = 150
    settings.quality.latency_critical = 300
    settings.quality.packet_loss_warning = 1.0
    settings.quality.packet_loss_critical = 3.0
    settings.quality.mos_good = 4.0
    settings.quality.mos_acceptable = 3.5
    
    # Initialize analyzer
    analyzer = CiscoCDRAnalyzer(settings)
    
    # ==================== RUN ALL EXAMPLES ====================
    
    try:
        # 1. Load Data
        if not example_data_loading(analyzer, cdr_file, cmr_file):
            print("\n❌ Failed to load CDR data. Please check file paths.")
            print(f"   Expected CDR file at: {cdr_file}")
            return
        
        # 2. Call Summary
        example_call_summary(analyzer)
        
        # 3. Time Analysis
        example_time_analysis(analyzer)
        
        # 4. User Analysis
        example_user_analysis(analyzer)
        
        # 5. Device Analysis
        example_device_analysis(analyzer)
        
        # 6. Quality Analysis
        example_quality_analysis(analyzer)
        
        # 7. Hunt Group Analysis
        example_hunt_group_analysis(analyzer)
        
        # 8. Security Analysis
        example_security_analysis(analyzer)
        
        # 9. Visualizations
        example_visualizations(analyzer, output_dir)
        
        # 10. Report Generation
        example_report_generation(analyzer, output_dir)
        
        # 11. Advanced Scenarios
        example_advanced_scenarios(analyzer)
        
        # 12. Custom Analysis
        example_custom_analysis(analyzer)
        
        # ==================== SUMMARY ====================
        
        print_section("ANALYSIS COMPLETE", "=")
        
        print(f"  ✅ All examples completed successfully!")
        print(f"\n  📊 Summary:")
        print(f"     • CDR records analyzed: {len(analyzer.cdr_df):,}")
        if analyzer.cmr_df is not None:
            print(f"     • CMR records analyzed: {len(analyzer.cmr_df):,}")
        print(f"     • Output saved to: {output_dir}")
        
        print(f"\n  📁 Generated Files:")
        print(f"     • Charts: {output_dir}/charts/")
        print(f"     • Interactive: {output_dir}/interactive/")
        print(f"     • Reports: {output_dir}/reports/")
        print(f"     • Data Export: {output_dir}/data_export/")
        
        print(f"\n  ⏱️  Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Analysis interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()