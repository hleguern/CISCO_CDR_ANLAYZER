"""
Base visualization class with common functionality
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
import numpy as np
from typing import TYPE_CHECKING, Optional, Tuple, List, Dict, Any, Union
from pathlib import Path
import logging
import os

if TYPE_CHECKING:
    from ..core.analyzer import CiscoCDRAnalyzer

logger = logging.getLogger(__name__)

# Set default style
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")


class BaseVisualizer:
    """Base class for all visualization modules"""
    
    # Color schemes
    COLORS = {
        'primary': '#3498db',
        'secondary': '#2ecc71',
        'warning': '#f39c12',
        'danger': '#e74c3c',
        'info': '#9b59b6',
        'success': '#27ae60',
        'muted': '#95a5a6',
        'dark': '#2c3e50',
    }
    
    PALETTE_CATEGORICAL = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6', 
                           '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b']
    
    PALETTE_SEQUENTIAL = 'Blues'
    PALETTE_DIVERGING = 'RdYlGn'
    
    def __init__(self, analyzer: 'CiscoCDRAnalyzer'):
        """
        Initialize with reference to main analyzer
        
        :param analyzer: Parent CiscoCDRAnalyzer instance
        """
        self.analyzer = analyzer
        self.default_figsize = (12, 6)
        self.default_dpi = 150
        self.output_dir = analyzer.settings.output_dir
    
    @property
    def cdr(self) -> Optional[pd.DataFrame]:
        """Get CDR DataFrame"""
        return self.analyzer.cdr_df
    
    @property
    def cmr(self) -> Optional[pd.DataFrame]:
        """Get CMR DataFrame"""
        return self.analyzer.cmr_df
    
    @property
    def merged(self) -> Optional[pd.DataFrame]:
        """Get merged DataFrame"""
        return self.analyzer.merged_df
    
    @property
    def settings(self):
        """Get settings"""
        return self.analyzer.settings
    
    def _check_data_loaded(self) -> bool:
        """Check if CDR data is loaded"""
        if self.cdr is None:
            logger.error("CDR data not loaded")
            return False
        return True
    
    def _create_figure(
        self, 
        figsize: Optional[Tuple[int, int]] = None,
        nrows: int = 1,
        ncols: int = 1,
        **kwargs
    ) -> Tuple[plt.Figure, Union[plt.Axes, np.ndarray]]:
        """Create matplotlib figure and axes"""
        figsize = figsize or self.default_figsize
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize, **kwargs)
        return fig, axes
    
    def _save_figure(
        self, 
        fig: plt.Figure, 
        filename: str,
        save_path: Optional[str] = None,
        dpi: Optional[int] = None
    ) -> Optional[str]:
        """Save figure to file"""
        if save_path:
            filepath = save_path
        else:
            os.makedirs(self.output_dir, exist_ok=True)
            filepath = os.path.join(self.output_dir, filename)
        
        dpi = dpi or self.default_dpi
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
        logger.info(f"Figure saved: {filepath}")
        return filepath
    
    def _add_value_labels(
        self, 
        ax: plt.Axes, 
        bars,
        format_str: str = '{:.0f}',
        offset: float = 0.5,
        fontsize: int = 9,
        rotation: int = 0
    ):
        """Add value labels to bar chart"""
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                format_str.format(height),
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, offset),
                textcoords="offset points",
                ha='center', va='bottom',
                fontsize=fontsize,
                rotation=rotation
            )
    
    def _format_axis_labels(
        self, 
        ax: plt.Axes,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
        title: Optional[str] = None,
        xlabel_fontsize: int = 11,
        ylabel_fontsize: int = 11,
        title_fontsize: int = 13
    ):
        """Format axis labels and title"""
        if xlabel:
            ax.set_xlabel(xlabel, fontsize=xlabel_fontsize)
        if ylabel:
            ax.set_ylabel(ylabel, fontsize=ylabel_fontsize)
        if title:
            ax.set_title(title, fontsize=title_fontsize, fontweight='bold')
    
    def _apply_style(self, ax: plt.Axes, style: str = 'default'):
        """Apply consistent styling to axes"""
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        if style == 'minimal':
            ax.spines['left'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.tick_params(left=False, bottom=False)
        elif style == 'clean':
            ax.spines['left'].set_color('#cccccc')
            ax.spines['bottom'].set_color('#cccccc')
    
    def _get_color_for_value(
        self, 
        value: float, 
        thresholds: Tuple[float, float] = (0.5, 0.8),
        colors: Tuple[str, str, str] = None
    ) -> str:
        """Get color based on value and thresholds"""
        if colors is None:
            colors = (self.COLORS['danger'], self.COLORS['warning'], self.COLORS['success'])
        
        if value < thresholds[0]:
            return colors[0]
        elif value < thresholds[1]:
            return colors[1]
        return colors[2]