"""
Chart generation for CDR/CMR data
Includes line charts, bar charts, pie charts, and trend visualizations
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator, FuncFormatter
import seaborn as sns
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any, Union
import logging

from .base_viz import BaseVisualizer

logger = logging.getLogger(__name__)


class ChartGenerator(BaseVisualizer):
    """Generate various charts for CDR/CMR analysis"""
    
    # ==================== CALL VOLUME CHARTS ====================
    
    def plot_calls_by_hour(
        self,
        user: Optional[str] = None,
        call_type: Optional[str] = None,
        show_avg_line: bool = True,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 6)
    ) -> Optional[plt.Figure]:
        """
        Plot call distribution by hour of day
        
        :param user: Optional user filter
        :param call_type: Optional call type filter
        :param show_avg_line: Show average line
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        df = self.cdr.copy()
        
        if user:
            df = df[(df['callingPartyNumber'] == user) | 
                    (df['finalCalledPartyNumber'] == user)]
        
        if call_type:
            df = df[df['call_type'] == call_type]
        
        if df.empty:
            logger.warning("No data to plot")
            return None
        
        # Aggregate by hour
        hourly = df.groupby('hour').agg({
            'globalCallID_callId': 'count',
            'answered': 'sum'
        }).reindex(range(24), fill_value=0)
        
        fig, ax = self._create_figure(figsize=figsize)
        
        # Create bar chart
        x = range(24)
        width = 0.8
        
        bars = ax.bar(x, hourly['globalCallID_callId'], width, 
                     color=self.COLORS['primary'], alpha=0.8,
                     label='Total Calls', edgecolor='white')
        
        # Overlay answered calls
        ax.bar(x, hourly['answered'], width, 
               color=self.COLORS['success'], alpha=0.6,
               label='Answered', edgecolor='white')
        
        # Add average line
        if show_avg_line:
            avg = hourly['globalCallID_callId'].mean()
            ax.axhline(y=avg, color=self.COLORS['danger'], linestyle='--', 
                      linewidth=2, label=f'Average ({avg:.0f})')
        
        # Formatting
        ax.set_xticks(x)
        ax.set_xticklabels([f'{h:02d}:00' for h in x], rotation=45, ha='right')
        
        self._format_axis_labels(
            ax,
            xlabel='Hour of Day',
            ylabel='Number of Calls',
            title='Call Distribution by Hour' + (f' - {user}' if user else '')
        )
        
        ax.legend(loc='upper right')
        self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'calls_by_hour.png', save_path)
        
        return fig
    
    def plot_daily_trend(
        self,
        days: int = 30,
        show_rolling_avg: bool = True,
        rolling_window: int = 7,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 6)
    ) -> Optional[plt.Figure]:
        """
        Plot daily call volume trend
        
        :param days: Number of days to show
        :param show_rolling_avg: Show rolling average line
        :param rolling_window: Window for rolling average
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        daily = self.analyzer.time.get_daily_call_volume()
        
        if daily.empty:
            return None
        
        # Get last N days
        daily = daily.tail(days)
        
        fig, ax = self._create_figure(figsize=figsize)
        
        # Plot bars for daily volume
        ax.bar(daily['date'], daily['total_calls'], 
               color=self.COLORS['primary'], alpha=0.6,
               label='Daily Calls', width=0.8)
        
        # Rolling average
        if show_rolling_avg and len(daily) >= rolling_window:
            rolling_avg = daily['total_calls'].rolling(window=rolling_window).mean()
            ax.plot(daily['date'], rolling_avg, 
                   color=self.COLORS['danger'], linewidth=2.5,
                   label=f'{rolling_window}-day Moving Avg')
        
        # Format x-axis dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days // 10)))
        
        plt.xticks(rotation=45, ha='right')
        
        self._format_axis_labels(
            ax,
            xlabel='Date',
            ylabel='Number of Calls',
            title=f'Daily Call Volume (Last {days} Days)'
        )
        
        ax.legend(loc='upper left')
        self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'daily_trend.png', save_path)
        
        return fig
    
    def plot_weekly_comparison(
        self,
        weeks: int = 8,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 6)
    ) -> Optional[plt.Figure]:
        """
        Compare call volumes week over week
        
        :param weeks: Number of weeks to compare
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        weekly = self.analyzer.time.get_weekly_trends(weeks=weeks)
        
        if weekly.empty:
            return None
        
        fig, ax = self._create_figure(figsize=figsize)
        
        x = range(len(weekly))
        width = 0.35
        
        # Total calls
        bars1 = ax.bar([i - width/2 for i in x], weekly['total_calls'], 
                       width, label='Total Calls', color=self.COLORS['primary'])
        
        # Answered calls
        bars2 = ax.bar([i + width/2 for i in x], weekly['answered_calls'], 
                       width, label='Answered', color=self.COLORS['success'])
        
        ax.set_xticks(x)
        ax.set_xticklabels(weekly['year_week'], rotation=45, ha='right')
        
        self._format_axis_labels(
            ax,
            xlabel='Week',
            ylabel='Number of Calls',
            title='Weekly Call Volume Comparison'
        )
        
        ax.legend()
        self._apply_style(ax)
        
        # Add week-over-week change annotation
        if 'calls_change_pct' in weekly.columns:
            for i, (_, row) in enumerate(weekly.iterrows()):
                if pd.notna(row['calls_change_pct']) and i > 0:
                    change = row['calls_change_pct']
                    color = self.COLORS['success'] if change >= 0 else self.COLORS['danger']
                    ax.annotate(
                        f'{change:+.1f}%',
                        xy=(i - width/2, row['total_calls']),
                        xytext=(0, 5),
                        textcoords='offset points',
                        ha='center', va='bottom',
                        fontsize=8, color=color
                    )
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'weekly_comparison.png', save_path)
        
        return fig
    
    def plot_monthly_comparison(
        self,
        months: int = 12,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 6)
    ) -> Optional[plt.Figure]:
        """
        Compare call volumes month over month
        
        :param months: Number of months to compare
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        monthly = self.analyzer.time.get_monthly_trends(months=months)
        
        if monthly.empty:
            return None
        
        fig, ax = self._create_figure(figsize=figsize)
        
        x = range(len(monthly))
        
        # Create bars with gradient based on change
        colors = []
        for _, row in monthly.iterrows():
            if pd.isna(row.get('calls_change_pct', np.nan)):
                colors.append(self.COLORS['primary'])
            elif row['calls_change_pct'] >= 0:
                colors.append(self.COLORS['success'])
            else:
                colors.append(self.COLORS['danger'])
        
        bars = ax.bar(x, monthly['total_calls'], color=colors, alpha=0.8)
        
        # Add answer rate line on secondary axis
        ax2 = ax.twinx()
        ax2.plot(x, monthly['answer_rate'], color=self.COLORS['warning'], 
                marker='o', linewidth=2, label='Answer Rate %')
        ax2.set_ylabel('Answer Rate (%)', fontsize=11)
        ax2.set_ylim(0, 100)
        
        ax.set_xticks(x)
        ax.set_xticklabels(monthly['year_month'], rotation=45, ha='right')
        
        self._format_axis_labels(
            ax,
            xlabel='Month',
            ylabel='Number of Calls',
            title='Monthly Call Volume and Answer Rate'
        )
        
        # Combined legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'monthly_comparison.png', save_path)
        
        return fig
    
    # ==================== CALL TYPE CHARTS ====================
    
    def plot_call_types(
        self,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (10, 8)
    ) -> Optional[plt.Figure]:
        """
        Plot pie chart of call types
        
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        type_counts = self.cdr['call_type'].value_counts()
        
        fig, ax = self._create_figure(figsize=figsize)
        
        colors = self.PALETTE_CATEGORICAL[:len(type_counts)]
        
        wedges, texts, autotexts = ax.pie(
            type_counts.values,
            labels=type_counts.index,
            autopct='%1.1f%%',
            colors=colors,
            startangle=90,
            explode=[0.02] * len(type_counts),
            shadow=True
        )
        
        # Style the percentage text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
        
        ax.set_title('Call Distribution by Type', fontsize=14, fontweight='bold')
        
        # Add legend with counts
        legend_labels = [f'{label}: {count:,}' 
                        for label, count in zip(type_counts.index, type_counts.values)]
        ax.legend(wedges, legend_labels, title="Call Types", 
                 loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'call_types.png', save_path)
        
        return fig
    
    def plot_call_duration_distribution(
        self,
        bins: int = 50,
        max_duration: Optional[int] = None,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 6)
    ) -> Optional[plt.Figure]:
        """
        Plot histogram of call durations
        
        :param bins: Number of histogram bins
        :param max_duration: Maximum duration to include
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        durations = self.cdr[self.cdr['answered']]['duration']
        
        if max_duration:
            durations = durations[durations <= max_duration]
        
        fig, ax = self._create_figure(figsize=figsize)
        
        # Create histogram
        n, bins_arr, patches = ax.hist(
            durations, bins=bins, 
            color=self.COLORS['primary'], 
            alpha=0.7, edgecolor='white'
        )
        
        # Add statistical lines
        mean_val = durations.mean()
        median_val = durations.median()
        
        ax.axvline(mean_val, color=self.COLORS['danger'], linestyle='--', 
                  linewidth=2, label=f'Mean: {mean_val:.1f}s')
        ax.axvline(median_val, color=self.COLORS['success'], linestyle='--', 
                  linewidth=2, label=f'Median: {median_val:.1f}s')
        
        # Add percentile markers
        p90 = durations.quantile(0.90)
        ax.axvline(p90, color=self.COLORS['warning'], linestyle=':', 
                  linewidth=2, label=f'90th %ile: {p90:.1f}s')
        
        self._format_axis_labels(
            ax,
            xlabel='Duration (seconds)',
            ylabel='Number of Calls',
            title='Call Duration Distribution'
        )
        
        ax.legend(loc='upper right')
        self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'duration_distribution.png', save_path)
        
        return fig
    
    # ==================== TOP CALLERS/CALLED CHARTS ====================
    
    def plot_top_callers(
        self,
        n: int = 10,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> Optional[plt.Figure]:
        """
        Plot horizontal bar chart of top callers
        
        :param n: Number of top callers to show
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        top_callers = self.analyzer.users.get_top_callers(n)
        
        if top_callers.empty:
            return None
        
        fig, ax = self._create_figure(figsize=figsize)
        
        y_pos = range(len(top_callers))
        
        # Create horizontal bar chart
        bars = ax.barh(y_pos, top_callers['total_calls'], 
                       color=self.COLORS['primary'], alpha=0.8)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(top_callers['caller'])
        ax.invert_yaxis()
        
        # Add value labels
        for bar, val in zip(bars, top_callers['total_calls']):
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                   f'{int(val):,}', va='center', fontsize=10)
        
        # Add answer rate indicator
        for i, (_, row) in enumerate(top_callers.iterrows()):
            rate = row['answer_rate']
            color = self._get_color_for_value(rate/100, (0.7, 0.9))
            ax.text(2, i, f'({rate:.0f}%)', va='center', fontsize=9, color=color)
        
        self._format_axis_labels(
            ax,
            xlabel='Number of Calls',
            ylabel='',
            title=f'Top {n} Callers'
        )
        
        self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'top_callers.png', save_path)
        
        return fig
    
    def plot_top_called(
        self,
        n: int = 10,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> Optional[plt.Figure]:
        """
        Plot horizontal bar chart of most called numbers
        
        :param n: Number of top called numbers to show
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        top_called = self.analyzer.users.get_top_called(n)
        
        if top_called.empty:
            return None
        
        fig, ax = self._create_figure(figsize=figsize)
        
        y_pos = range(len(top_called))
        
        bars = ax.barh(y_pos, top_called['total_calls'], 
                       color=self.COLORS['secondary'], alpha=0.8)
        
        ax.set_yticks(y_pos)
        ax.set_yticklabels(top_called['called_number'])
        ax.invert_yaxis()
        
        for bar, val in zip(bars, top_called['total_calls']):
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                   f'{int(val):,}', va='center', fontsize=10)
        
        self._format_axis_labels(
            ax,
            xlabel='Number of Calls',
            ylabel='',
            title=f'Top {n} Called Numbers'
        )
        
        self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'top_called.png', save_path)
        
        return fig
    
    # ==================== QUALITY CHARTS ====================
    
    def plot_quality_metrics(
        self,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 10)
    ) -> Optional[plt.Figure]:
        """
        Plot comprehensive quality metrics dashboard
        
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if self.cmr is None:
            logger.warning("CMR data not loaded")
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # 1. Jitter Distribution
        ax1 = axes[0, 0]
        ax1.hist(self.cmr['origjitter'], bins=30, alpha=0.7, 
                label='Origin', color=self.COLORS['primary'])
        ax1.hist(self.cmr['destjitter'], bins=30, alpha=0.7, 
                label='Destination', color=self.COLORS['warning'])
        ax1.axvline(30, color=self.COLORS['danger'], linestyle='--', 
                   label='Warning (30ms)')
        ax1.set_xlabel('Jitter (ms)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Jitter Distribution')
        ax1.legend()
        
        # 2. Latency Distribution
        ax2 = axes[0, 1]
        ax2.hist(self.cmr['origlatency'], bins=30, alpha=0.7, 
                label='Origin', color=self.COLORS['primary'])
        ax2.hist(self.cmr['destlatency'], bins=30, alpha=0.7, 
                label='Destination', color=self.COLORS['warning'])
        ax2.axvline(150, color=self.COLORS['danger'], linestyle='--', 
                   label='Warning (150ms)')
        ax2.set_xlabel('Latency (ms)')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Latency Distribution')
        ax2.legend()
        
        # 3. Packet Loss
        ax3 = axes[1, 0]
        packet_data = {
            'Origin Lost': self.cmr['orignumberPacketsLost'].sum(),
            'Dest Lost': self.cmr['destnumberPacketsLost'].sum(),
        }
        bars = ax3.bar(packet_data.keys(), packet_data.values(), 
                       color=[self.COLORS['primary'], self.COLORS['warning']])
        ax3.set_ylabel('Total Packets Lost')
        ax3.set_title('Total Packet Loss')
        self._add_value_labels(ax3, bars, format_str='{:,.0f}')
        
        # 4. MOS Distribution (if available)
        ax4 = axes[1, 1]
        if 'avg_mos' in self.cmr.columns:
            mos_data = self.cmr['avg_mos'].dropna()
            ax4.hist(mos_data, bins=20, color=self.COLORS['success'], alpha=0.7)
            ax4.axvline(3.5, color=self.COLORS['warning'], linestyle='--', 
                       label='Acceptable (3.5)')
            ax4.axvline(4.0, color=self.COLORS['success'], linestyle='--', 
                       label='Good (4.0)')
            ax4.set_xlabel('MOS Score')
            ax4.set_ylabel('Frequency')
            ax4.set_title('MOS Score Distribution')
            ax4.legend()
        else:
            # Quality status distribution
            if 'quality_status' in self.cmr.columns:
                status_counts = self.cmr['quality_status'].value_counts()
                colors = {
                    'good': self.COLORS['success'],
                    'acceptable': self.COLORS['primary'],
                    'fair': self.COLORS['warning'],
                    'poor': self.COLORS['danger'],
                    'unknown': self.COLORS['muted'],
                }
                bar_colors = [colors.get(s, self.COLORS['muted']) for s in status_counts.index]
                ax4.bar(status_counts.index, status_counts.values, color=bar_colors)
                ax4.set_ylabel('Number of Calls')
                ax4.set_title('Quality Status Distribution')
        
        for ax in axes.flat:
            self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'quality_metrics.png', save_path)
        
        return fig
    
    def plot_quality_trend(
        self,
        metric: str = 'mos',
        period: str = 'daily',
        days: int = 30,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 6)
    ) -> Optional[plt.Figure]:
        """
        Plot quality metric trend over time
        
        :param metric: 'mos', 'jitter', 'latency', 'packet_loss'
        :param period: 'daily', 'weekly', 'monthly'
        :param days: Number of days to include
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        trend = self.analyzer.quality.get_quality_trend_over_time(period, metric)
        
        if trend.empty:
            return None
        
        trend = trend.tail(days) if period == 'daily' else trend
        
        fig, ax = self._create_figure(figsize=figsize)
        
        # Get the main metric column
        metric_cols = [c for c in trend.columns if 'mean' in c.lower() or metric in c.lower()]
        
        if not metric_cols:
            return None
        
        main_col = metric_cols[0]
        x = range(len(trend))
        
        # Plot line
        ax.plot(x, trend[main_col], marker='o', linewidth=2, 
               color=self.COLORS['primary'], label=metric.upper())
        
        # Add threshold lines based on metric
        if metric == 'mos':
            ax.axhline(4.0, color=self.COLORS['success'], linestyle='--', 
                      label='Good (4.0)')
            ax.axhline(3.5, color=self.COLORS['warning'], linestyle='--', 
                      label='Acceptable (3.5)')
        elif metric == 'jitter':
            ax.axhline(30, color=self.COLORS['warning'], linestyle='--', 
                      label='Warning (30ms)')
            ax.axhline(50, color=self.COLORS['danger'], linestyle='--', 
                      label='Critical (50ms)')
        elif metric == 'latency':
            ax.axhline(150, color=self.COLORS['warning'], linestyle='--', 
                      label='Warning (150ms)')
            ax.axhline(300, color=self.COLORS['danger'], linestyle='--', 
                      label='Critical (300ms)')
        
        ax.set_xticks(x[::max(1, len(x)//10)])
        ax.set_xticklabels([str(trend.iloc[i]['period']) 
                          for i in range(0, len(trend), max(1, len(trend)//10))],
                         rotation=45, ha='right')
        
        self._format_axis_labels(
            ax,
            xlabel='Period',
            ylabel=f'{metric.upper()} Value',
            title=f'{metric.upper()} Trend Over Time'
        )
        
        ax.legend()
        self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, f'{metric}_trend.png', save_path)
        
        return fig
    
    # ==================== USER ACTIVITY CHARTS ====================
    
    def plot_user_activity_timeline(
        self,
        user: str,
        days: int = 30,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (14, 8)
    ) -> Optional[plt.Figure]:
        """
        Plot activity timeline for a specific user
        
        :param user: User extension/number
        :param days: Number of days to show
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        history = self.analyzer.users.get_user_call_history(user, days)
        
        if history.empty:
            return None
        
        fig, axes = plt.subplots(2, 2, figsize=figsize)
        
        # 1. Calls per day
        ax1 = axes[0, 0]
        daily = history.groupby(history['dateTimeOrigination_dt'].dt.date).size()
        ax1.bar(range(len(daily)), daily.values, color=self.COLORS['primary'])
        ax1.set_title(f'Daily Call Activity - {user}')
        ax1.set_xlabel('Day')
        ax1.set_ylabel('Calls')
        
        # 2. Hourly pattern
        ax2 = axes[0, 1]
        if 'dateTimeOrigination_dt' in history.columns:
            hourly = history['dateTimeOrigination_dt'].dt.hour.value_counts().sort_index()
            hourly = hourly.reindex(range(24), fill_value=0)
            ax2.bar(hourly.index, hourly.values, color=self.COLORS['secondary'])
        ax2.set_title('Activity by Hour')
        ax2.set_xlabel('Hour')
        ax2.set_ylabel('Calls')
        ax2.set_xticks(range(0, 24, 2))
        
        # 3. Inbound vs Outbound
        ax3 = axes[1, 0]
        if 'direction' in history.columns:
            direction_counts = history['direction'].value_counts()
            colors = [self.COLORS['success'], self.COLORS['primary']]
            ax3.pie(direction_counts.values, labels=direction_counts.index,
                   autopct='%1.1f%%', colors=colors[:len(direction_counts)])
        ax3.set_title('Call Direction')
        
        # 4. Duration distribution
        ax4 = axes[1, 1]
        if 'duration' in history.columns:
            answered = history[history['answered']]['duration']
            ax4.hist(answered, bins=20, color=self.COLORS['info'], alpha=0.7)
            ax4.axvline(answered.mean(), color=self.COLORS['danger'], 
                       linestyle='--', label=f'Mean: {answered.mean():.0f}s')
        ax4.set_title('Call Duration Distribution')
        ax4.set_xlabel('Duration (s)')
        ax4.legend()
        
        for ax in axes.flat:
            self._apply_style(ax)
        
        plt.suptitle(f'Activity Report: {user}', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, f'user_timeline_{user}.png', save_path)
        
        return fig
    
    # ==================== TRUNK/DEVICE CHARTS ====================
    
    def plot_trunk_utilization(
        self,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 6)
    ) -> Optional[plt.Figure]:
        """
        Plot trunk utilization over time
        
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if not self._check_data_loaded():
            return None
        
        trunk_data = self.analyzer.devices.get_trunk_utilization()
        
        if trunk_data.empty:
            return None
        
        fig, ax = self._create_figure(figsize=figsize)
        
        # Stacked bar for inbound/outbound
        x = range(len(trunk_data))
        width = 0.6
        
        ax.bar(x, trunk_data['inbound_calls'], width, 
               label='Inbound', color=self.COLORS['success'])
        ax.bar(x, trunk_data['outbound_calls'], width, 
               bottom=trunk_data['inbound_calls'],
               label='Outbound', color=self.COLORS['primary'])
        
        ax.set_xticks(x)
        ax.set_xticklabels(trunk_data['trunk'], rotation=45, ha='right')
        
        self._format_axis_labels(
            ax,
            xlabel='Trunk',
            ylabel='Number of Calls',
            title='Trunk Utilization (Inbound vs Outbound)'
        )
        
        ax.legend()
        self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'trunk_utilization.png', save_path)
        
        return fig
    
    def plot_concurrent_calls(
        self,
        interval_minutes: int = 15,
        capacity_limit: Optional[int] = None,
        show_business_hours: bool = True,
        business_hours: Tuple[int, int] = (8, 18),
        show_percentiles: bool = True,
        show_heatmap: bool = True,
        show_daily_comparison: bool = True,
        warning_threshold_pct: float = 0.75,
        critical_threshold_pct: float = 0.90,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (18, 14)
    ) -> Optional[plt.Figure]:
        """
        Advanced concurrent calls visualization with multiple analysis panels
        """
        concurrent = self.analyzer.time.get_concurrent_calls(interval_minutes)
        
        if concurrent.empty:
            logger.warning("No concurrent call data available")
            return None
        
        # Ensure datetime column
        if 'time_bucket' in concurrent.columns:
            concurrent['time_bucket'] = pd.to_datetime(concurrent['time_bucket'])
        
        # Auto-detect capacity if not provided
        if capacity_limit is None:
            capacity_limit = int(concurrent['concurrent_calls'].max() * 1.25)
            capacity_limit = max(capacity_limit, 10)
        
        # Calculate thresholds
        warning_threshold = int(capacity_limit * warning_threshold_pct)
        critical_threshold = int(capacity_limit * critical_threshold_pct)
        
        # =====================================================
        # USE constrained_layout=True INSTEAD OF tight_layout()
        # =====================================================
        fig = plt.figure(figsize=figsize, constrained_layout=True)
        
        gs = fig.add_gridspec(
            3, 3, 
            height_ratios=[2, 1, 1], 
            width_ratios=[2, 1, 1],
            hspace=0.1,  # Reduced since constrained_layout handles spacing
            wspace=0.1
        )
        
        # =====================================================
        # PANEL 1: Main Timeline (spans top row)
        # =====================================================
        ax_main = fig.add_subplot(gs[0, :])
        
        x = concurrent['time_bucket']
        y = concurrent['concurrent_calls']
        
        # Create gradient fill based on capacity utilization
        self._plot_capacity_zones(ax_main, x, y, capacity_limit, 
                                warning_threshold, critical_threshold)
        
        # Plot main line
        ax_main.plot(x, y, linewidth=1.5, color='#1a1a2e', zorder=5, alpha=0.8)
        
        # Add rolling average
        window = max(4, len(concurrent) // 50)
        rolling_avg = y.rolling(window=window, center=True).mean()
        ax_main.plot(x, rolling_avg, linewidth=2.5, color=self.COLORS['primary'],
                    linestyle='-', label=f'Rolling Avg ({window * interval_minutes}min)', zorder=6)
        
        # Add percentile bands
        if show_percentiles and len(y) > 10:
            self._add_percentile_bands(ax_main, x, y)
        
        # Add capacity threshold lines
        ax_main.axhline(y=capacity_limit, color='#8b0000', linestyle='-', 
                    linewidth=2, label=f'Capacity ({capacity_limit})', zorder=4)
        ax_main.axhline(y=critical_threshold, color=self.COLORS['danger'], 
                    linestyle='--', linewidth=1.5, 
                    label=f'Critical ({critical_threshold_pct:.0%})', zorder=4)
        ax_main.axhline(y=warning_threshold, color=self.COLORS['warning'], 
                    linestyle='--', linewidth=1.5, 
                    label=f'Warning ({warning_threshold_pct:.0%})', zorder=4)
        
        # Highlight business hours
        if show_business_hours:
            self._highlight_business_hours(ax_main, x, y, business_hours)
        
        # Mark peak points
        self._mark_peaks(ax_main, concurrent, capacity_limit, n_peaks=5)
        
        # Mark threshold breaches
        self._mark_threshold_breaches(ax_main, x, y, warning_threshold, critical_threshold)
        
        # Formatting
        ax_main.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
        ax_main.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.setp(ax_main.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        ax_main.set_ylabel('Concurrent Calls', fontsize=12, fontweight='bold')
        ax_main.set_xlabel('Time', fontsize=11)
        ax_main.set_title('Concurrent Call Analysis Dashboard', 
                        fontsize=16, fontweight='bold', pad=20)
        
        ax_main.set_ylim(0, capacity_limit * 1.1)
        ax_main.legend(loc='upper left', fontsize=9, ncol=2)
        ax_main.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
        
        # Add utilization annotation
        avg_util = (y.mean() / capacity_limit) * 100
        max_util = (y.max() / capacity_limit) * 100
        ax_main.annotate(
            f'Avg Utilization: {avg_util:.1f}%\nPeak Utilization: {max_util:.1f}%',
            xy=(0.98, 0.98), xycoords='axes fraction',
            fontsize=10, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='gray')
        )
        
        # =====================================================
        # PANEL 2: Hour-of-Day Heatmap
        # =====================================================
        if show_heatmap:
            ax_heatmap = fig.add_subplot(gs[1, 0:2])
            self._plot_concurrent_heatmap(ax_heatmap, concurrent, interval_minutes)
        
        # =====================================================
        # PANEL 3: Distribution Histogram
        # =====================================================
        ax_hist = fig.add_subplot(gs[1, 2])
        self._plot_concurrent_distribution(ax_hist, y, capacity_limit, 
                                            warning_threshold, critical_threshold)
        
        # =====================================================
        # PANEL 4: Daily Comparison
        # =====================================================
        if show_daily_comparison:
            ax_daily = fig.add_subplot(gs[2, 0])
            self._plot_daily_peak_comparison(ax_daily, concurrent)
        
        # =====================================================
        # PANEL 5: Hourly Pattern
        # =====================================================
        ax_hourly = fig.add_subplot(gs[2, 1])
        self._plot_hourly_pattern(ax_hourly, concurrent, business_hours)
        
        # =====================================================
        # PANEL 6: Statistics Summary
        # =====================================================
        ax_stats = fig.add_subplot(gs[2, 2])
        self._plot_statistics_panel(ax_stats, concurrent, capacity_limit, 
                                    warning_threshold, critical_threshold)
        
        # Apply styling to all axes
        for ax in fig.axes:
            if ax != ax_stats:  # Stats panel has special formatting
                self._apply_style(ax)
        
        # plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'concurrent_calls.png', save_path)
        
        return fig


    def _plot_capacity_zones(
        self, 
        ax: plt.Axes, 
        x: pd.Series, 
        y: pd.Series,
        capacity: int,
        warning: int,
        critical: int
    ) -> None:
        """Plot color-coded capacity utilization zones"""
        
        # Create zone fills
        ax.fill_between(x, 0, y.clip(upper=warning), 
                        alpha=0.3, color=self.COLORS['success'], 
                        label='Normal Zone')
        
        ax.fill_between(x, warning, y.clip(lower=warning, upper=critical),
                        where=(y >= warning),
                        alpha=0.4, color=self.COLORS['warning'],
                        label='Warning Zone')
        
        ax.fill_between(x, critical, y.clip(lower=critical, upper=capacity),
                        where=(y >= critical),
                        alpha=0.5, color=self.COLORS['danger'],
                        label='Critical Zone')
        
        ax.fill_between(x, capacity, y.clip(lower=capacity),
                        where=(y >= capacity),
                        alpha=0.6, color='#8b0000',
                        label='Over Capacity')


    def _add_percentile_bands(self, ax: plt.Axes, x: pd.Series, y: pd.Series) -> None:
        """Add percentile bands to show typical ranges"""
        
        # Calculate rolling percentiles
        window = max(8, len(y) // 20)
        
        p25 = y.rolling(window=window, center=True).quantile(0.25)
        p75 = y.rolling(window=window, center=True).quantile(0.75)
        p95 = y.rolling(window=window, center=True).quantile(0.95)
        
        # Fill between percentiles
        ax.fill_between(x, p25, p75, alpha=0.15, color=self.COLORS['primary'],
                        label='25th-75th percentile')
        ax.fill_between(x, p75, p95, alpha=0.1, color=self.COLORS['info'],
                        label='75th-95th percentile')


    def _highlight_business_hours(
        self, 
        ax: plt.Axes, 
        x: pd.Series, 
        y: pd.Series,
        business_hours: Tuple[int, int]
    ) -> None:
        """Highlight business hours on the timeline"""
        
        start_hour, end_hour = business_hours
        
        # Get unique dates
        dates = x.dt.date.unique()
        
        for date in dates:
            # Create business hours span for each day
            bh_start = pd.Timestamp(date) + pd.Timedelta(hours=start_hour)
            bh_end = pd.Timestamp(date) + pd.Timedelta(hours=end_hour)
            
            if bh_start >= x.min() and bh_start <= x.max():
                ax.axvspan(bh_start, min(bh_end, x.max()), 
                        alpha=0.05, color=self.COLORS['primary'],
                        zorder=0)


    def _mark_peaks(
        self, 
        ax: plt.Axes, 
        df: pd.DataFrame, 
        capacity: int,
        n_peaks: int = 5
    ) -> None:
        """Mark top N peak points on the chart"""
        
        # Find top peaks
        top_peaks = df.nlargest(n_peaks, 'concurrent_calls')
        
        for i, (idx, row) in enumerate(top_peaks.iterrows()):
            x_val = row['time_bucket']
            y_val = row['concurrent_calls']
            
            # Different marker for absolute peak
            if i == 0:
                ax.scatter([x_val], [y_val], color=self.COLORS['danger'], 
                        s=200, zorder=10, marker='*', edgecolor='white', 
                        linewidth=1.5)
                ax.annotate(
                    f'PEAK: {int(y_val)}',
                    xy=(x_val, y_val),
                    xytext=(10, 20),
                    textcoords='offset points',
                    fontsize=10,
                    fontweight='bold',
                    color=self.COLORS['danger'],
                    arrowprops=dict(arrowstyle='->', color=self.COLORS['danger'], lw=1.5),
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                            edgecolor=self.COLORS['danger'], alpha=0.9)
                )
            else:
                ax.scatter([x_val], [y_val], color=self.COLORS['warning'], 
                        s=80, zorder=8, marker='o', edgecolor='white', linewidth=1)

    def _mark_threshold_breaches(
        self, 
        ax: plt.Axes, 
        x: pd.Series, 
        y: pd.Series,
        warning: int,
        critical: int
    ) -> None:
        """Add markers for threshold breach periods"""
        
        # Find critical breaches
        critical_mask = y >= critical
        if critical_mask.any():
            breach_starts = []
            breach_ends = []
            in_breach = False
            
            for i, is_breach in enumerate(critical_mask):
                if is_breach and not in_breach:
                    breach_starts.append(i)
                    in_breach = True
                elif not is_breach and in_breach:
                    breach_ends.append(i - 1)
                    in_breach = False
            
            if in_breach:
                breach_ends.append(len(critical_mask) - 1)
            
            # Add breach duration annotations for significant breaches
            for start, end in zip(breach_starts, breach_ends):
                duration = end - start + 1
                if duration >= 2:  # Only annotate significant breaches
                    mid_point = (start + end) // 2
                    ax.annotate(
                        f'! {duration * 15}min',  # Changed from ⚠ to !
                        xy=(x.iloc[mid_point], y.iloc[mid_point]),
                        xytext=(0, -25),
                        textcoords='offset points',
                        fontsize=8,
                        ha='center',
                        color=self.COLORS['danger'],
                        fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                edgecolor=self.COLORS['danger'], alpha=0.8)
                    )


    def _plot_concurrent_heatmap(
        self, 
        ax: plt.Axes, 
        df: pd.DataFrame,
        interval_minutes: int
    ) -> None:
        """Create hour-by-day heatmap of concurrent calls"""
        
        # Prepare data
        df_temp = df.copy()
        df_temp['hour'] = df_temp['time_bucket'].dt.hour
        df_temp['day_name'] = df_temp['time_bucket'].dt.day_name()
        
        # Create pivot table
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        pivot = df_temp.pivot_table(
            values='concurrent_calls',
            index='day_name',
            columns='hour',
            aggfunc='mean'
        )
        
        # Reorder days
        pivot = pivot.reindex([d for d in day_order if d in pivot.index])
        
        # Ensure all hours are present
        for hour in range(24):
            if hour not in pivot.columns:
                pivot[hour] = np.nan
        pivot = pivot.reindex(columns=range(24))
        
        # Create heatmap
        sns.heatmap(
            pivot,
            ax=ax,
            cmap='YlOrRd',
            annot=True,
            fmt='.0f',
            cbar_kws={'label': 'Avg Concurrent Calls', 'shrink': 0.8},
            linewidths=0.5,
            linecolor='white',
            mask=pivot.isna()
        )
        
        ax.set_title('Average Concurrent Calls by Hour & Day', fontsize=12, fontweight='bold')
        ax.set_xlabel('Hour of Day', fontsize=10)
        ax.set_ylabel('Day of Week', fontsize=10)
        
        # Highlight business hours (8-18)
        ax.axvline(x=8, color='blue', linestyle='--', linewidth=1.5, alpha=0.7)
        ax.axvline(x=18, color='blue', linestyle='--', linewidth=1.5, alpha=0.7)


    def _plot_concurrent_distribution(
        self, 
        ax: plt.Axes, 
        y: pd.Series,
        capacity: int,
        warning: int,
        critical: int
    ) -> None:
        """Plot distribution histogram of concurrent calls"""
        
        # Create histogram with custom bins
        bins = np.linspace(0, max(y.max(), capacity), 30)
        
        n, bins_arr, patches = ax.hist(y, bins=bins, orientation='horizontal',
                                        color=self.COLORS['primary'], alpha=0.7,
                                        edgecolor='white')
        
        # Color bars based on threshold
        for i, (patch, bin_val) in enumerate(zip(patches, bins_arr[:-1])):
            if bin_val >= critical:
                patch.set_facecolor(self.COLORS['danger'])
            elif bin_val >= warning:
                patch.set_facecolor(self.COLORS['warning'])
            else:
                patch.set_facecolor(self.COLORS['success'])
        
        # Add threshold lines
        ax.axhline(y=warning, color=self.COLORS['warning'], linestyle='--', 
                linewidth=2, label='Warning')
        ax.axhline(y=critical, color=self.COLORS['danger'], linestyle='--', 
                linewidth=2, label='Critical')
        ax.axhline(y=capacity, color='#8b0000', linestyle='-', 
                linewidth=2, label='Capacity')
        
        # Add mean and median
        ax.axhline(y=y.mean(), color=self.COLORS['primary'], linestyle=':',
                linewidth=2, label=f'Mean: {y.mean():.1f}')
        ax.axhline(y=y.median(), color=self.COLORS['info'], linestyle=':',
                linewidth=2, label=f'Median: {y.median():.1f}')
        
        ax.set_xlabel('Frequency', fontsize=10)
        ax.set_ylabel('Concurrent Calls', fontsize=10)
        ax.set_title('Distribution', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=8)
        ax.set_ylim(0, capacity * 1.1)


    def _plot_daily_peak_comparison(self, ax: plt.Axes, df: pd.DataFrame) -> None:
        """Plot daily peak and average comparison"""
        
        df_temp = df.copy()
        df_temp['date'] = df_temp['time_bucket'].dt.date
        
        daily_stats = df_temp.groupby('date').agg({
            'concurrent_calls': ['max', 'mean', 'min']
        }).reset_index()
        
        daily_stats.columns = ['date', 'peak', 'avg', 'min']
        daily_stats = daily_stats.tail(14)  # Last 2 weeks
        
        x = range(len(daily_stats))
        
        # Plot bars for peak
        bars = ax.bar(x, daily_stats['peak'], color=self.COLORS['danger'], 
                    alpha=0.7, label='Peak', width=0.6)
        
        # Overlay average as line
        ax.plot(x, daily_stats['avg'], color=self.COLORS['primary'], 
                marker='o', linewidth=2, label='Average', markersize=6)
        
        # Add min as dots
        ax.scatter(x, daily_stats['min'], color=self.COLORS['success'], 
                s=30, zorder=5, label='Min')
        
        # Format x-axis
        ax.set_xticks(x)
        date_labels = [d.strftime('%m/%d') for d in daily_stats['date']]
        ax.set_xticklabels(date_labels, rotation=45, ha='right', fontsize=8)
        
        ax.set_ylabel('Concurrent Calls', fontsize=10)
        ax.set_xlabel('Date', fontsize=10)
        ax.set_title('Daily Peak vs Average', fontsize=12, fontweight='bold')
        ax.legend(loc='upper left', fontsize=8)
        
        # Add trend line for peaks
        z = np.polyfit(x, daily_stats['peak'], 1)
        p = np.poly1d(z)
        ax.plot(x, p(x), '--', color='gray', alpha=0.5, linewidth=1)


    def _plot_hourly_pattern(
        self, 
        ax: plt.Axes, 
        df: pd.DataFrame,
        business_hours: Tuple[int, int]
    ) -> None:
        """Plot average pattern by hour of day"""
        
        df_temp = df.copy()
        df_temp['hour'] = df_temp['time_bucket'].dt.hour
        
        hourly = df_temp.groupby('hour').agg({
            'concurrent_calls': ['mean', 'std', 'max', 'min']
        }).reset_index()
        
        hourly.columns = ['hour', 'mean', 'std', 'max', 'min']
        hourly = hourly.reindex(range(24), fill_value=0)
        hourly['hour'] = range(24)
        
        x = hourly['hour']
        
        # Fill between min and max
        ax.fill_between(x, hourly['min'], hourly['max'], 
                        alpha=0.2, color=self.COLORS['primary'], 
                        label='Min-Max Range')
        
        # Fill between mean ± std
        ax.fill_between(x, 
                        hourly['mean'] - hourly['std'], 
                        hourly['mean'] + hourly['std'],
                        alpha=0.3, color=self.COLORS['info'], 
                        label='±1 Std Dev')
        
        # Plot mean line
        ax.plot(x, hourly['mean'], color=self.COLORS['primary'], 
                linewidth=2.5, marker='o', markersize=4, label='Average')
        
        # Highlight business hours
        start_h, end_h = business_hours
        ax.axvspan(start_h, end_h, alpha=0.1, color='green', label='Business Hours')
        
        ax.set_xticks(range(0, 24, 2))
        ax.set_xticklabels([f'{h:02d}' for h in range(0, 24, 2)])
        ax.set_xlabel('Hour of Day', fontsize=10)
        ax.set_ylabel('Concurrent Calls', fontsize=10)
        ax.set_title('Hourly Pattern', fontsize=12, fontweight='bold')
        ax.legend(loc='upper right', fontsize=7)
        ax.set_xlim(0, 23)


    def _plot_statistics_panel(
        self, 
        ax: plt.Axes, 
        df: pd.DataFrame,
        capacity: int,
        warning: int,
        critical: int
    ) -> None:
        """Create statistics summary panel"""
        
        y = df['concurrent_calls']
        
        # Calculate statistics
        stats = {
            'Total Intervals': len(df),
            'Peak Concurrent': int(y.max()),
            'Average': f'{y.mean():.1f}',
            'Median': f'{y.median():.1f}',
            'Std Deviation': f'{y.std():.1f}',
            '95th Percentile': f'{y.quantile(0.95):.1f}',
            '99th Percentile': f'{y.quantile(0.99):.1f}',
            'Capacity': capacity,
            'Peak Utilization': f'{(y.max()/capacity)*100:.1f}%',
            'Avg Utilization': f'{(y.mean()/capacity)*100:.1f}%',
        }
        
        # Calculate breach metrics
        warning_breaches = (y >= warning).sum()
        critical_breaches = (y >= critical).sum()
        over_capacity = (y >= capacity).sum()
        
        breach_stats = {
            'Warning Breaches': f'{warning_breaches} ({warning_breaches/len(df)*100:.1f}%)',
            'Critical Breaches': f'{critical_breaches} ({critical_breaches/len(df)*100:.1f}%)',
            'Over Capacity': f'{over_capacity} ({over_capacity/len(df)*100:.1f}%)',
        }
        
        # Hide axes
        ax.axis('off')
        
        # Create text content - Using ASCII-safe characters instead of emojis
        stats_text = "STATISTICS\n" + "=" * 30 + "\n"
        for key, value in stats.items():
            stats_text += f"  {key}: {value}\n"
        
        stats_text += "\nTHRESHOLD ANALYSIS\n" + "=" * 30 + "\n"
        for key, value in breach_stats.items():
            stats_text += f"  {key}: {value}\n"
        
        # Add time range
        time_range = (
            f"\nData Range:\n"
            f"  From: {df['time_bucket'].min().strftime('%Y-%m-%d %H:%M')}\n"
            f"  To:   {df['time_bucket'].max().strftime('%Y-%m-%d %H:%M')}"
        )
        stats_text += time_range
        
        # Determine health status - Using text instead of emojis
        if over_capacity > 0:
            health = "[CRITICAL]"
            health_color = self.COLORS['danger']
            box_color = '#ffebee'  # Light red
            edge_color = self.COLORS['danger']
        elif critical_breaches > len(df) * 0.05:
            health = "[WARNING]"
            health_color = self.COLORS['warning']
            box_color = '#fff3e0'  # Light orange
            edge_color = self.COLORS['warning']
        elif warning_breaches > len(df) * 0.10:
            health = "[CAUTION]"
            health_color = '#FFD700'
            box_color = '#fffde7'  # Light yellow
            edge_color = '#FFD700'
        else:
            health = "[HEALTHY]"
            health_color = self.COLORS['success']
            box_color = '#e8f5e9'  # Light green
            edge_color = self.COLORS['success']
        
        stats_text += f"\n\nCapacity Status: {health}"
        
        # Add text box
        ax.text(0.5, 0.5, stats_text, transform=ax.transAxes,
                fontsize=9, verticalalignment='center', horizontalalignment='center',
                fontfamily='monospace',
                bbox=dict(boxstyle='round', facecolor=box_color, 
                        edgecolor=edge_color, alpha=0.95, pad=1))
        
        ax.set_title('Summary Statistics', fontsize=12, fontweight='bold')
        
    def plot_codec_distribution(
        self,
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 10)
    ) -> Optional[plt.Figure]:
        """
        Plot codec usage distribution with detailed breakdown
        
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        if self.cmr is None or self.cmr.empty:
            logger.warning("CMR data not loaded - cannot generate codec distribution")
            return None
        
        # Compute codec stats directly from CMR data
        codec_stats = self._compute_codec_stats()
        
        if codec_stats is None or codec_stats.empty:
            logger.warning("No codec data available")
            return None
        
        # Create figure with subplots
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # =====================================
        # Panel 1: Pie Chart
        # =====================================
        ax1 = axes[0]
        
        colors = self.PALETTE_CATEGORICAL[:len(codec_stats)]
        
        # Calculate percentages for labels
        total = codec_stats['count'].sum()
        percentages = (codec_stats['count'] / total * 100).values
        
        # Create pie chart
        wedges, texts, autotexts = ax1.pie(
            codec_stats['count'],
            labels=None,  # We'll use a legend instead
            autopct=lambda pct: f'{pct:.1f}%' if pct > 3 else '',
            colors=colors,
            startangle=90,
            explode=[0.02] * len(codec_stats),
            shadow=False,
            wedgeprops=dict(edgecolor='white', linewidth=1.5)
        )
        
        # Style the percentage text
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontweight('bold')
            autotext.set_fontsize(10)
        
        ax1.set_title('Codec Distribution', fontsize=14, fontweight='bold')
        
        # Add legend with counts and percentages
        legend_labels = [
            f'{row["codec"]}: {row["count"]:,} ({row["count"]/total*100:.1f}%)' 
            for _, row in codec_stats.iterrows()
        ]
        ax1.legend(
            wedges, legend_labels, 
            title="Codecs", 
            loc="center left", 
            bbox_to_anchor=(1, 0.5),
            fontsize=9
        )
        
        # =====================================
        # Panel 2: Horizontal Bar Chart
        # =====================================
        ax2 = axes[1]
        
        y_pos = range(len(codec_stats))
        
        bars = ax2.barh(
            y_pos, 
            codec_stats['count'], 
            color=colors, 
            edgecolor='white',
            alpha=0.8
        )
        
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels(codec_stats['codec'])
        ax2.invert_yaxis()
        
        # Add value labels
        max_val = codec_stats['count'].max()
        for bar, val, pct in zip(bars, codec_stats['count'], percentages):
            # Position label inside or outside bar based on size
            if val > max_val * 0.3:
                ax2.text(
                    val - max_val * 0.02, 
                    bar.get_y() + bar.get_height()/2,
                    f'{int(val):,}',
                    va='center', ha='right', 
                    fontsize=10, color='white', fontweight='bold'
                )
            else:
                ax2.text(
                    val + max_val * 0.02, 
                    bar.get_y() + bar.get_height()/2,
                    f'{int(val):,} ({pct:.1f}%)',
                    va='center', ha='left', 
                    fontsize=10, color='#333'
                )
        
        ax2.set_xlabel('Number of Calls', fontsize=11)
        ax2.set_title('Codec Usage Count', fontsize=14, fontweight='bold')
        
        # Apply styling
        for ax in axes:
            self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'codec_distribution.png', save_path)
        
        return fig


    def _compute_codec_stats(self) -> Optional[pd.DataFrame]:
        """
        Compute codec statistics directly from CMR data
        
        :return: DataFrame with codec statistics
        """
        if self.cmr is None or self.cmr.empty:
            return None
        
        # Try different possible codec column names
        codec_columns = [
            'payloadType', 'codecType', 'codec', 
            'origCodec', 'destCodec', 
            'origPayloadType', 'destPayloadType',
            'origMediaPayloadType', 'destMediaPayloadType',
            'varVQMetrics',  # Sometimes codec info is here
        ]
        
        codec_col = None
        for col in codec_columns:
            if col in self.cmr.columns:
                codec_col = col
                break
        
        if codec_col is None:
            # Try to find any column with 'codec' or 'payload' in the name
            for col in self.cmr.columns:
                col_lower = col.lower()
                if 'codec' in col_lower or 'payload' in col_lower:
                    codec_col = col
                    break
        
        if codec_col is None:
            logger.warning(f"No codec column found in CMR data. Available columns: {list(self.cmr.columns)}")
            # Create a dummy "Unknown" codec entry
            return pd.DataFrame({'codec': ['Unknown'], 'count': [len(self.cmr)]})
        
        # Count codec usage
        codec_counts = self.cmr[codec_col].value_counts().reset_index()
        codec_counts.columns = ['codec', 'count']
        
        # Map codec IDs to names if they appear to be numeric
        codec_map = {
            0: 'Unknown',
            1: 'G.711 A-law (64k)',
            2: 'G.711 u-law (64k)',
            3: 'G.722 (64k)',
            4: 'G.723.1',
            5: 'G.728',
            6: 'G.729',
            7: 'G.729A',
            8: 'G.729B',
            9: 'G.729AB',
            10: 'GSM FR',
            11: 'GSM HR',
            12: 'GSM EFR',
            15: 'iLBC',
            16: 'iSAC',
            18: 'AMR',
            19: 'AMR-WB',
            25: 'AAC-LD',
            40: 'G.722.1 (24k)',
            41: 'G.722.1 (32k)',
            42: 'G.722.1 Annex C (24k)',
            43: 'G.722.1 Annex C (32k)',
            44: 'G.722.1 Annex C (48k)',
            45: 'ISAC',
            86: 'Opus',
            100: 'H.261',
            101: 'H.263',
            102: 'H.264 (AVC)',
            103: 'H.265 (HEVC)',
            104: 'VP8',
            105: 'VP9',
        }
        
        # Check if codec values are numeric and map them
        def map_codec(x):
            if pd.isna(x):
                return 'Unknown'
            try:
                numeric_val = int(float(x))
                return codec_map.get(numeric_val, f'Codec_{numeric_val}')
            except (ValueError, TypeError):
                return str(x)
        
        if pd.api.types.is_numeric_dtype(codec_counts['codec']):
            codec_counts['codec'] = codec_counts['codec'].apply(map_codec)
        else:
            # Try to convert string numbers
            codec_counts['codec'] = codec_counts['codec'].apply(map_codec)
        
        # Clean up codec names
        codec_counts['codec'] = codec_counts['codec'].astype(str).str.strip()
        codec_counts = codec_counts[codec_counts['codec'] != '']
        codec_counts = codec_counts[codec_counts['codec'].str.lower() != 'nan']
        
        # Aggregate same codecs (in case mapping created duplicates)
        codec_counts = codec_counts.groupby('codec', as_index=False)['count'].sum()
        
        # Sort by count descending
        codec_counts = codec_counts.sort_values('count', ascending=False).reset_index(drop=True)
        
        # Limit to top 10 codecs, group rest as 'Other'
        if len(codec_counts) > 10:
            top_codecs = codec_counts.head(10).copy()
            other_count = codec_counts.iloc[10:]['count'].sum()
            if other_count > 0:
                other_row = pd.DataFrame({'codec': ['Other'], 'count': [other_count]})
                codec_counts = pd.concat([top_codecs, other_row], ignore_index=True)
            else:
                codec_counts = top_codecs
        
        return codec_counts
    
    def plot_department_comparison(
        self,
        dept_mapping: Dict[str, List[str]],
        save_path: Optional[str] = None,
        figsize: Tuple[int, int] = (12, 8)
    ) -> Optional[plt.Figure]:
        """
        Compare call statistics across departments
        
        :param dept_mapping: Dictionary mapping department names to extensions
        :param save_path: Optional path to save figure
        :param figsize: Figure size
        :return: Figure object
        """
        dept_stats = self.analyzer.users.get_department_stats(dept_mapping)
        
        if dept_stats.empty:
            return None
        
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # 1. Call volume by department
        ax1 = axes[0]
        x = range(len(dept_stats))
        width = 0.35
        
        ax1.bar([i - width/2 for i in x], dept_stats['outgoing_calls'],
            width, label='Outgoing', color=self.COLORS['primary'])
        ax1.bar([i + width/2 for i in x], dept_stats['incoming_calls'],
            width, label='Incoming', color=self.COLORS['success'])
        
        ax1.set_xticks(x)
        ax1.set_xticklabels(dept_stats['department'], rotation=45, ha='right')
        ax1.set_ylabel('Number of Calls')
        ax1.set_title('Call Volume by Department')
        ax1.legend()
        
        # 2. Answer rate by department
        ax2 = axes[1]
        colors = [self._get_color_for_value(r/100, (0.8, 0.95)) 
                for r in dept_stats['answer_rate']]
        ax2.barh(dept_stats['department'], dept_stats['answer_rate'], color=colors)
        ax2.set_xlabel('Answer Rate (%)')
        ax2.set_title('Answer Rate by Department')
        ax2.set_xlim(0, 100)
        
        # Add value labels
        for i, v in enumerate(dept_stats['answer_rate']):
            ax2.text(v + 1, i, f'{v:.1f}%', va='center')
        
        for ax in axes:
            self._apply_style(ax)
        
        plt.tight_layout()
        
        if save_path:
            self._save_figure(fig, 'department_comparison.png', save_path)
        
        return fig