"""
Heatmap visualizations for CDR/CMR data
Includes hourly heatmaps, quality heatmaps, and connection matrices
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from typing import Optional, Tuple, List, Dict, Any
import logging

from .base_viz import BaseVisualizer

logger = logging.getLogger(__name__)


class HeatmapGenerator(BaseVisualizer):
    """Generate heatmap visualizations for CDR/CMR analysis"""
    
    def _ensure_full_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure DataFrame has all 24 hours as index
        
        :param df: DataFrame with hour as index
        :return: DataFrame with all 24 hours
        """
        if df.empty:
            return df
        
        # Create full hour index (0-23)
        full_hours = pd.Index(range(24), name=df.index.name or 'hour')
        
        # Reindex to include all hours, fill missing with 0
        df_full = df.reindex(full_hours, fill_value=0)
        
        return df_full
    
    def _ensure_full_hour_day_matrix(
        self, 
        df: pd.DataFrame,
        fill_value: float = 0
    ) -> pd.DataFrame:
        """
        Ensure DataFrame has all 24 hours and all 7 days
        
        :param df: DataFrame with hours as index and days as columns
        :param fill_value: Value to fill missing cells
        :return: Complete 24x7 DataFrame
        """
        if df.empty:
            return df
        
        # Define expected structure
        all_hours = list(range(24))
        all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        # Get current columns (days) - preserve order if they exist
        current_days = [d for d in all_days if d in df.columns]
        missing_days = [d for d in all_days if d not in df.columns]
        
        # Add missing days
        for day in missing_days:
            df[day] = fill_value
        
        # Reorder columns to standard day order
        df = df.reindex(columns=all_days)
        
        # Reindex rows to have all 24 hours
        df = df.reindex(all_hours, fill_value=fill_value)
        
        # Ensure index name
        df.index.name = 'hour'
        
        return df
    
    def plot_hourly_heatmap(
        self,
        metric: str = 'count',
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 8),
        cmap: str = 'YlOrRd'
    ) -> Optional[plt.Figure]:
        """
        Plot Hour x Day of Week heatmap
        
        :param metric: 'count', 'duration', 'answer_rate'
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :param cmap: Colormap name
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        try:
            heatmap_data = self.analyzer.time.get_hourly_heatmap_by_metric(metric)
            
            if heatmap_data.empty:
                logger.warning(f"No heatmap data available for metric: {metric}")
                return None
            
            # Ensure we have all 24 hours and all 7 days
            heatmap_data = self._ensure_full_hour_day_matrix(heatmap_data)
            
            fig, ax = self._create_figure(figsize=figsize)
            
            # Determine annotation format
            if metric == 'count':
                fmt = '.0f'
            elif metric == 'answer_rate':
                fmt = '.1f'
            else:
                fmt = '.1f'
            
            # Create heatmap
            sns.heatmap(
                heatmap_data,
                ax=ax,
                cmap=cmap,
                annot=True,
                fmt=fmt,
                linewidths=0.5,
                cbar_kws={'label': self._get_metric_label(metric)}
            )
            
            ax.set_xlabel('Day of Week', fontsize=12)
            ax.set_ylabel('Hour of Day', fontsize=12)
            
            title_map = {
                'count': 'Call Volume',
                'duration': 'Average Duration (seconds)',
                'answer_rate': 'Answer Rate (%)'
            }
            ax.set_title(f'{title_map.get(metric, metric)} - Hour vs Day', 
                        fontsize=14, fontweight='bold')
            
            # Set y-axis labels based on actual index
            hour_labels = [f'{h:02d}:00' for h in heatmap_data.index]
            ax.set_yticklabels(hour_labels, rotation=0)
            
            plt.tight_layout()
            
            if save_path:
                self._save_figure(fig, f'heatmap_{metric}.png', save_path)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating hourly heatmap: {e}")
            return None
    
    def plot_quality_heatmap(
        self,
        metric: str = 'mos',
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 8),
        cmap: str = 'RdYlGn'
    ) -> Optional[plt.Figure]:
        """
        Plot quality metrics heatmap (Hour x Day)
        
        :param metric: 'mos', 'jitter', 'latency', 'packet_loss'
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :param cmap: Colormap name
        :return: Figure object
        """
        try:
            heatmap_data = self.analyzer.quality.get_quality_heatmap(metric)
            
            if heatmap_data.empty:
                logger.warning(f"No quality heatmap data available for metric: {metric}")
                return None
            
            # Determine appropriate fill value for missing data
            if metric == 'mos':
                fill_value = np.nan  # Don't show MOS where there's no data
            else:
                fill_value = 0
            
            # Ensure we have all 24 hours and all 7 days
            heatmap_data = self._ensure_full_hour_day_matrix(heatmap_data, fill_value=fill_value)
            
            fig, ax = self._create_figure(figsize=figsize)
            
            # For jitter/latency/packet_loss, reverse colormap (lower is better)
            if metric in ['jitter', 'latency', 'packet_loss']:
                if not cmap.endswith('_r'):
                    cmap = cmap + '_r'
            
            # Create annotations format
            fmt = '.2f' if metric in ['mos', 'packet_loss'] else '.0f'
            
            # Create mask for NaN values
            mask = heatmap_data.isna()
            
            sns.heatmap(
                heatmap_data,
                ax=ax,
                cmap=cmap,
                annot=True,
                fmt=fmt,
                linewidths=0.5,
                mask=mask,
                cbar_kws={'label': self._get_quality_metric_label(metric)}
            )
            
            ax.set_xlabel('Day of Week', fontsize=12)
            ax.set_ylabel('Hour of Day', fontsize=12)
            ax.set_title(f'{metric.upper()} Quality Heatmap', fontsize=14, fontweight='bold')
            
            # Set y-axis labels based on actual index
            hour_labels = [f'{h:02d}:00' for h in heatmap_data.index]
            ax.set_yticklabels(hour_labels, rotation=0)
            
            plt.tight_layout()
            
            if save_path:
                self._save_figure(fig, f'quality_heatmap_{metric}.png', save_path)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating quality heatmap: {e}")
            return None
    def plot_connection_heatmap(
        self,
        users: Optional[List[str]] = None,
        max_users: int = 20,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 10)
    ) -> Optional[plt.Figure]:
        """
        Plot connection matrix heatmap between users
        
        :param users: List of users to include
        :param max_users: Maximum number of users if not specified
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        try:
            # If no users specified, get top callers
            if users is None:
                top_callers = self.analyzer.users.get_top_callers(max_users)
                if top_callers.empty:
                    logger.warning("No caller data available for connection heatmap")
                    return None
                users = top_callers['caller'].tolist()
            
            if not users:
                logger.warning("No users specified for connection heatmap")
                return None
            
            # Filter to valid users only
            users = [u for u in users if u and str(u) not in ['', 'nan', 'None']]
            
            if len(users) < 2:
                logger.warning("Need at least 2 users for connection heatmap")
                return None
            
            matrix = self.analyzer.users.get_connection_matrix(users)
            
            if matrix.empty:
                logger.warning("Empty connection matrix")
                return None
            
            # Get dimensions
            n_rows, n_cols = matrix.shape
            
            # Check if matrix is square
            is_square = n_rows == n_cols
            
            # Adjust figure size based on matrix dimensions
            adjusted_figsize = (
                max(figsize[0], n_cols * 0.8),
                max(figsize[1], n_rows * 0.6)
            )
            
            fig, ax = self._create_figure(figsize=adjusted_figsize)
            
            # Create mask for diagonal (self-calls) only if matrix is square
            if is_square and n_rows > 0:
                mask = np.eye(n_rows, dtype=bool)
            else:
                # Non-square or empty - no mask
                mask = None
            
            # Determine if annotations should be shown (too many cells = hard to read)
            show_annot = (n_rows * n_cols) <= 400  # Max 20x20 for annotations
            
            sns.heatmap(
                matrix,
                ax=ax,
                cmap='Blues',
                annot=show_annot,
                fmt='d' if show_annot else '',
                mask=mask,
                linewidths=0.5 if (n_rows * n_cols) <= 225 else 0,  # Lines only for smaller matrices
                square=is_square,
                cbar_kws={'label': 'Number of Calls'}
            )
            
            ax.set_xlabel('Called', fontsize=12)
            ax.set_ylabel('Caller', fontsize=12)
            ax.set_title('User Connection Matrix', fontsize=14, fontweight='bold')
            
            # Rotate labels for readability
            plt.xticks(rotation=45, ha='right', fontsize=8 if n_cols > 15 else 10)
            plt.yticks(rotation=0, fontsize=8 if n_rows > 15 else 10)
            
            plt.tight_layout()
            
            if save_path:
                self._save_figure(fig, 'connection_heatmap.png', save_path)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating connection heatmap: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    def plot_department_connection_heatmap(
        self,
        dept_mapping: Dict[str, List[str]],
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (10, 8)
    ) -> Optional[plt.Figure]:
        """
        Plot inter-department call matrix
        
        :param dept_mapping: Dictionary mapping department names to extensions
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        try:
            matrix = self.analyzer.users.get_inter_department_calls(dept_mapping)
            
            if matrix.empty:
                logger.warning("No inter-department call data available")
                return None
            
            fig, ax = self._create_figure(figsize=figsize)
            
            sns.heatmap(
                matrix,
                ax=ax,
                cmap='Greens',
                annot=True,
                fmt='d',
                linewidths=1,
                square=True,
                cbar_kws={'label': 'Number of Calls'}
            )
            
            ax.set_xlabel('Called Department', fontsize=12)
            ax.set_ylabel('Calling Department', fontsize=12)
            ax.set_title('Inter-Department Call Matrix', fontsize=14, fontweight='bold')
            
            plt.xticks(rotation=45, ha='right')
            plt.yticks(rotation=0)
            
            plt.tight_layout()
            
            if save_path:
                self._save_figure(fig, 'department_heatmap.png', save_path)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating department heatmap: {e}")
            return None
    
    def plot_device_quality_heatmap(
        self,
        devices: Optional[List[str]] = None,
        max_devices: int = 15,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 10)
    ) -> Optional[plt.Figure]:
        """
        Plot device quality comparison heatmap
        
        :param devices: List of devices to compare
        :param max_devices: Maximum devices if not specified
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if self.cmr is None:
            logger.warning("CMR data not loaded - cannot create device quality heatmap")
            return None
        
        try:
            # Get devices if not specified
            if devices is None:
                device_summary = self.analyzer.devices.get_device_summary()
                if device_summary.empty:
                    logger.warning("No device data available")
                    return None
                devices = device_summary.head(max_devices)['device'].tolist()
            
            if not devices:
                logger.warning("No devices specified for quality heatmap")
                return None
            
            comparison = self.analyzer.devices.compare_device_quality(devices)
            
            if comparison.empty:
                logger.warning("No device quality comparison data available")
                return None
            
            # Prepare data for heatmap
            metrics = ['avg_jitter_orig', 'avg_latency_orig', 'avg_mos']
            available_metrics = [m for m in metrics if m in comparison.columns]
            
            if not available_metrics:
                logger.warning("No quality metrics available for heatmap")
                return None
            
            # Filter out devices with no data (status='no_data')
            if 'status' in comparison.columns:
                comparison = comparison[comparison['status'] != 'no_data']
            
            if comparison.empty:
                logger.warning("All devices have no quality data")
                return None
            
            # Normalize metrics for visualization
            comparison_norm = comparison.set_index('device')[available_metrics].copy()
            
            # Create the display data (original values for annotation)
            display_data = comparison.set_index('device')[available_metrics].copy()
            
            # For MOS, invert so higher is better (green) - for normalized version only
            if 'avg_mos' in comparison_norm.columns:
                max_mos = comparison_norm['avg_mos'].max()
                if not pd.isna(max_mos):
                    comparison_norm['avg_mos'] = max_mos - comparison_norm['avg_mos']
            
            fig, ax = self._create_figure(figsize=figsize)
            
            sns.heatmap(
                comparison_norm.T,
                ax=ax,
                cmap='RdYlGn_r',  # Lower values (green) are better
                annot=display_data.T,
                fmt='.1f',
                linewidths=0.5,
                cbar_kws={'label': 'Quality Score (lower is better for jitter/latency)'}
            )
            
            ax.set_xlabel('Device', fontsize=12)
            ax.set_ylabel('Metric', fontsize=12)
            ax.set_title('Device Quality Comparison', fontsize=14, fontweight='bold')
            
            plt.xticks(rotation=45, ha='right')
            
            plt.tight_layout()
            
            if save_path:
                self._save_figure(fig, 'device_quality_heatmap.png', save_path)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating device quality heatmap: {e}")
            return None
    
    def plot_hunt_group_performance_heatmap(
        self,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> Optional[plt.Figure]:
        """
        Plot hunt group performance heatmap
        
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        try:
            summary = self.analyzer.hunt_groups.get_hunt_group_summary()
            
            if summary.empty:
                logger.warning("No hunt group data available for heatmap")
                return None
            
            # Select metrics for heatmap
            metrics = ['answer_rate', 'abandonment_rate', 'avg_wait_sec']
            available = [m for m in metrics if m in summary.columns]
            
            if not available:
                logger.warning("No hunt group metrics available for heatmap")
                return None
            
            heatmap_data = summary.set_index('hunt_dn')[available]
            
            if heatmap_data.empty:
                return None
            
            fig, ax = self._create_figure(figsize=figsize)
            
            sns.heatmap(
                heatmap_data.T,
                ax=ax,
                cmap='RdYlGn',
                annot=True,
                fmt='.1f',
                linewidths=0.5,
                cbar_kws={'label': 'Value'}
            )
            
            ax.set_xlabel('Hunt Group', fontsize=12)
            ax.set_ylabel('Metric', fontsize=12)
            ax.set_title('Hunt Group Performance', fontsize=14, fontweight='bold')
            
            plt.xticks(rotation=45, ha='right')
            
            plt.tight_layout()
            
            if save_path:
                self._save_figure(fig, 'hunt_group_heatmap.png', save_path)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating hunt group heatmap: {e}")
            return None
    
    def plot_hourly_call_volume_heatmap(
        self,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (16, 6)
    ) -> Optional[plt.Figure]:
        """
        Plot hourly call volume heatmap across dates
        
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        try:
            df = self.cdr.copy()
            
            if 'date' not in df.columns or 'hour' not in df.columns:
                logger.warning("Required columns (date, hour) not available")
                return None
            
            # Create pivot table: hours vs dates
            pivot = df.pivot_table(
                values='globalCallID_callId',
                index='hour',
                columns='date',
                aggfunc='count',
                fill_value=0
            )
            
            # Ensure all 24 hours are present
            pivot = pivot.reindex(range(24), fill_value=0)
            
            fig, ax = self._create_figure(figsize=figsize)
            
            sns.heatmap(
                pivot,
                ax=ax,
                cmap='YlOrRd',
                cbar_kws={'label': 'Call Count'}
            )
            
            ax.set_xlabel('Date', fontsize=12)
            ax.set_ylabel('Hour of Day', fontsize=12)
            ax.set_title('Hourly Call Volume Over Time', fontsize=14, fontweight='bold')
            
            # Set y-axis labels
            hour_labels = [f'{h:02d}:00' for h in pivot.index]
            ax.set_yticklabels(hour_labels, rotation=0)
            
            # Rotate x-axis labels
            plt.xticks(rotation=45, ha='right')
            
            plt.tight_layout()
            
            if save_path:
                self._save_figure(fig, 'hourly_volume_over_time.png', save_path)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating hourly volume heatmap: {e}")
            return None
    
    def _get_metric_label(self, metric: str) -> str:
        """Get human-readable metric label"""
        labels = {
            'count': 'Number of Calls',
            'duration': 'Avg Duration (seconds)',
            'answer_rate': 'Answer Rate (%)'
        }
        return labels.get(metric, metric)
    
    def _get_quality_metric_label(self, metric: str) -> str:
        """Get human-readable quality metric label"""
        labels = {
            'mos': 'MOS Score',
            'jitter': 'Jitter (ms)',
            'latency': 'Latency (ms)',
            'packet_loss': 'Packet Loss (%)'
        }
        return labels.get(metric, metric)