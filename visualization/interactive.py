"""
Interactive visualizations using Plotly
Includes dashboards, network graphs, sankey diagrams, and geographic maps
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple, Union
import logging

try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

from .base_viz import BaseVisualizer

logger = logging.getLogger(__name__)


class InteractiveVisualizer(BaseVisualizer):
    """Generate interactive Plotly visualizations"""
    
    def __init__(self, analyzer):
        super().__init__(analyzer)
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly not available. Install with: pip install plotly")
    
    def _check_plotly(self) -> bool:
        """Check if Plotly is available"""
        if not PLOTLY_AVAILABLE:
            logger.error("Plotly is required for interactive visualizations")
            return False
        return True
    
    # ==================== DAILY TREND ====================
    
    def plot_daily_trend_interactive(
        self,
        days: int = 30,
        show_answered: bool = True
    ) -> Optional['go.Figure']:
        """
        Create interactive daily trend chart
        
        :param days: Number of days to show
        :param show_answered: Show answered vs total breakdown
        :return: Plotly Figure object
        """
        if not self._check_plotly() or not self._check_data_loaded():
            return None
        
        daily = self.analyzer.time.get_daily_call_volume()
        if daily.empty:
            return None
        
        daily = daily.tail(days)
        
        fig = go.Figure()
        
        # Total calls
        fig.add_trace(go.Bar(
            x=daily['date'],
            y=daily['total_calls'],
            name='Total Calls',
            marker_color='#3498db',
            opacity=0.7
        ))
        
        if show_answered:
            # Answered calls overlay
            fig.add_trace(go.Bar(
                x=daily['date'],
                y=daily['answered_calls'],
                name='Answered',
                marker_color='#2ecc71',
                opacity=0.7
            ))
        
        # Rolling average line
        rolling = daily['total_calls'].rolling(window=7, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=daily['date'],
            y=rolling,
            name='7-Day Average',
            line=dict(color='#e74c3c', width=3),
            mode='lines'
        ))
        
        fig.update_layout(
            title='Daily Call Volume Trend',
            xaxis_title='Date',
            yaxis_title='Number of Calls',
            barmode='overlay',
            hovermode='x unified',
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=1.02)
        )
        
        return fig
    
    # ==================== HOURLY HEATMAP ====================
    
    def plot_hourly_heatmap_interactive(
        self,
        metric: str = 'count'
    ) -> Optional['go.Figure']:
        """
        Create interactive hourly heatmap
        
        :param metric: 'count', 'duration', 'answer_rate'
        :return: Plotly Figure object
        """
        if not self._check_plotly() or not self._check_data_loaded():
            return None
        
        heatmap_data = self.analyzer.time.get_hourly_heatmap_by_metric(metric)
        
        if heatmap_data.empty:
            return None
        
        # Prepare labels
        hours = [f'{h:02d}:00' for h in heatmap_data.index]
        days = list(heatmap_data.columns)
        
        colorscale = 'YlOrRd' if metric != 'answer_rate' else 'RdYlGn'
        
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=days,
            y=hours,
            colorscale=colorscale,
            hoverongaps=False,
            hovertemplate='%{y} %{x}<br>Value: %{z:.1f}<extra></extra>'
        ))
        
        title_map = {
            'count': 'Call Volume',
            'duration': 'Average Duration (seconds)',
            'answer_rate': 'Answer Rate (%)'
        }
        
        fig.update_layout(
            title=f'{title_map.get(metric, metric)} by Hour and Day',
            xaxis_title='Day of Week',
            yaxis_title='Hour of Day',
            template='plotly_white',
            yaxis=dict(autorange='reversed')
        )
        
        return fig
    
    # ==================== CALL FLOW SANKEY ====================
    
    def plot_call_flow_sankey(
        self,
        top_n: int = 10,
        flow_type: str = 'caller_to_called'
    ) -> Optional['go.Figure']:
        """
        Create Sankey diagram showing call flows
        
        :param top_n: Number of top sources/destinations
        :param flow_type: 'caller_to_called' or 'device_to_device'
        :return: Plotly Figure object
        """
        if not self._check_plotly() or not self._check_data_loaded():
            return None
        
        df = self.cdr.copy()
        
        if flow_type == 'caller_to_called':
            source_col = 'callingPartyNumber'
            target_col = 'finalCalledPartyNumber'
        else:
            source_col = 'origDeviceName'
            target_col = 'destDeviceName'
        
        # Get top sources and targets
        top_sources = df[source_col].value_counts().head(top_n).index.tolist()
        top_targets = df[target_col].value_counts().head(top_n).index.tolist()
        
        # Filter to top sources/targets
        filtered = df[
            df[source_col].isin(top_sources) | 
            df[target_col].isin(top_targets)
        ]
        
        # Create flow counts
        flows = filtered.groupby([source_col, target_col]).size().reset_index(name='count')
        flows = flows.nlargest(50, 'count')  # Top 50 flows
        
        # Create node list
        all_nodes = list(set(flows[source_col].tolist() + flows[target_col].tolist()))
        node_indices = {node: i for i, node in enumerate(all_nodes)}
        
        # Create source, target, value lists
        sources = [node_indices[s] for s in flows[source_col]]
        targets = [node_indices[t] for t in flows[target_col]]
        values = flows['count'].tolist()
        
        # Create colors
        colors = px.colors.qualitative.Set3[:len(all_nodes)]
        
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color='black', width=0.5),
                label=all_nodes,
                color=colors
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                hovertemplate='%{source.label} → %{target.label}<br>Calls: %{value}<extra></extra>'
            )
        )])
        
        fig.update_layout(
            title=f'Call Flow Diagram (Top {top_n} {"Callers/Called" if flow_type == "caller_to_called" else "Devices"})',
            template='plotly_white',
            font_size=10
        )
        
        return fig
    
    # ==================== NETWORK TOPOLOGY ====================
    
    def plot_network_topology(
        self,
        max_nodes: int = 30,
        min_calls: int = 5
    ) -> Optional['go.Figure']:
        """
        Create network graph showing call relationships
        
        :param max_nodes: Maximum number of nodes
        :param min_calls: Minimum calls to include edge
        :return: Plotly Figure object
        """
        if not self._check_plotly() or not self._check_data_loaded():
            return None
        
        if not NETWORKX_AVAILABLE:
            logger.error("NetworkX required for network topology. Install with: pip install networkx")
            return None
        
        df = self.cdr.copy()
        
        # Create connection counts
        connections = df.groupby(['callingPartyNumber', 'finalCalledPartyNumber']).size().reset_index(name='count')
        connections = connections[connections['count'] >= min_calls]
        
        # Get top nodes by total connections
        all_nodes = pd.concat([
            connections.groupby('callingPartyNumber')['count'].sum(),
            connections.groupby('finalCalledPartyNumber')['count'].sum()
        ]).groupby(level=0).sum().nlargest(max_nodes)
        
        top_nodes = set(all_nodes.index)
        
        # Filter connections
        connections = connections[
            connections['callingPartyNumber'].isin(top_nodes) &
            connections['finalCalledPartyNumber'].isin(top_nodes)
        ]
        
        if connections.empty:
            return None
        
        # Create NetworkX graph
        G = nx.DiGraph()
        
        for _, row in connections.iterrows():
            G.add_edge(
                row['callingPartyNumber'],
                row['finalCalledPartyNumber'],
                weight=row['count']
            )
        
        # Calculate layout
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # Create edge traces
        edge_x = []
        edge_y = []
        edge_weights = []
        
        for edge in G.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_weights.append(edge[2]['weight'])
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines'
        )
        
        # Create node traces
        node_x = []
        node_y = []
        node_text = []
        node_size = []
        
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            # Calculate node metrics
            in_degree = G.in_degree(node, weight='weight')
            out_degree = G.out_degree(node, weight='weight')
            
            node_text.append(f'{node}<br>Incoming: {in_degree}<br>Outgoing: {out_degree}')
            node_size.append(10 + (in_degree + out_degree) / 10)
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=[n[:10] for n in G.nodes()],
            textposition='top center',
            hovertext=node_text,
            marker=dict(
                showscale=True,
                colorscale='YlGnBu',
                size=node_size,
                color=[G.degree(n, weight='weight') for n in G.nodes()],
                colorbar=dict(
                    thickness=15,
                    title='Connections',
                    xanchor='left'
                ),
                line_width=2
            )
        )
        
        fig = go.Figure(data=[edge_trace, node_trace])
        
        fig.update_layout(
            title='Call Network Topology',
            showlegend=False,
            hovermode='closest',
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            template='plotly_white'
        )
        
        return fig
    
    # ==================== GEOGRAPHIC MAP ====================
    
    def plot_geographic_map(
        self,
        location_data: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> Optional['go.Figure']:
        """
        Create geographic map with call locations
        
        :param location_data: Dict mapping locations to (lat, lon) coordinates
        :return: Plotly Figure object
        """
        if not self._check_plotly() or not self._check_data_loaded():
            return None
        
        if location_data is None:
            logger.warning("No location data provided for geographic map")
            return None
        
        df = self.cdr.copy()
        
        # This is a placeholder - actual implementation would need
        # location mapping from device names or IP addresses
        
        # Example with dummy data
        locations = []
        for loc_name, coords in location_data.items():
            # Count calls for this location
            # This would need actual mapping logic
            locations.append({
                'location': loc_name,
                'lat': coords[0],
                'lon': coords[1],
                'calls': np.random.randint(100, 1000)  # Placeholder
            })
        
        loc_df = pd.DataFrame(locations)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scattergeo(
            lon=loc_df['lon'],
            lat=loc_df['lat'],
            text=loc_df.apply(lambda r: f"{r['location']}<br>Calls: {r['calls']}", axis=1),
            marker=dict(
                size=loc_df['calls'] / 50,
                color=loc_df['calls'],
                colorscale='Viridis',
                showscale=True,
                colorbar_title='Calls'
            ),
            hoverinfo='text'
        ))
        
        fig.update_layout(
            title='Call Volume by Location',
            geo=dict(
                showland=True,
                landcolor='rgb(243, 243, 243)',
                countrycolor='rgb(204, 204, 204)',
            ),
            template='plotly_white'
        )
        
        return fig
    
    # ==================== QUALITY DASHBOARD ====================
    
    def plot_quality_dashboard(self) -> Optional['go.Figure']:
        """
        Create comprehensive quality metrics dashboard
        
        :return: Plotly Figure object
        """
        if not self._check_plotly():
            return None
        
        if self.cmr is None:
            logger.warning("CMR data not available for quality dashboard")
            return None
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                'Jitter Distribution',
                'Latency Distribution',
                'Packet Loss Over Time',
                'MOS Score Distribution'
            ),
            specs=[[{'type': 'histogram'}, {'type': 'histogram'}],
                   [{'type': 'scatter'}, {'type': 'histogram'}]]
        )
        
        # 1. Jitter Distribution
        fig.add_trace(
            go.Histogram(
                x=self.cmr['origjitter'],
                name='Origin Jitter',
                marker_color='#3498db',
                opacity=0.7
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Histogram(
                x=self.cmr['destjitter'],
                name='Dest Jitter',
                marker_color='#f39c12',
                opacity=0.7
            ),
            row=1, col=1
        )
        
        # 2. Latency Distribution
        fig.add_trace(
            go.Histogram(
                x=self.cmr['origlatency'],
                name='Origin Latency',
                marker_color='#3498db',
                opacity=0.7
            ),
            row=1, col=2
        )
        fig.add_trace(
            go.Histogram(
                x=self.cmr['destlatency'],
                name='Dest Latency',
                marker_color='#f39c12',
                opacity=0.7
            ),
            row=1, col=2
        )
        
        # 3. Packet Loss Trend (if merged data available)
        if self.merged is not None and 'dateTimeOrigination_dt' in self.merged.columns:
            daily_pl = self.merged.groupby(
                self.merged['dateTimeOrigination_dt'].dt.date
            )['orig_packet_loss_pct'].mean().reset_index()
            daily_pl.columns = ['date', 'packet_loss']
            
            fig.add_trace(
                go.Scatter(
                    x=daily_pl['date'],
                    y=daily_pl['packet_loss'],
                    name='Packet Loss %',
                    line=dict(color='#e74c3c', width=2),
                    mode='lines+markers'
                ),
                row=2, col=1
            )
        
        # 4. MOS Distribution
        if 'avg_mos' in self.cmr.columns:
            fig.add_trace(
                go.Histogram(
                    x=self.cmr['avg_mos'].dropna(),
                    name='MOS Score',
                    marker_color='#2ecc71',
                    opacity=0.7
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            title='Call Quality Dashboard',
            showlegend=True,
            template='plotly_white',
            height=800
        )
        
        return fig
    
    # ==================== REAL-TIME DASHBOARD ====================
    
    def create_dashboard_figures(self) -> Dict[str, 'go.Figure']:
        """
        Create all figures for a dashboard
        
        :return: Dictionary of figure names to Plotly figures
        """
        figures = {}
        
        # Call volume trend
        fig = self.plot_daily_trend_interactive()
        if fig:
            figures['daily_trend'] = fig
        
        # Hourly heatmap
        fig = self.plot_hourly_heatmap_interactive()
        if fig:
            figures['hourly_heatmap'] = fig
        
        # Call flow
        fig = self.plot_call_flow_sankey()
        if fig:
            figures['call_flow'] = fig
        
        # Quality dashboard
        fig = self.plot_quality_dashboard()
        if fig:
            figures['quality_dashboard'] = fig
        
        # Network topology
        fig = self.plot_network_topology()
        if fig:
            figures['network_topology'] = fig
        
        return figures
    
    # ==================== CALL TYPE SUNBURST ====================
    
    def plot_call_type_sunburst(self) -> Optional['go.Figure']:
        """
        Create sunburst chart showing call type hierarchy
        
        :return: Plotly Figure object
        """
        if not self._check_plotly() or not self._check_data_loaded():
            return None
        
        df = self.cdr.copy()
        
        # Create hierarchy: call_type -> answered/missed -> device_type
        hierarchy_data = df.groupby(['call_type', 'answered', 'orig_device_type']).size().reset_index(name='count')
        hierarchy_data['answered_label'] = hierarchy_data['answered'].map({True: 'Answered', False: 'Missed'})
        
        # Build sunburst data
        labels = ['All Calls']
        parents = ['']
        values = [len(df)]
        
        # Level 1: Call types
        for call_type in df['call_type'].unique():
            labels.append(call_type)
            parents.append('All Calls')
            values.append(len(df[df['call_type'] == call_type]))
        
        # Level 2: Answered/Missed
        for _, row in hierarchy_data.groupby(['call_type', 'answered_label']).agg({'count': 'sum'}).reset_index().iterrows():
            label = f"{row['call_type']} - {row['answered_label']}"
            labels.append(label)
            parents.append(row['call_type'])
            values.append(row['count'])
        
        fig = go.Figure(go.Sunburst(
            labels=labels,
            parents=parents,
            values=values,
            branchvalues='total',
            hovertemplate='<b>%{label}</b><br>Calls: %{value}<br>Percentage: %{percentParent:.1%}<extra></extra>'
        ))
        
        fig.update_layout(
            title='Call Distribution Hierarchy',
            template='plotly_white'
        )
        
        return fig
    
    # ==================== GAUGE CHARTS ====================
    
    def plot_kpi_gauges(self) -> Optional['go.Figure']:
        """
        Create KPI gauge charts
        
        :return: Plotly Figure object
        """
        if not self._check_plotly() or not self._check_data_loaded():
            return None
        
        summary = self.analyzer.get_call_summary()
        
        fig = make_subplots(
            rows=1, cols=3,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}, {'type': 'indicator'}]],
            subplot_titles=['Answer Rate', 'Avg Duration', 'Total Calls']
        )
        
        # Answer Rate Gauge
        answer_rate = float(summary.get('answer_rate_pct', 0))
        fig.add_trace(
            go.Indicator(
                mode='gauge+number+delta',
                value=answer_rate,
                title={'text': 'Answer Rate (%)'},
                delta={'reference': 90},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': '#2ecc71'},
                    'steps': [
                        {'range': [0, 70], 'color': '#ffcccc'},
                        {'range': [70, 90], 'color': '#ffffcc'},
                        {'range': [90, 100], 'color': '#ccffcc'}
                    ],
                    'threshold': {
                        'line': {'color': 'red', 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ),
            row=1, col=1
        )
        
        # Avg Duration Gauge
        avg_duration = summary.get('avg_duration_sec', 0)
        fig.add_trace(
            go.Indicator(
                mode='gauge+number',
                value=avg_duration,
                title={'text': 'Avg Duration (sec)'},
                gauge={
                    'axis': {'range': [0, 600]},
                    'bar': {'color': '#3498db'},
                    'steps': [
                        {'range': [0, 120], 'color': '#e8f4f8'},
                        {'range': [120, 300], 'color': '#b8dde8'},
                        {'range': [300, 600], 'color': '#88c6d8'}
                    ]
                }
            ),
            row=1, col=2
        )
        
        # Total Calls (number only)
        total_calls = summary.get('total_calls', 0)
        fig.add_trace(
            go.Indicator(
                mode='number+delta',
                value=total_calls,
                title={'text': 'Total Calls'},
                number={'font': {'size': 60}},
                delta={'reference': total_calls * 0.9, 'relative': True}
            ),
            row=1, col=3
        )
        
        fig.update_layout(
            title='Key Performance Indicators',
            template='plotly_white',
            height=400
        )
        
        return fig
    
    def save_interactive_html(
        self,
        fig: 'go.Figure',
        filename: str,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Save interactive figure as HTML
        
        :param fig: Plotly figure
        :param filename: Output filename
        :param output_dir: Output directory
        :return: Path to saved file
        """
        import os
        
        output_dir = output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        filepath = os.path.join(output_dir, filename)
        fig.write_html(filepath, include_plotlyjs=True, full_html=True)
        
        logger.info(f"Interactive chart saved: {filepath}")
        return filepath