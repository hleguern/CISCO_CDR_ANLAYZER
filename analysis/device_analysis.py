"""
Device-based analysis for CDR/CMR data
Includes device utilization, health status, firmware tracking, and quality per device
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


class DeviceAnalyzer(BaseAnalyzer):
    """Device-based analysis of call data"""
    
    # ==================== DEVICE LISTING ====================
    
    def get_all_devices(self) -> List[str]:
        """
        Get all unique device names
        
        :return: Sorted list of device names
        """
        if not self._check_cdr_loaded():
            return []
        
        orig_devices = set(self.cdr['origDeviceName'].unique())
        dest_devices = set(self.cdr['destDeviceName'].unique())
        all_devices = orig_devices | dest_devices
        
        # Filter out empty/invalid values
        all_devices = {d for d in all_devices if d and d not in ['', 'nan', '\\']}
        
        return sorted(list(all_devices))
    
    def get_devices_by_type(self) -> Dict[str, List[str]]:
        """
        Group devices by type (SEP, CIPC, CSF, etc.)
        
        :return: Dictionary mapping device type to list of devices
        """
        devices = self.get_all_devices()
        
        grouped = defaultdict(list)
        
        for device in devices:
            device_upper = device.upper()
            matched = False
            
            for pattern, device_type in self.settings.device_patterns.items():
                if pattern in device_upper:
                    grouped[device_type].append(device)
                    matched = True
                    break
            
            if not matched:
                grouped['Other'].append(device)
        
        return dict(grouped)
    
    def get_device_type_summary(self) -> pd.DataFrame:
        """
        Get summary statistics by device type
        
        :return: DataFrame with device type statistics
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Add device type columns if not present
        if 'orig_device_type' not in df.columns:
            df['orig_device_type'] = df['origDeviceName'].apply(self._get_device_type)
        if 'dest_device_type' not in df.columns:
            df['dest_device_type'] = df['destDeviceName'].apply(self._get_device_type)
        
        # Aggregate by origin device type
        orig_stats = df.groupby('orig_device_type').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
            'origDeviceName': 'nunique',
        }).reset_index()
        
        orig_stats.columns = ['device_type', 'originated_calls', 'total_duration',
                             'avg_duration', 'answered_calls', 'device_count']
        
        # Aggregate by destination device type
        dest_stats = df.groupby('dest_device_type').agg({
            'globalCallID_callId': 'count',
        }).reset_index()
        
        dest_stats.columns = ['device_type', 'received_calls']
        
        # Merge
        summary = pd.merge(orig_stats, dest_stats, on='device_type', how='outer').fillna(0)
        summary['total_calls'] = summary['originated_calls'] + summary['received_calls']
        summary['answer_rate'] = np.where(
            summary['originated_calls'] > 0,
            (summary['answered_calls'] / summary['originated_calls'] * 100).round(2),
            0
        )
        
        return summary.sort_values('total_calls', ascending=False)
    
    def _get_device_type(self, device_name: str) -> str:
        """Get device type from device name"""
        if pd.isna(device_name):
            return 'Unknown'
        device_name = str(device_name).upper()
        for pattern, device_type in self.settings.device_patterns.items():
            if pattern in device_name:
                return device_type
        return 'Unknown'
    
    # ==================== DEVICE SUMMARY ====================
    
    def get_device_summary(self) -> pd.DataFrame:
        """
        Get overview of all devices with statistics
        
        :return: DataFrame with device overview
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Stats as originator
        orig_stats = df.groupby('origDeviceName').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
            'callingPartyNumber': 'nunique',
            'dateTimeOrigination_dt': ['min', 'max'],
        }).reset_index()
        
        orig_stats.columns = ['device', 'originated_calls', 'orig_total_duration',
                             'orig_avg_duration', 'orig_answered', 'users_count',
                             'first_seen', 'last_seen']
        
        # Stats as destination
        dest_stats = df.groupby('destDeviceName').agg({
            'globalCallID_callId': 'count',
            'duration': 'sum',
            'answered': 'sum',
        }).reset_index()
        
        dest_stats.columns = ['device', 'received_calls', 'dest_total_duration',
                             'dest_answered']
        
        # Merge
        summary = pd.merge(orig_stats, dest_stats, on='device', how='outer').fillna(0)
        
        # Calculate totals
        summary['total_calls'] = summary['originated_calls'] + summary['received_calls']
        summary['total_duration'] = summary['orig_total_duration'] + summary['dest_total_duration']
        summary['total_answered'] = summary['orig_answered'] + summary['dest_answered']
        
        # Add device type
        summary['device_type'] = summary['device'].apply(self._get_device_type)
        
        # Calculate answer rate
        summary['answer_rate'] = np.where(
            summary['total_calls'] > 0,
            (summary['total_answered'] / summary['total_calls'] * 100).round(2),
            0
        )
        
        # Days active
        summary['days_active'] = (
            pd.to_datetime(summary['last_seen']) - pd.to_datetime(summary['first_seen'])
        ).dt.days + 1
        
        return summary.sort_values('total_calls', ascending=False)
    
    # ==================== DEVICE UTILIZATION ====================
    
    def get_device_utilization(
        self, 
        device: str,
        period: str = 'daily'
    ) -> pd.DataFrame:
        """
        Get usage statistics for a specific device over time
        
        :param device: Device name
        :param period: 'daily', 'weekly', or 'monthly'
        :return: DataFrame with utilization data
        """
        records = self.get_device_records(device)
        
        if records.empty:
            return pd.DataFrame()
        
        records = records.copy()
        
        if period == 'daily':
            group_col = 'date'
        elif period == 'weekly':
            records['period'] = records['dateTimeOrigination_dt'].dt.to_period('W').astype(str)
            group_col = 'period'
        else:
            records['period'] = records['dateTimeOrigination_dt'].dt.to_period('M').astype(str)
            group_col = 'period'
        
        utilization = records.groupby(group_col).agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
        }).reset_index()
        
        utilization.columns = [group_col, 'total_calls', 'total_duration',
                              'avg_duration', 'answered_calls']
        
        utilization['answer_rate'] = (
            utilization['answered_calls'] / utilization['total_calls'] * 100
        ).round(2)
        
        # Calculate utilization percentage (assuming 8 hours business day)
        if period == 'daily':
            utilization['utilization_pct'] = (
                utilization['total_duration'] / (8 * 3600) * 100
            ).round(2).clip(upper=100)
        
        return utilization
    
    def get_device_records(self, device: str) -> pd.DataFrame:
        """
        Get all call records for a specific device
        
        :param device: Device name
        :return: DataFrame with device's call records
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        mask = (
            (df['origDeviceName'] == device) |
            (df['destDeviceName'] == device)
        )
        
        return df[mask].copy()
    
    def get_device_statistics(self, device: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific device
        
        :param device: Device name
        :return: Dictionary with device statistics
        """
        records = self.get_device_records(device)
        
        if records.empty:
            return {'device': device, 'error': 'Device not found'}
        
        originated = records[records['origDeviceName'] == device]
        received = records[records['destDeviceName'] == device]
        answered = records[records['answered']] if 'answered' in records.columns else pd.DataFrame()
        
        # Get associated users
        users = list(set(
            list(originated['callingPartyNumber'].unique()) +
            list(received['finalCalledPartyNumber'].unique())
        ))
        users = [u for u in users if u and str(u) not in ['', 'nan', 'None']]
        
        stats = {
            'device': device,
            'device_type': self._get_device_type(device),
            'total_calls': len(records),
            'originated_calls': len(originated),
            'received_calls': len(received),
            'answered_calls': len(answered),
            'answer_rate': round(len(answered) / len(records) * 100, 2) if len(records) > 0 else 0,
            'total_duration_sec': int(records['duration'].sum()),
            'avg_duration_sec': round(answered['duration'].mean(), 1) if len(answered) > 0 else 0,
            'associated_users': users,
            'user_count': len(users),
            'call_types': records['call_type'].value_counts().to_dict() if 'call_type' in records.columns else {},
        }
        
        if 'dateTimeOrigination_dt' in records.columns:
            stats['first_seen'] = records['dateTimeOrigination_dt'].min().isoformat()
            stats['last_seen'] = records['dateTimeOrigination_dt'].max().isoformat()
            if 'date' in records.columns:
                stats['active_days'] = records['date'].nunique()
        
        return stats
    
    def get_device_hourly_usage(self, device: str) -> pd.DataFrame:
        """
        Get hourly usage pattern for a device
        
        :param device: Device name
        :return: DataFrame with hourly usage
        """
        records = self.get_device_records(device)
        
        if records.empty or 'hour' not in records.columns:
            return pd.DataFrame()
        
        hourly = records.groupby('hour').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
        }).reindex(range(24), fill_value=0).reset_index()
        
        hourly.columns = ['hour', 'total_calls', 'total_duration',
                         'avg_duration', 'answered_calls']
        
        hourly['hour_label'] = hourly['hour'].apply(lambda h: f"{h:02d}:00")
        
        return hourly
    
    # ==================== DEVICE QUALITY ====================
    
    def get_device_quality_report(
        self, 
        device: str
    ) -> Dict[str, Any]:
        """
        Get quality metrics for a specific device
        
        :param device: Device name
        :return: Dictionary with quality metrics
        """
        if self.cmr is None:
            return {'device': device, 'error': 'CMR data not loaded'}
        
        cmr = self.cmr.copy()
        
        # Filter for device
        device_cmr = cmr[
            (cmr['origdeviceName'] == device) |
            (cmr['destdeviceName'] == device)
        ]
        
        if device_cmr.empty:
            return {'device': device, 'error': 'No quality data for device'}
        
        # Separate origin and destination metrics
        as_orig = device_cmr[device_cmr['origdeviceName'] == device]
        as_dest = device_cmr[device_cmr['destdeviceName'] == device]
        
        quality = {
            'device': device,
            'device_type': self._get_device_type(device),
            'total_records': len(device_cmr),
            'as_originator': {
                'count': len(as_orig),
                'avg_jitter': round(as_orig['origjitter'].mean(), 2) if len(as_orig) > 0 and 'origjitter' in as_orig.columns else 0,
                'max_jitter': round(as_orig['origjitter'].max(), 2) if len(as_orig) > 0 and 'origjitter' in as_orig.columns else 0,
                'avg_latency': round(as_orig['origlatency'].mean(), 2) if len(as_orig) > 0 and 'origlatency' in as_orig.columns else 0,
                'max_latency': round(as_orig['origlatency'].max(), 2) if len(as_orig) > 0 and 'origlatency' in as_orig.columns else 0,
                'total_packets_lost': int(as_orig['orignumberPacketsLost'].sum()) if 'orignumberPacketsLost' in as_orig.columns else 0,
                'avg_packet_loss_pct': round(as_orig['orig_packet_loss_pct'].mean(), 4) if 'orig_packet_loss_pct' in as_orig.columns and len(as_orig) > 0 else 0,
            },
            'as_destination': {
                'count': len(as_dest),
                'avg_jitter': round(as_dest['destjitter'].mean(), 2) if len(as_dest) > 0 and 'destjitter' in as_dest.columns else 0,
                'max_jitter': round(as_dest['destjitter'].max(), 2) if len(as_dest) > 0 and 'destjitter' in as_dest.columns else 0,
                'avg_latency': round(as_dest['destlatency'].mean(), 2) if len(as_dest) > 0 and 'destlatency' in as_dest.columns else 0,
                'max_latency': round(as_dest['destlatency'].max(), 2) if len(as_dest) > 0 and 'destlatency' in as_dest.columns else 0,
                'total_packets_lost': int(as_dest['destnumberPacketsLost'].sum()) if 'destnumberPacketsLost' in as_dest.columns else 0,
                'avg_packet_loss_pct': round(as_dest['dest_packet_loss_pct'].mean(), 4) if 'dest_packet_loss_pct' in as_dest.columns and len(as_dest) > 0 else 0,
            },
        }
        
        # MOS if available
        if 'avg_mos' in device_cmr.columns:
            quality['avg_mos'] = round(device_cmr['avg_mos'].mean(), 2)
            quality['min_mos'] = round(device_cmr['avg_mos'].min(), 2)
        
        # Quality status distribution
        if 'quality_status' in device_cmr.columns:
            quality['quality_distribution'] = device_cmr['quality_status'].value_counts().to_dict()
        
        return quality
    
    def compare_device_quality(
        self, 
        devices: List[str]
    ) -> pd.DataFrame:
        """
        Compare quality metrics across multiple devices
        
        :param devices: List of device names to compare
        :return: DataFrame with comparison
        """
        if self.cmr is None:
            return pd.DataFrame()
        
        comparisons = []
        
        for device in devices:
            quality = self.get_device_quality_report(device)
            
            if 'error' in quality:
                comparisons.append({
                    'device': device,
                    'status': 'no_data'
                })
                continue
            
            comparisons.append({
                'device': device,
                'device_type': quality.get('device_type', 'Unknown'),
                'total_records': quality.get('total_records', 0),
                'avg_jitter_orig': quality['as_originator']['avg_jitter'],
                'avg_jitter_dest': quality['as_destination']['avg_jitter'],
                'avg_latency_orig': quality['as_originator']['avg_latency'],
                'avg_latency_dest': quality['as_destination']['avg_latency'],
                'packets_lost_orig': quality['as_originator']['total_packets_lost'],
                'packets_lost_dest': quality['as_destination']['total_packets_lost'],
                'avg_mos': quality.get('avg_mos', None),
            })
        
        return pd.DataFrame(comparisons)
    
    # ==================== DEVICE HEALTH ====================
    
    def get_device_health_status(
        self,
        jitter_threshold: int = 30,
        latency_threshold: int = 150,
        packet_loss_threshold: float = 1.0
    ) -> pd.DataFrame:
        """
        Identify devices with quality issues
        
        :param jitter_threshold: Max acceptable jitter (ms)
        :param latency_threshold: Max acceptable latency (ms)
        :param packet_loss_threshold: Max acceptable packet loss (%)
        :return: DataFrame with device health status
        """
        if self.cmr is None:
            return pd.DataFrame()
        
        cmr = self.cmr.copy()
        
        # Get all devices from CMR
        orig_devices = set(cmr['origdeviceName'].dropna().unique()) if 'origdeviceName' in cmr.columns else set()
        dest_devices = set(cmr['destdeviceName'].dropna().unique()) if 'destdeviceName' in cmr.columns else set()
        devices = orig_devices | dest_devices
        devices = {d for d in devices if d and str(d) not in ['', 'nan', '\\']}
        
        health_status = []
        
        for device in devices:
            device_cmr = cmr[
                (cmr['origdeviceName'] == device) |
                (cmr['destdeviceName'] == device)
            ]
            
            if device_cmr.empty:
                continue
            
            # Calculate metrics safely
            jitter_cols = []
            latency_cols = []
            
            if 'origjitter' in device_cmr.columns:
                jitter_cols.append('origjitter')
            if 'destjitter' in device_cmr.columns:
                jitter_cols.append('destjitter')
            if 'origlatency' in device_cmr.columns:
                latency_cols.append('origlatency')
            if 'destlatency' in device_cmr.columns:
                latency_cols.append('destlatency')
            
            avg_jitter = device_cmr[jitter_cols].mean().mean() if jitter_cols else 0
            max_jitter = device_cmr[jitter_cols].max().max() if jitter_cols else 0
            avg_latency = device_cmr[latency_cols].mean().mean() if latency_cols else 0
            max_latency = device_cmr[latency_cols].max().max() if latency_cols else 0
            
            total_lost = 0
            total_sent = 0
            
            if 'orignumberPacketsLost' in device_cmr.columns:
                total_lost += device_cmr['orignumberPacketsLost'].sum()
            if 'destnumberPacketsLost' in device_cmr.columns:
                total_lost += device_cmr['destnumberPacketsLost'].sum()
            if 'orignumberPacketsSent' in device_cmr.columns:
                total_sent += device_cmr['orignumberPacketsSent'].sum()
            if 'destnumberPacketsSent' in device_cmr.columns:
                total_sent += device_cmr['destnumberPacketsSent'].sum()
            
            packet_loss_pct = (total_lost / total_sent * 100) if total_sent > 0 else 0
            
            # Determine health status
            issues = []
            if avg_jitter > jitter_threshold:
                issues.append(f"high_jitter({avg_jitter:.1f}ms)")
            if avg_latency > latency_threshold:
                issues.append(f"high_latency({avg_latency:.1f}ms)")
            if packet_loss_pct > packet_loss_threshold:
                issues.append(f"packet_loss({packet_loss_pct:.2f}%)")
            
            if not issues:
                status = 'healthy'
            elif len(issues) == 1:
                status = 'warning'
            else:
                status = 'critical'
            
            health_status.append({
                'device': device,
                'device_type': self._get_device_type(device),
                'call_count': len(device_cmr),
                'avg_jitter': round(avg_jitter, 2) if not pd.isna(avg_jitter) else 0,
                'max_jitter': round(max_jitter, 2) if not pd.isna(max_jitter) else 0,
                'avg_latency': round(avg_latency, 2) if not pd.isna(avg_latency) else 0,
                'max_latency': round(max_latency, 2) if not pd.isna(max_latency) else 0,
                'packet_loss_pct': round(packet_loss_pct, 4),
                'status': status,
                'issues': ', '.join(issues) if issues else 'none',
            })
        
        if not health_status:
            return pd.DataFrame()
        
        result = pd.DataFrame(health_status)
        
        # Sort by status severity
        status_order = {'critical': 0, 'warning': 1, 'healthy': 2}
        result['status_order'] = result['status'].map(status_order)
        result = result.sort_values(['status_order', 'call_count'], ascending=[True, False])
        result = result.drop('status_order', axis=1)
        
        return result
    
    def get_problematic_devices(
        self,
        threshold_pct: float = 10.0
    ) -> pd.DataFrame:
        """
        Get devices with high percentage of quality issues
        
        :param threshold_pct: Minimum percentage of calls with issues
        :return: DataFrame with problematic devices
        """
        health = self.get_device_health_status()
        
        if health.empty:
            return pd.DataFrame()
        
        # Filter to devices with issues
        problematic = health[health['status'].isin(['warning', 'critical'])]
        
        return problematic
    
    # ==================== DEVICE REGISTRATION ====================
    
    def get_device_registration_status(
        self,
        inactive_hours: int = 24
    ) -> pd.DataFrame:
        """
        Determine device online/offline status based on recent activity
        
        :param inactive_hours: Hours without activity to consider offline
        :return: DataFrame with registration status
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        cutoff = datetime.now() - timedelta(hours=inactive_hours)
        
        # Get last activity for each device
        orig_last = df.groupby('origDeviceName')['dateTimeOrigination_dt'].max().reset_index()
        orig_last.columns = ['device', 'last_originated']
        
        dest_last = df.groupby('destDeviceName')['dateTimeOrigination_dt'].max().reset_index()
        dest_last.columns = ['device', 'last_received']
        
        # Merge
        status = pd.merge(orig_last, dest_last, on='device', how='outer')
        
        # Determine last activity
        status['last_activity'] = status[['last_originated', 'last_received']].max(axis=1)
        
        # Determine status
        status['is_active'] = status['last_activity'] >= cutoff
        status['status'] = np.where(status['is_active'], 'online', 'offline')
        status['hours_inactive'] = (
            (datetime.now() - status['last_activity']).dt.total_seconds() / 3600
        ).round(1)
        
        # Add device type
        status['device_type'] = status['device'].apply(self._get_device_type)
        
        return status.sort_values('last_activity', ascending=False)
    
    def get_offline_devices(
        self,
        inactive_hours: int = 24
    ) -> pd.DataFrame:
        """
        Get devices that haven't been active
        
        :param inactive_hours: Hours threshold
        :return: DataFrame with offline devices
        """
        status = self.get_device_registration_status(inactive_hours)
        
        if status.empty:
            return pd.DataFrame()
        
        return status[status['status'] == 'offline'].sort_values('hours_inactive', ascending=False)
    
    # ==================== FIRMWARE TRACKING ====================
    
    def get_firmware_versions(self) -> pd.DataFrame:
        """
        Extract firmware version information from CMR data if available
        Note: Requires firmware info in CMR VQ metrics
        
        :return: DataFrame with firmware versions
        """
        if self.cmr is None:
            return pd.DataFrame()
        
        cmr = self.cmr.copy()
        
        # Try to extract firmware from VQ metrics if available
        firmware_info = []
        
        for col, prefix in [('origvarVQMetrics', 'orig'), ('destvarVQMetrics', 'dest')]:
            if col not in cmr.columns:
                continue
            
            device_col = f'{prefix}deviceName' if prefix == 'orig' else f'{prefix}deviceName'
            if device_col not in cmr.columns:
                device_col = f'{prefix}devicName'  # Handle typo in column name
            
            if device_col not in cmr.columns:
                continue
            
            # Extract unique device entries
            subset = cmr[[device_col, col]].drop_duplicates()
            for _, row in subset.iterrows():
                device = row[device_col]
                vq = str(row[col])
                
                if pd.isna(device) or str(device) in ['', 'nan']:
                    continue
                
                # Try to extract version info
                fw_match = re.search(r'FW=([^;]+)', vq)
                ver_match = re.search(r'Ver=([^;]+)', vq)
                
                firmware_info.append({
                    'device': device,
                    'device_type': self._get_device_type(str(device)),
                    'firmware': fw_match.group(1) if fw_match else None,
                    'version': ver_match.group(1) if ver_match else None,
                })
        
        if not firmware_info:
            # Fallback: group by device and provide count
            devices = self.get_all_devices()
            return pd.DataFrame([{
                'device': d,
                'device_type': self._get_device_type(d),
                'firmware': 'Unknown',
                'version': 'Unknown',
            } for d in devices[:100]])  # Limit to first 100
        
        result = pd.DataFrame(firmware_info).drop_duplicates(subset=['device'])
        return result.sort_values('device_type')
    
    def get_firmware_summary(self) -> pd.DataFrame:
        """
        Get summary of firmware versions by device type
        
        :return: DataFrame with firmware summary
        """
        firmware = self.get_firmware_versions()
        
        if firmware.empty:
            return pd.DataFrame()
        
        summary = firmware.groupby(['device_type', 'firmware']).agg({
            'device': 'count'
        }).reset_index()
        
        summary.columns = ['device_type', 'firmware', 'device_count']
        
        return summary.sort_values(['device_type', 'device_count'], ascending=[True, False])
    
    # ==================== TRUNK ANALYSIS ====================
    
    def get_trunk_devices(self) -> List[str]:
        """
        Get all trunk/gateway devices
        
        :return: List of trunk device names
        """
        devices = self.get_all_devices()
        
        trunks = []
        for device in devices:
            device_upper = device.upper()
            if any(p in device_upper for p in self.settings.trunk_patterns):
                trunks.append(device)
        
        return sorted(trunks)
    
    def get_trunk_utilization(
        self,
        trunk: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get utilization statistics for trunks
        
        :param trunk: Optional specific trunk to analyze
        :return: DataFrame with trunk utilization
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Filter for trunk calls
        trunks = [trunk] if trunk else self.get_trunk_devices()
        
        if not trunks:
            return pd.DataFrame()
        
        # Create mask for trunk calls
        orig_is_trunk = df['origDeviceName'].isin(trunks)
        dest_is_trunk = df['destDeviceName'].isin(trunks)
        
        # Filter and create a proper copy to avoid SettingWithCopyWarning
        trunk_calls = df[orig_is_trunk | dest_is_trunk].copy()
        
        if trunk_calls.empty:
            return pd.DataFrame()
        
        # Add trunk identifier - now safe because we're working with a copy
        trunk_calls['trunk'] = np.where(
            trunk_calls['origDeviceName'].isin(trunks),
            trunk_calls['origDeviceName'],
            trunk_calls['destDeviceName']
        )
        
        trunk_calls['direction'] = np.where(
            trunk_calls['origDeviceName'].isin(trunks),
            'inbound',
            'outbound'
        )
        
        # Aggregate by trunk
        utilization = trunk_calls.groupby('trunk').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
            'answered': 'sum',
            'direction': lambda x: (x == 'inbound').sum(),
        }).reset_index()
        
        utilization.columns = ['trunk', 'total_calls', 'total_duration',
                              'avg_duration', 'answered_calls', 'inbound_calls']
        
        utilization['outbound_calls'] = utilization['total_calls'] - utilization['inbound_calls']
        utilization['answer_rate'] = np.where(
            utilization['total_calls'] > 0,
            (utilization['answered_calls'] / utilization['total_calls'] * 100).round(2),
            0
        )
        
        return utilization.sort_values('total_calls', ascending=False)
    
    def get_trunk_hourly_utilization(
        self,
        trunk: str
    ) -> pd.DataFrame:
        """
        Get hourly utilization for a specific trunk
        
        :param trunk: Trunk device name
        :return: DataFrame with hourly utilization
        """
        records = self.get_device_records(trunk)
        
        if records.empty or 'hour' not in records.columns:
            return pd.DataFrame()
        
        hourly = records.groupby('hour').agg({
            'globalCallID_callId': 'count',
            'duration': ['sum', 'mean'],
        }).reindex(range(24), fill_value=0).reset_index()
        
        hourly.columns = ['hour', 'total_calls', 'total_duration', 'avg_duration']
        hourly['hour_label'] = hourly['hour'].apply(lambda h: f"{h:02d}:00")
        
        return hourly
    
    def get_trunk_concurrent_calls(
        self,
        trunk: Optional[str] = None,
        interval_minutes: int = 5
    ) -> pd.DataFrame:
        """
        Estimate concurrent call usage on trunks
        
        :param trunk: Optional specific trunk
        :param interval_minutes: Time interval for sampling
        :return: DataFrame with concurrent call estimates
        """
        if not self._check_cdr_loaded():
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        trunks = [trunk] if trunk else self.get_trunk_devices()
        
        if not trunks:
            return pd.DataFrame()
        
        # Filter trunk calls
        trunk_calls = df[
            (df['origDeviceName'].isin(trunks)) |
            (df['destDeviceName'].isin(trunks))
        ].copy()
        
        if trunk_calls.empty:
            return pd.DataFrame()
        
        # Ensure we have end time
        if 'dateTimeDisconnect_dt' not in trunk_calls.columns:
            trunk_calls['dateTimeDisconnect_dt'] = (
                trunk_calls['dateTimeOrigination_dt'] + 
                pd.to_timedelta(trunk_calls['duration'], unit='s')
            )
        
        # Create time range
        min_time = trunk_calls['dateTimeOrigination_dt'].min()
        max_time = trunk_calls['dateTimeDisconnect_dt'].max()
        
        time_range = pd.date_range(min_time, max_time, freq=f'{interval_minutes}min')
        
        concurrent_data = []
        
        for ts in time_range:
            # Count calls active at this timestamp
            active = trunk_calls[
                (trunk_calls['dateTimeOrigination_dt'] <= ts) &
                (trunk_calls['dateTimeDisconnect_dt'] >= ts)
            ]
            
            concurrent_data.append({
                'timestamp': ts,
                'concurrent_calls': len(active),
                'hour': ts.hour,
            })
        
        result = pd.DataFrame(concurrent_data)
        
        if not result.empty:
            result['peak'] = result['concurrent_calls'] == result['concurrent_calls'].max()
        
        return result