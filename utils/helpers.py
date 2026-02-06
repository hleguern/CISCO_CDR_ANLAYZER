"""
Utility helper functions for CDR/CMR analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple, Union
import re
import math
import logging
import os

logger = logging.getLogger(__name__)


def format_duration(seconds: Union[int, float], format_type: str = 'hms') -> str:
    """
    Format duration in seconds to human readable string
    
    :param seconds: Duration in seconds
    :param format_type: 'hms' (1h 23m 45s), 'colon' (1:23:45), 'verbose'
    :return: Formatted string
    """
    if pd.isna(seconds) or seconds < 0:
        return "0s"
    
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    if format_type == 'colon':
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"
    
    elif format_type == 'verbose':
        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")
        return ', '.join(parts)
    
    else:  # 'hms'
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"


def format_phone_number(number: str, format_type: str = 'E164') -> str:
    """
    Format phone number to standard format
    
    :param number: Phone number string
    :param format_type: 'E164', 'national', 'extension'
    :return: Formatted phone number
    """
    if not number or number in ['nan', '\\', '']:
        return ''
    
    # Remove non-digits except +
    cleaned = re.sub(r'[^\d+]', '', str(number))
    
    if format_type == 'extension':
        # Just return last 4-6 digits as extension
        digits_only = re.sub(r'\D', '', cleaned)
        if len(digits_only) <= 6:
            return digits_only
        return digits_only[-4:]
    
    elif format_type == 'national':
        # Format as (XXX) XXX-XXXX for 10-digit numbers
        digits = re.sub(r'\D', '', cleaned)
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        return cleaned
    
    else:  # E164
        digits = re.sub(r'\D', '', cleaned)
        if not cleaned.startswith('+'):
            if len(digits) == 10:
                return f"+1{digits}"
            elif len(digits) == 11 and digits[0] == '1':
                return f"+{digits}"
        return cleaned


def parse_date_range(
    date_range: Union[str, Tuple[str, str], Dict[str, str]]
) -> Tuple[datetime, datetime]:
    """
    Parse various date range formats
    
    :param date_range: Can be:
        - String: 'last_7_days', 'last_30_days', 'this_month', 'last_month'
        - Tuple: ('2024-01-01', '2024-01-31')
        - Dict: {'start': '2024-01-01', 'end': '2024-01-31'}
    :return: Tuple of (start_datetime, end_datetime)
    """
    now = datetime.now()
    
    if isinstance(date_range, str):
        if date_range == 'last_7_days':
            return (now - timedelta(days=7), now)
        elif date_range == 'last_30_days':
            return (now - timedelta(days=30), now)
        elif date_range == 'last_90_days':
            return (now - timedelta(days=90), now)
        elif date_range == 'this_month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return (start, now)
        elif date_range == 'last_month':
            first_this_month = now.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return (last_month_start, last_month_end)
        elif date_range == 'this_week':
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return (start, now)
        elif date_range == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return (start, now)
        elif date_range == 'yesterday':
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59)
            return (start, end)
        else:
            # Try to parse as single date
            parsed = pd.to_datetime(date_range)
            return (parsed, parsed + timedelta(days=1) - timedelta(seconds=1))
    
    elif isinstance(date_range, tuple):
        start = pd.to_datetime(date_range[0])
        end = pd.to_datetime(date_range[1])
        return (start, end)
    
    elif isinstance(date_range, dict):
        start = pd.to_datetime(date_range['start'])
        end = pd.to_datetime(date_range['end'])
        return (start, end)
    
    raise ValueError(f"Invalid date_range format: {date_range}")


def calculate_erlang_b(
    traffic_erlangs: float, 
    channels: int
) -> float:
    """
    Calculate blocking probability using Erlang B formula
    
    :param traffic_erlangs: Traffic intensity in Erlangs
    :param channels: Number of channels (lines)
    :return: Blocking probability (0-1)
    """
    if channels <= 0:
        return 1.0
    if traffic_erlangs <= 0:
        return 0.0
    
    # Calculate Erlang B recursively
    inv_b = 1.0
    for i in range(1, channels + 1):
        inv_b = 1.0 + inv_b * i / traffic_erlangs
    
    return 1.0 / inv_b


def calculate_traffic_erlangs(
    call_count: int,
    avg_duration_seconds: float,
    period_hours: float = 1.0
) -> float:
    """
    Calculate traffic in Erlangs
    
    :param call_count: Number of calls
    :param avg_duration_seconds: Average call duration in seconds
    :param period_hours: Time period in hours
    :return: Traffic in Erlangs
    """
    if period_hours <= 0:
        return 0.0
    
    total_duration_hours = (call_count * avg_duration_seconds) / 3600
    return total_duration_hours / period_hours


def calculate_required_channels(
    traffic_erlangs: float,
    target_blocking: float = 0.01
) -> int:
    """
    Calculate required channels for target blocking probability
    
    :param traffic_erlangs: Traffic in Erlangs
    :param target_blocking: Target blocking probability (default 1%)
    :return: Required number of channels
    """
    if traffic_erlangs <= 0:
        return 0
    
    # Binary search for required channels
    low, high = 1, int(traffic_erlangs * 10) + 100
    
    while low < high:
        mid = (low + high) // 2
        blocking = calculate_erlang_b(traffic_erlangs, mid)
        
        if blocking <= target_blocking:
            high = mid
        else:
            low = mid + 1
    
    return low


def validate_extension(
    extension: str,
    min_length: int = 3,
    max_length: int = 6
) -> bool:
    """
    Validate extension number format
    
    :param extension: Extension string
    :param min_length: Minimum length
    :param max_length: Maximum length
    :return: True if valid
    """
    if not extension:
        return False
    
    ext_str = str(extension).strip()
    
    # Must be digits only
    if not ext_str.isdigit():
        return False
    
    # Check length
    if len(ext_str) < min_length or len(ext_str) > max_length:
        return False
    
    return True


def export_to_excel(
    data: Dict[str, pd.DataFrame],
    filepath: str,
    include_summary: bool = True
) -> str:
    """
    Export multiple DataFrames to Excel workbook
    
    :param data: Dictionary of sheet_name -> DataFrame
    :param filepath: Output file path
    :param include_summary: Include summary sheet
    :return: Path to created file
    """
    try:
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            if include_summary:
                summary_data = []
                for name, df in data.items():
                    summary_data.append({
                        'Sheet': name,
                        'Rows': len(df),
                        'Columns': len(df.columns),
                    })
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            for sheet_name, df in data.items():
                # Truncate sheet name if too long
                safe_name = sheet_name[:31]
                df.to_excel(writer, sheet_name=safe_name, index=False)
        
        logger.info(f"Excel file exported: {filepath}")
        return filepath
    
    except Exception as e:
        logger.error(f"Error exporting to Excel: {e}")
        raise


def create_summary_report(
    call_summary: Dict[str, Any],
    quality_summary: Optional[Dict[str, Any]] = None,
    output_format: str = 'dict'
) -> Union[Dict, str]:
    """
    Create a summary report from analysis results
    
    :param call_summary: Call summary dictionary
    :param quality_summary: Optional quality summary
    :param output_format: 'dict', 'text', or 'markdown'
    :return: Summary in requested format
    """
    report = {
        'report_generated': datetime.now().isoformat(),
        'call_statistics': call_summary,
    }
    
    if quality_summary:
        report['quality_statistics'] = quality_summary
    
    if output_format == 'dict':
        return report
    
    elif output_format == 'text':
        lines = [
            "=" * 60,
            "CDR/CMR ANALYSIS SUMMARY REPORT",
            "=" * 60,
            f"Generated: {report['report_generated']}",
            "",
            "CALL STATISTICS",
            "-" * 40,
        ]
        
        for key, value in call_summary.items():
            if not isinstance(value, (dict, list)):
                lines.append(f"  {key}: {value}")
        
        if quality_summary:
            lines.extend([
                "",
                "QUALITY STATISTICS",
                "-" * 40,
            ])
            for key, value in quality_summary.items():
                if not isinstance(value, (dict, list)):
                    lines.append(f"  {key}: {value}")
        
        lines.append("=" * 60)
        return '\n'.join(lines)
    
    elif output_format == 'markdown':
        lines = [
            "# CDR/CMR Analysis Summary Report",
            f"*Generated: {report['report_generated']}*",
            "",
            "## Call Statistics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]
        
        for key, value in call_summary.items():
            if not isinstance(value, (dict, list)):
                lines.append(f"| {key} | {value} |")
        
        if quality_summary:
            lines.extend([
                "",
                "## Quality Statistics",
                "",
                "| Metric | Value |",
                "|--------|-------|",
            ])
            for key, value in quality_summary.items():
                if not isinstance(value, (dict, list)):
                    lines.append(f"| {key} | {value} |")
        
        return '\n'.join(lines)
    
    return report


def get_date_range_label(
    start: datetime, 
    end: datetime
) -> str:
    """
    Generate human-readable label for date range
    
    :param start: Start datetime
    :param end: End datetime
    :return: Label string
    """
    if start.date() == end.date():
        return start.strftime('%B %d, %Y')
    elif start.year == end.year:
        if start.month == end.month:
            return f"{start.strftime('%B %d')} - {end.strftime('%d, %Y')}"
        return f"{start.strftime('%B %d')} - {end.strftime('%B %d, %Y')}"
    return f"{start.strftime('%B %d, %Y')} - {end.strftime('%B %d, %Y')}"


def calculate_percentile(
    series: pd.Series, 
    percentile: float
) -> float:
    """
    Calculate percentile value
    
    :param series: Pandas Series
    :param percentile: Percentile (0-100)
    :return: Percentile value
    """
    return series.quantile(percentile / 100)


def detect_outliers(
    series: pd.Series,
    method: str = 'iqr',
    threshold: float = 1.5
) -> pd.Series:
    """
    Detect outliers in a series
    
    :param series: Pandas Series
    :param method: 'iqr' or 'zscore'
    :param threshold: Threshold multiplier
    :return: Boolean Series indicating outliers
    """
    if method == 'iqr':
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - threshold * IQR
        upper = Q3 + threshold * IQR
        return (series < lower) | (series > upper)
    
    elif method == 'zscore':
        z_scores = (series - series.mean()) / series.std()
        return z_scores.abs() > threshold
    
    return pd.Series([False] * len(series))


def safe_divide(
    numerator: Union[int, float],
    denominator: Union[int, float],
    default: float = 0.0
) -> float:
    """
    Safe division with default for zero denominator
    
    :param numerator: Numerator
    :param denominator: Denominator
    :param default: Default value if division by zero
    :return: Result or default
    """
    if denominator == 0 or pd.isna(denominator):
        return default
    return numerator / denominator


def chunk_dataframe(
    df: pd.DataFrame, 
    chunk_size: int
) -> List[pd.DataFrame]:
    """
    Split DataFrame into chunks
    
    :param df: DataFrame to split
    :param chunk_size: Size of each chunk
    :return: List of DataFrame chunks
    """
    return [df[i:i + chunk_size] for i in range(0, len(df), chunk_size)]