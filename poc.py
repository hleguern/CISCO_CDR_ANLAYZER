#!/usr/bin/env python3
"""
Cisco VoIP CDR/CMR Analyzer
Analyzes Call Detail Records (CDR) and Call Management Records (CMR) from Cisco UCM

Author: Claude
Version: 1.0
"""

import csv
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
import seaborn as sns
import re
from typing import Optional, List, Dict, Tuple, Any
import warnings
import os

warnings.filterwarnings('ignore')

# Set plotting style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")


class CiscoCDRAnalyzer:
    """
    Comprehensive analyzer for Cisco Call Detail Records (CDR) 
    and Call Management Records (CMR)
    """
    
    def __init__(self):
        self.cdr_df: Optional[pd.DataFrame] = None
        self.cmr_df: Optional[pd.DataFrame] = None
        self.merged_df: Optional[pd.DataFrame] = None
        
    # ==================== DATA LOADING ====================
    
    def load_cdr(self, file_path: str, encoding: str = 'utf-8') -> pd.DataFrame:
        """
        Load CDR file from CSV
        
        :param file_path: Path to CDR CSV file
        :param encoding: File encoding (default: utf-8)
        :return: Processed CDR DataFrame
        """
        print(f"Loading CDR from: {file_path}")
        self.cdr_df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
        self._process_cdr()
        print(f"  ✓ Loaded {len(self.cdr_df)} CDR records")
        return self.cdr_df
    
    def load_cmr(self, file_path: str, encoding: str = 'utf-8') -> pd.DataFrame:
        """
        Load CMR file from CSV
        
        :param file_path: Path to CMR CSV file
        :param encoding: File encoding (default: utf-8)
        :return: Processed CMR DataFrame
        """
        print(f"Loading CMR from: {file_path}")
        self.cmr_df = pd.read_csv(file_path, encoding=encoding, low_memory=False)
        self._process_cmr()
        print(f"  ✓ Loaded {len(self.cmr_df)} CMR records")
        return self.cmr_df
    
    def _process_cdr(self):
        """Process CDR data - convert timestamps, calculate durations, etc."""
        if self.cdr_df is None:
            return
        
        # Convert Unix timestamps to datetime
        timestamp_cols = ['dateTimeOrigination', 'dateTimeConnect', 'dateTimeDisconnect']
        for col in timestamp_cols:
            if col in self.cdr_df.columns:
                self.cdr_df[f'{col}_dt'] = pd.to_datetime(
                    self.cdr_df[col], unit='s', errors='coerce'
                )
        
        # Extract time components for analysis
        if 'dateTimeOrigination_dt' in self.cdr_df.columns:
            self.cdr_df['hour'] = self.cdr_df['dateTimeOrigination_dt'].dt.hour
            self.cdr_df['day_of_week'] = self.cdr_df['dateTimeOrigination_dt'].dt.day_name()
            self.cdr_df['date'] = self.cdr_df['dateTimeOrigination_dt'].dt.date
        
        # Clean phone numbers and device names
        str_cols = ['callingPartyNumber', 'finalCalledPartyNumber', 
                    'origDeviceName', 'destDeviceName',
                    'callingPartyNumber_uri', 'callingPartyUnicodeLoginUserID']
        for col in str_cols:
            if col in self.cdr_df.columns:
                self.cdr_df[col] = self.cdr_df[col].astype(str).replace('\\\\', '', regex=True).str.strip()
        
        # Determine call direction/type
        self.cdr_df['call_type'] = self.cdr_df.apply(self._determine_call_type, axis=1)
        
        # Calculate ring time (time before answer)
        if 'dateTimeConnect' in self.cdr_df.columns and 'dateTimeOrigination' in self.cdr_df.columns:
            self.cdr_df['ring_time'] = self.cdr_df['dateTimeConnect'] - self.cdr_df['dateTimeOrigination']
            self.cdr_df['ring_time'] = self.cdr_df['ring_time'].apply(lambda x: x if x >= 0 else 0)
        
        # Determine if call was answered
        self.cdr_df['answered'] = self.cdr_df['duration'] > 0
        
    def _process_cmr(self):
        """Process CMR data - parse VQ metrics"""
        if self.cmr_df is None:
            return
        
        # Handle packet statistics
        packet_cols = ['orignumberPacketsLost', 'destnumberPacketsLost',
                       'orignumberPacketsSent', 'destnumberPacketsSent',
                       'orignumberPacketsReceived', 'destnumberPacketsReceived']
        for col in packet_cols:
            if col in self.cmr_df.columns:
                self.cmr_df[col] = pd.to_numeric(self.cmr_df[col], errors='coerce').fillna(0)
        
        # Calculate packet loss percentage
        if 'orignumberPacketsSent' in self.cmr_df.columns:
            self.cmr_df['orig_packet_loss_pct'] = (
                self.cmr_df['orignumberPacketsLost'] / 
                self.cmr_df['orignumberPacketsSent'].replace(0, np.nan) * 100
            ).fillna(0)
        
        if 'destnumberPacketsSent' in self.cmr_df.columns:
            self.cmr_df['dest_packet_loss_pct'] = (
                self.cmr_df['destnumberPacketsLost'] / 
                self.cmr_df['destnumberPacketsSent'].replace(0, np.nan) * 100
            ).fillna(0)
        
        # Handle jitter and latency
        for col in ['origjitter', 'destjitter', 'origlatency', 'destlatency']:
            if col in self.cmr_df.columns:
                self.cmr_df[col] = pd.to_numeric(self.cmr_df[col], errors='coerce').fillna(0)
        
        # Parse VQ metrics strings
        for prefix, col in [('orig', 'origvarVQMetrics'), ('dest', 'destvarVQMetrics')]:
            if col in self.cmr_df.columns:
                self._parse_vq_metrics(col, prefix)
    
    def _parse_vq_metrics(self, col: str, prefix: str):
        """Parse VQ metrics string into separate columns"""
        metrics = {
            'CCR': float,      # Concealment Ratio
            'ICR': float,      # Interval Concealment Ratio
            'ICRmx': float,    # Max Interval Concealment Ratio
            'CS': int,         # Concealment Seconds
            'SCS': int,        # Severely Concealed Seconds
            'VoPktLost': int,  # Voice Packets Lost
            'VoPktDis': int,   # Voice Packets Discarded
            'VoOneWayDelayMs': int,  # One-way Delay in ms
            'maxJitter': int,  # Maximum Jitter
            'VoRxCodec': str,  # Voice Receive Codec
            'VoPktSizeMs': int # Voice Packet Size in ms
        }
        
        def extract_metric(value, metric_name, dtype):
            if pd.isna(value) or value in ['\\', '\\ ', '', 'nan']:
                return None
            match = re.search(f'{metric_name}=([^;]+)', str(value))
            if match:
                try:
                    return dtype(match.group(1))
                except (ValueError, TypeError):
                    return match.group(1) if dtype == str else None
            return None
        
        for metric, dtype in metrics.items():
            self.cmr_df[f'{prefix}_{metric}'] = self.cmr_df[col].apply(
                lambda x: extract_metric(x, metric, dtype)
            )
    
    def _determine_call_type(self, row) -> str:
        """Determine if call is internal, inbound, or outbound"""
        orig_device = str(row.get('origDeviceName', ''))
        dest_device = str(row.get('destDeviceName', ''))
        
        # Check for SIP trunk (external calls)
        if 'SIP-TRUNK' in orig_device or 'TRUNK' in orig_device:
            return 'inbound'
        elif 'SIP-TRUNK' in dest_device or 'TRUNK' in dest_device:
            return 'outbound'
        elif orig_device.startswith('SEP') and dest_device.startswith('SEP'):
            return 'internal'
        else:
            return 'other'
    
    def merge_cdr_cmr(self) -> Optional[pd.DataFrame]:
        """
        Merge CDR and CMR data using globalCallID_callId
        
        :return: Merged DataFrame
        """
        if self.cdr_df is None or self.cmr_df is None:
            print("Error: Both CDR and CMR must be loaded first")
            return None
        
        # Merge on globalCallID_callId
        self.merged_df = pd.merge(
            self.cdr_df,
            self.cmr_df,
            on=['globalCallID_callManagerId', 'globalCallID_callId'],
            how='left',
            suffixes=('', '_cmr')
        )
        print(f"  ✓ Merged {len(self.merged_df)} records")
        return self.merged_df
    
    # ==================== ANALYSIS FUNCTIONS ====================
    
    def get_call_summary(self) -> Dict[str, Any]:
        """
        Get overall call statistics summary
        
        :return: Dictionary with call statistics
        """
        if self.cdr_df is None:
            print("Error: CDR data not loaded")
            return {}
        
        df = self.cdr_df
        
        summary = {
            'total_calls': len(df),
            'answered_calls': df['answered'].sum(),
            'missed_calls': (~df['answered']).sum(),
            'answer_rate': f"{df['answered'].mean() * 100:.1f}%",
            'total_duration_sec': df['duration'].sum(),
            'total_duration_formatted': str(timedelta(seconds=int(df['duration'].sum()))),
            'avg_duration_sec': df[df['answered']]['duration'].mean(),
            'max_duration_sec': df['duration'].max(),
            'call_types': df['call_type'].value_counts().to_dict(),
            'unique_callers': df['callingPartyNumber'].nunique(),
            'unique_called': df['finalCalledPartyNumber'].nunique(),
            'unique_devices': pd.concat([
                df['origDeviceName'], df['destDeviceName']
            ]).nunique(),
        }
        
        if 'dateTimeOrigination_dt' in df.columns:
            summary['date_range'] = {
                'start': df['dateTimeOrigination_dt'].min(),
                'end': df['dateTimeOrigination_dt'].max()
            }
        
        return summary
    
    def get_quality_summary(self) -> Dict[str, Any]:
        """
        Get call quality statistics from CMR data
        
        :return: Dictionary with quality statistics
        """
        if self.cmr_df is None:
            print("Error: CMR data not loaded")
            return {}
        
        df = self.cmr_df
        
        summary = {
            'total_records': len(df),
            'avg_orig_jitter': df['origjitter'].mean(),
            'avg_dest_jitter': df['destjitter'].mean(),
            'max_orig_jitter': df['origjitter'].max(),
            'max_dest_jitter': df['destjitter'].max(),
            'avg_orig_latency': df['origlatency'].mean(),
            'avg_dest_latency': df['destlatency'].mean(),
            'total_orig_packets_lost': df['orignumberPacketsLost'].sum(),
            'total_dest_packets_lost': df['destnumberPacketsLost'].sum(),
            'avg_orig_packet_loss_pct': df['orig_packet_loss_pct'].mean(),
            'avg_dest_packet_loss_pct': df['dest_packet_loss_pct'].mean(),
        }
        
        # VQ Metrics if parsed
        if 'orig_maxJitter' in df.columns:
            summary['vq_avg_max_jitter_orig'] = df['orig_maxJitter'].mean()
            summary['vq_avg_max_jitter_dest'] = df['dest_maxJitter'].mean()
        
        if 'orig_VoOneWayDelayMs' in df.columns:
            summary['vq_avg_one_way_delay_orig'] = df['orig_VoOneWayDelayMs'].mean()
            summary['vq_avg_one_way_delay_dest'] = df['dest_VoOneWayDelayMs'].mean()
        
        return summary
    
    def get_all_users(self) -> List[str]:
        """
        Get all unique users/phone numbers in the CDR
        
        :return: List of unique phone numbers
        """
        if self.cdr_df is None:
            return []
        
        callers = set(self.cdr_df['callingPartyNumber'].unique())
        called = set(self.cdr_df['finalCalledPartyNumber'].unique())
        return sorted(list(callers | called))
    
    def get_all_devices(self) -> List[str]:
        """
        Get all unique devices
        
        :return: List of unique device names
        """
        if self.cdr_df is None:
            return []
        
        orig = set(self.cdr_df['origDeviceName'].unique())
        dest = set(self.cdr_df['destDeviceName'].unique())
        return sorted(list(orig | dest))
    
    def get_user_records(self, user: str) -> pd.DataFrame:
        """
        Get all call records for a specific user/phone number
        
        :param user: Phone number or user ID
        :return: DataFrame with user's call records
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        mask = (
            (self.cdr_df['callingPartyNumber'] == user) |
            (self.cdr_df['finalCalledPartyNumber'] == user) |
            (self.cdr_df['callingPartyUnicodeLoginUserID'] == user)
        )
        return self.cdr_df[mask].copy()
    
    def get_records_between_users(self, user1: str, user2: str) -> pd.DataFrame:
        """
        Get call records between two specific users
        
        :param user1: First phone number/user
        :param user2: Second phone number/user
        :return: DataFrame with calls between the two users
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        mask = (
            ((self.cdr_df['callingPartyNumber'] == user1) & 
             (self.cdr_df['finalCalledPartyNumber'] == user2)) |
            ((self.cdr_df['callingPartyNumber'] == user2) & 
             (self.cdr_df['finalCalledPartyNumber'] == user1))
        )
        return self.cdr_df[mask].copy()
    
    def get_connected_users(self, user: str) -> List[str]:
        """
        Get all users that have called or been called by the specified user
        
        :param user: Phone number or user ID
        :return: List of connected phone numbers
        """
        user_records = self.get_user_records(user)
        if user_records.empty:
            return []
        
        connected = set()
        connected.update(user_records['callingPartyNumber'].unique())
        connected.update(user_records['finalCalledPartyNumber'].unique())
        connected.discard(user)
        return sorted(list(connected))
    
    def get_user_statistics(self, user: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific user
        
        :param user: Phone number or user ID
        :return: Dictionary with user statistics
        """
        records = self.get_user_records(user)
        if records.empty:
            return {'error': 'User not found'}
        
        outgoing = records[records['callingPartyNumber'] == user]
        incoming = records[records['finalCalledPartyNumber'] == user]
        
        stats = {
            'user': user,
            'total_calls': len(records),
            'outgoing_calls': len(outgoing),
            'incoming_calls': len(incoming),
            'outgoing_answered': outgoing['answered'].sum(),
            'incoming_answered': incoming['answered'].sum(),
            'total_duration_sec': records['duration'].sum(),
            'avg_call_duration_sec': records[records['answered']]['duration'].mean(),
            'connected_users': len(self.get_connected_users(user)),
            'devices_used': records['origDeviceName'].unique().tolist(),
        }
        
        return stats
    
    def get_device_records(self, device_name: str) -> pd.DataFrame:
        """
        Get all call records for a specific device
        
        :param device_name: Device name (e.g., SEP08CCA7F71AAE)
        :return: DataFrame with device's call records
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        mask = (
            (self.cdr_df['origDeviceName'] == device_name) |
            (self.cdr_df['destDeviceName'] == device_name)
        )
        return self.cdr_df[mask].copy()
    
    def get_most_active_time(self, user: Optional[str] = None) -> Dict[int, int]:
        """
        Get call activity by hour of day
        
        :param user: Optional - specific user to analyze
        :return: Dictionary with hour -> call count
        """
        if self.cdr_df is None or 'hour' not in self.cdr_df.columns:
            return {}
        
        df = self.get_user_records(user) if user else self.cdr_df
        return df['hour'].value_counts().sort_index().to_dict()
    
    def get_top_callers(self, n: int = 10) -> pd.DataFrame:
        """
        Get top N callers by number of calls
        
        :param n: Number of top callers to return
        :return: DataFrame with caller statistics
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        caller_stats = self.cdr_df.groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum'
        }).reset_index()
        
        caller_stats.columns = ['caller', 'total_calls', 'total_duration', 
                                'avg_duration', 'answered_calls']
        caller_stats = caller_stats.sort_values('total_calls', ascending=False)
        
        return caller_stats.head(n)
    
    def get_top_called(self, n: int = 10) -> pd.DataFrame:
        """
        Get top N called numbers
        
        :param n: Number of top called numbers to return
        :return: DataFrame with called number statistics
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        called_stats = self.cdr_df.groupby('finalCalledPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum'
        }).reset_index()
        
        called_stats.columns = ['called_number', 'total_calls', 'total_duration', 
                                'avg_duration', 'answered_calls']
        called_stats = called_stats.sort_values('total_calls', ascending=False)
        
        return called_stats.head(n)
    
    def get_calls_by_type(self) -> pd.DataFrame:
        """
        Get call statistics grouped by call type (internal/inbound/outbound)
        
        :return: DataFrame with call type statistics
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        type_stats = self.cdr_df.groupby('call_type').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': ['sum', 'mean']
        }).reset_index()
        
        type_stats.columns = ['call_type', 'total_calls', 'total_duration', 
                              'avg_duration', 'answered_calls', 'answer_rate']
        return type_stats
    
    def get_quality_issues(self, 
                          jitter_threshold: int = 30,
                          latency_threshold: int = 150,
                          packet_loss_threshold: float = 1.0) -> pd.DataFrame:
        """
        Get calls with quality issues based on thresholds
        
        :param jitter_threshold: Maximum acceptable jitter in ms
        :param latency_threshold: Maximum acceptable latency in ms
        :param packet_loss_threshold: Maximum acceptable packet loss percentage
        :return: DataFrame with problematic calls
        """
        if self.cmr_df is None:
            return pd.DataFrame()
        
        df = self.cmr_df
        
        quality_mask = (
            (df['origjitter'] > jitter_threshold) |
            (df['destjitter'] > jitter_threshold) |
            (df['origlatency'] > latency_threshold) |
            (df['destlatency'] > latency_threshold) |
            (df['orig_packet_loss_pct'] > packet_loss_threshold) |
            (df['dest_packet_loss_pct'] > packet_loss_threshold)
        )
        
        return df[quality_mask].copy()
    
    def get_close_contacts(self, user: str, top_n: int = 5) -> pd.DataFrame:
        """
        Get the most frequently contacted numbers for a user
        
        :param user: Phone number or user ID
        :param top_n: Number of top contacts to return
        :return: DataFrame with contact statistics
        """
        records = self.get_user_records(user)
        if records.empty:
            return pd.DataFrame()
        
        # Get outgoing calls
        outgoing = records[records['callingPartyNumber'] == user].groupby('finalCalledPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum'
        }).reset_index()
        outgoing.columns = ['contact', 'outgoing_calls', 'outgoing_duration']
        
        # Get incoming calls
        incoming = records[records['finalCalledPartyNumber'] == user].groupby('callingPartyNumber').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum'
        }).reset_index()
        incoming.columns = ['contact', 'incoming_calls', 'incoming_duration']
        
        # Merge
        contacts = pd.merge(outgoing, incoming, on='contact', how='outer').fillna(0)
        contacts['total_calls'] = contacts['outgoing_calls'] + contacts['incoming_calls']
        contacts['total_duration'] = contacts['outgoing_duration'] + contacts['incoming_duration']
        contacts = contacts.sort_values('total_calls', ascending=False)
        
        return contacts.head(top_n)
    
    def get_missed_calls(self, user: Optional[str] = None) -> pd.DataFrame:
        """
        Get missed/unanswered calls
        
        :param user: Optional - specific user to analyze
        :return: DataFrame with missed calls
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        df = self.get_user_records(user) if user else self.cdr_df
        return df[~df['answered']].copy()
    
    def get_connection_matrix(self, users: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Get a connection matrix showing call counts between users
        
        :param users: Optional list of users to include
        :return: DataFrame with connection matrix
        """
        if self.cdr_df is None:
            return pd.DataFrame()
        
        df = self.cdr_df
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
        
        return matrix
    
    # ==================== VISUALIZATION FUNCTIONS ====================
    
    def plot_calls_by_hour(self, user: Optional[str] = None, save_path: Optional[str] = None):
        """
        Plot call distribution by hour of day
        
        :param user: Optional - specific user to analyze
        :param save_path: Optional - path to save the figure
        """
        time_data = self.get_most_active_time(user)
        if not time_data:
            print("No data to plot")
            return
        
        fig, ax = plt.subplots(figsize=(12, 6))
        hours = list(range(24))
        counts = [time_data.get(h, 0) for h in hours]
        
        ax.bar(hours, counts, color='steelblue', edgecolor='navy')
        ax.set_xlabel('Hour of Day', fontsize=12)
        ax.set_ylabel('Number of Calls', fontsize=12)
        title = f'Call Activity by Hour' + (f' - {user}' if user else '')
        ax.set_title(title, fontsize=14)
        ax.set_xticks(hours)
        ax.set_xticklabels([f'{h:02d}:00' for h in hours], rotation=45)
        
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
    
    def plot_call_types(self, save_path: Optional[str] = None):
        """
        Plot pie chart of call types
        
        :param save_path: Optional - path to save the figure
        """
        if self.cdr_df is None:
            return
        
        type_counts = self.cdr_df['call_type'].value_counts()
        
        fig, ax = plt.subplots(figsize=(8, 8))
        colors = ['#2ecc71', '#3498db', '#e74c3c', '#95a5a6']
        ax.pie(type_counts.values, labels=type_counts.index, autopct='%1.1f%%',
               colors=colors[:len(type_counts)], startangle=90)
        ax.set_title('Call Distribution by Type', fontsize=14)
        
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
    
    def plot_call_duration_distribution(self, save_path: Optional[str] = None):
        """
        Plot histogram of call durations
        
        :param save_path: Optional - path to save the figure
        """
        if self.cdr_df is None:
            return
        
        durations = self.cdr_df[self.cdr_df['answered']]['duration']
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.hist(durations, bins=50, color='steelblue', edgecolor='navy', alpha=0.7)
        ax.set_xlabel('Duration (seconds)', fontsize=12)
        ax.set_ylabel('Number of Calls', fontsize=12)
        ax.set_title('Call Duration Distribution', fontsize=14)
        ax.axvline(durations.mean(), color='red', linestyle='--', 
                   label=f'Mean: {durations.mean():.1f}s')
        ax.axvline(durations.median(), color='green', linestyle='--', 
                   label=f'Median: {durations.median():.1f}s')
        ax.legend()
        
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
    
    def plot_quality_metrics(self, save_path: Optional[str] = None):
        """
        Plot quality metrics from CMR data
        
        :param save_path: Optional - path to save the figure
        """
        if self.cmr_df is None:
            print("CMR data not loaded")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # Jitter distribution
        ax1 = axes[0, 0]
        ax1.hist(self.cmr_df['origjitter'], bins=30, alpha=0.7, label='Origin', color='blue')
        ax1.hist(self.cmr_df['destjitter'], bins=30, alpha=0.7, label='Destination', color='orange')
        ax1.set_xlabel('Jitter (ms)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Jitter Distribution')
        ax1.legend()
        
        # Latency distribution
        ax2 = axes[0, 1]
        ax2.hist(self.cmr_df['origlatency'], bins=30, alpha=0.7, label='Origin', color='blue')
        ax2.hist(self.cmr_df['destlatency'], bins=30, alpha=0.7, label='Destination', color='orange')
        ax2.set_xlabel('Latency (ms)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Latency Distribution')
        ax2.legend()
        
        # Packet Loss
        ax3 = axes[1, 0]
        ax3.bar(['Origin', 'Destination'], 
                [self.cmr_df['orignumberPacketsLost'].sum(), 
                 self.cmr_df['destnumberPacketsLost'].sum()],
                color=['blue', 'orange'])
        ax3.set_ylabel('Total Packets Lost')
        ax3.set_title('Total Packet Loss')
        
        # Quality by Device
        ax4 = axes[1, 1]
        device_quality = self.cmr_df.groupby('origdeviceName').agg({
            'origjitter': 'mean',
            'origlatency': 'mean'
        }).head(10)
        device_quality.plot(kind='bar', ax=ax4)
        ax4.set_xlabel('Device')
        ax4.set_ylabel('Avg Value (ms)')
        ax4.set_title('Quality Metrics by Device')
        ax4.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
    
    def plot_top_callers(self, n: int = 10, save_path: Optional[str] = None):
        """
        Plot bar chart of top callers
        
        :param n: Number of top callers to show
        :param save_path: Optional - path to save the figure
        """
        top_callers = self.get_top_callers(n)
        if top_callers.empty:
            return
        
        fig, ax = plt.subplots(figsize=(12, 6))
        bars = ax.barh(range(len(top_callers)), top_callers['total_calls'], color='steelblue')
        ax.set_yticks(range(len(top_callers)))
        ax.set_yticklabels(top_callers['caller'])
        ax.set_xlabel('Number of Calls')
        ax.set_title(f'Top {n} Callers')
        ax.invert_yaxis()
        
        # Add value labels
        for bar, val in zip(bars, top_callers['total_calls']):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    f'{int(val)}', va='center', fontsize=10)
        
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
    
    # ==================== REPORTING FUNCTIONS ====================
    
    def generate_report(self, output_dir: str = 'cdr_report'):
        """
        Generate a comprehensive HTML report
        
        :param output_dir: Directory to save report files
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate summary
        call_summary = self.get_call_summary()
        quality_summary = self.get_quality_summary() if self.cmr_df is not None else {}
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Cisco CDR/CMR Analysis Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
                .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
                h2 { color: #34495e; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }
                table { border-collapse: collapse; width: 100%; margin: 10px 0; }
                th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
                th { background: #3498db; color: white; }
                tr:nth-child(even) { background: #f9f9f9; }
                .stat-box { display: inline-block; background: #ecf0f1; padding: 15px; margin: 5px; border-radius: 5px; min-width: 150px; }
                .stat-value { font-size: 24px; font-weight: bold; color: #2980b9; }
                .stat-label { font-size: 12px; color: #7f8c8d; }
                .good { color: #27ae60; }
                .warning { color: #f39c12; }
                .bad { color: #e74c3c; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 Cisco CDR/CMR Analysis Report</h1>
                <p>Generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</p>
                
                <h2>📞 Call Summary</h2>
                <div class="stats">
        """
        
        # Add stat boxes
        for key, value in call_summary.items():
            if key != 'date_range' and key != 'call_types':
                html += f"""
                    <div class="stat-box">
                        <div class="stat-value">{value}</div>
                        <div class="stat-label">{key.replace('_', ' ').title()}</div>
                    </div>
                """
        
        html += """
                </div>
                
                <h2>📊 Call Types</h2>
                <table>
                    <tr><th>Call Type</th><th>Count</th></tr>
        """
        
        for call_type, count in call_summary.get('call_types', {}).items():
            html += f"<tr><td>{call_type}</td><td>{count}</td></tr>"
        
        if quality_summary:
            html += """
                </table>
                
                <h2>📶 Quality Metrics</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
            """
            
            for key, value in quality_summary.items():
                if isinstance(value, float):
                    value = f"{value:.2f}"
                html += f"<tr><td>{key.replace('_', ' ').title()}</td><td>{value}</td></tr>"
        
        # Add top callers table
        top_callers = self.get_top_callers(10)
        if not top_callers.empty:
            html += """
                </table>
                
                <h2>📱 Top 10 Callers</h2>
                <table>
                    <tr><th>Caller</th><th>Total Calls</th><th>Total Duration</th><th>Answered</th></tr>
            """
            for _, row in top_callers.iterrows():
                html += f"""<tr>
                    <td>{row['caller']}</td>
                    <td>{int(row['total_calls'])}</td>
                    <td>{int(row['total_duration'])}s</td>
                    <td>{int(row['answered_calls'])}</td>
                </tr>"""
        
        html += """
                </table>
            </div>
        </body>
        </html>
        """
        
        report_path = os.path.join(output_dir, 'report.html')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"  ✓ Report generated: {report_path}")
        
        # Save plots
        self.plot_calls_by_hour(save_path=os.path.join(output_dir, 'calls_by_hour.png'))
        self.plot_call_types(save_path=os.path.join(output_dir, 'call_types.png'))
        self.plot_call_duration_distribution(save_path=os.path.join(output_dir, 'duration_distribution.png'))
        if self.cmr_df is not None:
            self.plot_quality_metrics(save_path=os.path.join(output_dir, 'quality_metrics.png'))
        
        # Export data to CSV
        if self.cdr_df is not None:
            self.cdr_df.to_csv(os.path.join(output_dir, 'processed_cdr.csv'), index=False)
        if self.cmr_df is not None:
            self.cmr_df.to_csv(os.path.join(output_dir, 'processed_cmr.csv'), index=False)
        
        print(f"  ✓ All files saved to: {output_dir}/")
    
    def print_summary(self):
        """Print a formatted summary to console"""
        print("\n" + "="*60)
        print("           CISCO CDR/CMR ANALYSIS SUMMARY")
        print("="*60)
        
        if self.cdr_df is not None:
            summary = self.get_call_summary()
            print("\n📞 CALL STATISTICS:")
            print("-"*40)
            print(f"  Total Calls:        {summary.get('total_calls', 'N/A')}")
            print(f"  Answered Calls:     {summary.get('answered_calls', 'N/A')}")
            print(f"  Missed Calls:       {summary.get('missed_calls', 'N/A')}")
            print(f"  Answer Rate:        {summary.get('answer_rate', 'N/A')}")
            print(f"  Total Duration:     {summary.get('total_duration_formatted', 'N/A')}")
            print(f"  Avg Duration:       {summary.get('avg_duration_sec', 0):.1f}s")
            print(f"  Unique Callers:     {summary.get('unique_callers', 'N/A')}")
            print(f"  Unique Devices:     {summary.get('unique_devices', 'N/A')}")
            
            print("\n📊 CALL TYPES:")
            print("-"*40)
            for call_type, count in summary.get('call_types', {}).items():
                print(f"  {call_type:15s}: {count}")
        
        if self.cmr_df is not None:
            quality = self.get_quality_summary()
            print("\n📶 QUALITY METRICS:")
            print("-"*40)
            print(f"  Avg Jitter (orig):    {quality.get('avg_orig_jitter', 0):.2f} ms")
            print(f"  Avg Jitter (dest):    {quality.get('avg_dest_jitter', 0):.2f} ms")
            print(f"  Avg Latency (orig):   {quality.get('avg_orig_latency', 0):.2f} ms")
            print(f"  Avg Latency (dest):   {quality.get('avg_dest_latency', 0):.2f} ms")
            print(f"  Packet Loss (orig):   {quality.get('avg_orig_packet_loss_pct', 0):.3f}%")
            print(f"  Packet Loss (dest):   {quality.get('avg_dest_packet_loss_pct', 0):.3f}%")
        
        print("\n" + "="*60 + "\n")

def main():
    """Main function to demonstrate the analyzer"""
    
    # Initialize analyzer
    analyzer = CiscoCDRAnalyzer()
    
    # Get the directory where the script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # File paths - files in same folder as script
    cdr_file = os.path.join(script_dir, "cdr.csv")
    cmr_file = os.path.join(script_dir, "cmr.csv")
    
    # Load data
    print("\n" + "="*60)
    print("        CISCO CDR/CMR ANALYZER")
    print("="*60 + "\n")
    
    print(f"Looking for files in: {script_dir}")
    print(f"  CDR file: {cdr_file}")
    print(f"  CMR file: {cmr_file}\n")
    
    try:
        # Load CDR
        if os.path.exists(cdr_file):
            analyzer.load_cdr(cdr_file)
        else:
            print(f"Warning: CDR file not found: {cdr_file}")
        
        # Load CMR
        if os.path.exists(cmr_file):
            analyzer.load_cmr(cmr_file)
        else:
            print(f"Warning: CMR file not found: {cmr_file}")
        
        # Merge data if both loaded
        if analyzer.cdr_df is not None and analyzer.cmr_df is not None:
            analyzer.merge_cdr_cmr()
        
        # Print summary
        analyzer.print_summary()
        
        # Generate visualizations
        print("\n📈 Generating visualizations...")
        analyzer.plot_calls_by_hour()
        analyzer.plot_call_types()
        analyzer.plot_call_duration_distribution()
        
        if analyzer.cmr_df is not None:
            analyzer.plot_quality_metrics()
        
        # Show top callers
        print("\n📱 Top 10 Callers:")
        print(analyzer.get_top_callers(10).to_string(index=False))
        
        # Show top called numbers
        print("\n📞 Top 10 Called Numbers:")
        print(analyzer.get_top_called(10).to_string(index=False))
        
        # Show call types breakdown
        print("\n📊 Calls by Type:")
        print(analyzer.get_calls_by_type().to_string(index=False))
        
        # Check for quality issues
        if analyzer.cmr_df is not None:
            quality_issues = analyzer.get_quality_issues()
            if not quality_issues.empty:
                print(f"\n⚠️  Found {len(quality_issues)} calls with quality issues")
        
        # Generate HTML report
        report_dir = os.path.join(script_dir, 'cdr_analysis_report')
        print("\n📄 Generating HTML report...")
        analyzer.generate_report(report_dir)
        
        # Interactive example - get user statistics
        print("\n" + "-"*60)
        print("Example: User Statistics")
        print("-"*60)
        users = analyzer.get_all_users()
        if users:
            sample_user = users[0]
            user_stats = analyzer.get_user_statistics(sample_user)
            print(f"\nStatistics for user: {sample_user}")
            for key, value in user_stats.items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()