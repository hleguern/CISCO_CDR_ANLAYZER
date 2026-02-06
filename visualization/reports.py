"""
Report generation for CDR/CMR analysis
Includes HTML reports, PDF exports, and Excel workbooks
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import logging
import os
import json

try:
    from jinja2 import Environment, BaseLoader, FileSystemLoader
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

from .base_viz import BaseVisualizer

logger = logging.getLogger(__name__)


class ReportGenerator(BaseVisualizer):
    """Generate comprehensive reports for CDR/CMR analysis"""
    
    HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        :root {
            --primary: #3498db;
            --success: #2ecc71;
            --warning: #f39c12;
            --danger: #e74c3c;
            --dark: #2c3e50;
            --light: #ecf0f1;
            --muted: #95a5a6;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f6fa;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: linear-gradient(135deg, var(--primary), var(--dark));
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .subtitle { opacity: 0.9; font-size: 1.1em; }
        .header .meta { margin-top: 15px; font-size: 0.9em; opacity: 0.8; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        }
        
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: var(--primary);
            margin-bottom: 5px;
        }
        
        .stat-label {
            color: var(--muted);
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .stat-card.success .stat-value { color: var(--success); }
        .stat-card.warning .stat-value { color: var(--warning); }
        .stat-card.danger .stat-value { color: var(--danger); }
        
        .section {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .section h2 {
            color: var(--dark);
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid var(--primary);
        }
        
        .section h3 {
            color: var(--dark);
            margin: 20px 0 15px;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--light);
        }
        
        th {
            background: var(--primary);
            color: white;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
        }
        
        tr:hover { background: #f8f9fa; }
        
        .chart-container {
            margin: 20px 0;
            text-align: center;
        }
        
        .chart-container img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        .quality-good { color: var(--success); font-weight: bold; }
        .quality-warning { color: var(--warning); font-weight: bold; }
        .quality-bad { color: var(--danger); font-weight: bold; }
        
        .two-column {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        
        @media (max-width: 768px) {
            .two-column { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
        
        .progress-bar {
            height: 20px;
            background: var(--light);
            border-radius: 10px;
            overflow: hidden;
            margin: 10px 0;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--success));
            transition: width 0.5s ease;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .badge-success { background: #d4edda; color: #155724; }
        .badge-warning { background: #fff3cd; color: #856404; }
        .badge-danger { background: #f8d7da; color: #721c24; }
        
        .footer {
            text-align: center;
            padding: 20px;
            color: var(--muted);
            font-size: 0.9em;
        }
        
        .alert {
            padding: 15px 20px;
            border-radius: 8px;
            margin: 15px 0;
        }
        
        .alert-info { background: #e3f2fd; border-left: 4px solid var(--primary); }
        .alert-warning { background: #fff8e1; border-left: 4px solid var(--warning); }
        .alert-danger { background: #ffebee; border-left: 4px solid var(--danger); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {{ title }}</h1>
            <div class="subtitle">Cisco CDR/CMR Analysis Report</div>
            <div class="meta">
                Generated: {{ generated_at }} | 
                Period: {{ date_range.start }} to {{ date_range.end }} |
                Total Records: {{ '{:,}'.format(total_calls) }}
            </div>
        </div>
        
        <!-- Summary Statistics -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ '{:,}'.format(total_calls) }}</div>
                <div class="stat-label">Total Calls</div>
            </div>
            <div class="stat-card success">
                <div class="stat-value">{{ '{:,}'.format(answered_calls) }}</div>
                <div class="stat-label">Answered</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-value">{{ '{:,}'.format(missed_calls) }}</div>
                <div class="stat-label">Missed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ answer_rate }}%</div>
                <div class="stat-label">Answer Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ total_duration }}</div>
                <div class="stat-label">Total Duration</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ avg_duration }}s</div>
                <div class="stat-label">Avg Duration</div>
            </div>
        </div>
        
        <!-- Call Types Section -->
        <div class="section">
            <h2>📞 Call Distribution</h2>
            <div class="two-column">
                <div>
                    <h3>By Type</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Call Type</th>
                                <th>Count</th>
                                <th>Percentage</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for type, count in call_types.items() %}
                            <tr>
                                <td>{{ type }}</td>
                                <td>{{ '{:,}'.format(count) }}</td>
                                <td>{{ '{:.1f}'.format(count / total_calls * 100) }}%</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                <div>
                    {% if charts.call_types %}
                    <div class="chart-container">
                        <img src="{{ charts.call_types }}" alt="Call Types Distribution">
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
        
        <!-- Top Callers Section -->
        <div class="section">
            <h2>📱 Top Callers</h2>
            <table>
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>Caller</th>
                        <th>Total Calls</th>
                        <th>Answered</th>
                        <th>Answer Rate</th>
                        <th>Total Duration</th>
                    </tr>
                </thead>
                <tbody>
                    {% for caller in top_callers %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ caller.caller }}</td>
                        <td>{{ '{:,}'.format(caller.total_calls|int) }}</td>
                        <td>{{ '{:,}'.format(caller.answered_calls|int) }}</td>
                        <td>
                            <span class="{% if caller.answer_rate >= 90 %}quality-good{% elif caller.answer_rate >= 70 %}quality-warning{% else %}quality-bad{% endif %}">
                                {{ '{:.1f}'.format(caller.answer_rate) }}%
                            </span>
                        </td>
                        <td>{{ '{:,}'.format(caller.total_duration|int) }}s</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <!-- Quality Section -->
        {% if quality_summary %}
        <div class="section">
            <h2>📶 Quality Metrics</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{{ '{:.1f}'.format(quality_summary.metrics.jitter.orig_avg) }}</div>
                    <div class="stat-label">Avg Jitter (ms)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ '{:.1f}'.format(quality_summary.metrics.latency.orig_avg) }}</div>
                    <div class="stat-label">Avg Latency (ms)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ '{:.3f}'.format(quality_summary.metrics.packet_loss.orig_avg_pct) }}%</div>
                    <div class="stat-label">Packet Loss</div>
                </div>
                {% if quality_summary.mos %}
                <div class="stat-card {% if quality_summary.mos.average >= 4.0 %}success{% elif quality_summary.mos.average >= 3.5 %}warning{% else %}danger{% endif %}">
                    <div class="stat-value">{{ '{:.2f}'.format(quality_summary.mos.average) }}</div>
                    <div class="stat-label">Average MOS</div>
                </div>
                {% endif %}
            </div>
            
            {% if charts.quality_metrics %}
            <div class="chart-container">
                <img src="{{ charts.quality_metrics }}" alt="Quality Metrics">
            </div>
            {% endif %}
        </div>
        {% endif %}
        
        <!-- Hourly Distribution -->
        <div class="section">
            <h2>⏰ Hourly Distribution</h2>
            {% if charts.calls_by_hour %}
            <div class="chart-container">
                <img src="{{ charts.calls_by_hour }}" alt="Calls by Hour">
            </div>
            {% endif %}
        </div>
        
        <!-- Security Alerts -->
        {% if security_alerts %}
        <div class="section">
            <h2>🔒 Security Alerts</h2>
            {% for alert in security_alerts %}
            <div class="alert alert-{{ 'danger' if alert.severity == 'high' else ('warning' if alert.severity == 'medium' else 'info') }}">
                <strong>{{ alert.type }}</strong>: {{ alert.description }}
                <span class="badge badge-{{ 'danger' if alert.severity == 'high' else ('warning' if alert.severity == 'medium' else 'success') }}">
                    {{ alert.severity }}
                </span>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <div class="footer">
            <p>Generated by Cisco CDR/CMR Analyzer v2.0</p>
            <p>Report generated at {{ generated_at }}</p>
        </div>
    </div>
</body>
</html>
    """
    
    def __init__(self, analyzer):
        super().__init__(analyzer)
        self.charts_generated = {}
    
    def generate_report(
        self,
        output_dir: Optional[str] = None,
        title: str = 'CDR Analysis Report',
        include_charts: bool = True,
        include_quality: bool = True,
        include_security: bool = True,
        format: str = 'html'
    ) -> str:
        """
        Generate comprehensive analysis report
        
        :param output_dir: Output directory
        :param title: Report title
        :param include_charts: Include chart images
        :param include_quality: Include quality analysis
        :param include_security: Include security analysis
        :param format: 'html', 'json', or 'xlsx'
        :return: Path to generated report
        """
        output_dir = output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        logger.info(f"Generating {format.upper()} report...")
        
        if format == 'html':
            return self._generate_html_report(output_dir, title, include_charts, 
                                             include_quality, include_security)
        elif format == 'json':
            return self._generate_json_report(output_dir, title, include_quality, 
                                             include_security)
        elif format == 'xlsx':
            return self._generate_excel_report(output_dir, title, include_quality)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _generate_html_report(
        self,
        output_dir: str,
        title: str,
        include_charts: bool,
        include_quality: bool,
        include_security: bool
    ) -> str:
        """Generate HTML report"""
        # Gather data
        call_summary = self.analyzer.get_call_summary()
        quality_summary = self.analyzer.get_quality_summary() if include_quality and self.cmr is not None else None
        top_callers = self.analyzer.users.get_top_callers(10).to_dict('records')
        
        # Security analysis
        security_alerts = []
        if include_security:
            security = self.analyzer.security.get_security_summary()
            if 'total_alerts' in security and security['total_alerts'] > 0:
                fraud = self.analyzer.security.detect_toll_fraud()
                security_alerts = fraud.get('alerts', [])[:5]
        
        # Generate charts
        charts = {}
        if include_charts:
            charts_dir = os.path.join(output_dir, 'charts')
            os.makedirs(charts_dir, exist_ok=True)
            
            # Generate and save charts
            from .charts import ChartGenerator
            chart_gen = ChartGenerator(self.analyzer)
            
            fig = chart_gen.plot_calls_by_hour()
            if fig:
                chart_path = os.path.join(charts_dir, 'calls_by_hour.png')
                fig.savefig(chart_path, dpi=150, bbox_inches='tight')
                charts['calls_by_hour'] = 'charts/calls_by_hour.png'
                plt.close(fig)
            
            fig = chart_gen.plot_call_types()
            if fig:
                chart_path = os.path.join(charts_dir, 'call_types.png')
                fig.savefig(chart_path, dpi=150, bbox_inches='tight')
                charts['call_types'] = 'charts/call_types.png'
                plt.close(fig)
            
            if self.cmr is not None:
                fig = chart_gen.plot_quality_metrics()
                if fig:
                    chart_path = os.path.join(charts_dir, 'quality_metrics.png')
                    fig.savefig(chart_path, dpi=150, bbox_inches='tight')
                    charts['quality_metrics'] = 'charts/quality_metrics.png'
                    plt.close(fig)
        
        # Prepare template data
        template_data = {
            'title': title,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'date_range': call_summary.get('date_range', {'start': 'N/A', 'end': 'N/A'}),
            'total_calls': call_summary.get('total_calls', 0),
            'answered_calls': call_summary.get('answered_calls', 0),
            'missed_calls': call_summary.get('missed_calls', 0),
            'answer_rate': call_summary.get('answer_rate_pct', 0),
            'total_duration': call_summary.get('total_duration_formatted', '0s'),
            'avg_duration': call_summary.get('avg_duration_sec', 0),
            'call_types': call_summary.get('call_types', {}),
            'top_callers': top_callers,
            'quality_summary': quality_summary,
            'security_alerts': security_alerts,
            'charts': charts,
        }
        
        # Render template
        if JINJA2_AVAILABLE:
            env = Environment(loader=BaseLoader())
            template = env.from_string(self.HTML_TEMPLATE)
            html_content = template.render(**template_data)
        else:
            html_content = self._render_simple_html(template_data)
        
        # Save report
        report_path = os.path.join(output_dir, 'report.html')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {report_path}")
        return report_path
    
    def _render_simple_html(self, data: Dict[str, Any]) -> str:
        """Simple HTML rendering without Jinja2"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{data['title']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }}
        .stat-box {{ display: inline-block; background: #ecf0f1; padding: 15px; margin: 5px; border-radius: 5px; min-width: 150px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
        .stat-label {{ font-size: 12px; color: #7f8c8d; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background: #3498db; color: white; }}
        tr:nth-child(even) {{ background: #f9f9f9; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 {data['title']}</h1>
        <p>Generated: {data['generated_at']}</p>
        
        <h2>📞 Call Summary</h2>
        <div class="stat-box">
            <div class="stat-value">{data['total_calls']:,}</div>
            <div class="stat-label">Total Calls</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{data['answered_calls']:,}</div>
            <div class="stat-label">Answered</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{data['missed_calls']:,}</div>
            <div class="stat-label">Missed</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{data['answer_rate']}%</div>
            <div class="stat-label">Answer Rate</div>
        </div>
        
        <h2>📊 Call Types</h2>
        <table>
            <tr><th>Type</th><th>Count</th></tr>
"""
        for ctype, count in data['call_types'].items():
            html += f"<tr><td>{ctype}</td><td>{count:,}</td></tr>\n"
        
        html += """
        </table>
        
        <h2>📱 Top Callers</h2>
        <table>
            <tr><th>Caller</th><th>Total Calls</th><th>Answer Rate</th></tr>
"""
        for caller in data['top_callers'][:10]:
            html += f"<tr><td>{caller['caller']}</td><td>{int(caller['total_calls']):,}</td><td>{caller['answer_rate']:.1f}%</td></tr>\n"
        
        html += """
        </table>
    </div>
</body>
</html>
"""
        return html
    
    def _generate_json_report(
        self,
        output_dir: str,
        title: str,
        include_quality: bool,
        include_security: bool
    ) -> str:
        """Generate JSON report"""
        report_data = {
            'title': title,
            'generated_at': datetime.now().isoformat(),
            'call_summary': self.analyzer.get_call_summary(),
            'top_callers': self.analyzer.users.get_top_callers(20).to_dict('records'),
            'top_called': self.analyzer.users.get_top_called(20).to_dict('records'),
            'daily_trend': self.analyzer.time.get_daily_call_volume().tail(30).to_dict('records'),
        }
        
        if include_quality and self.cmr is not None:
            report_data['quality_summary'] = self.analyzer.get_quality_summary()
        
        if include_security:
            report_data['security_summary'] = self.analyzer.security.get_security_summary()
        
        report_path = os.path.join(output_dir, 'report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        logger.info(f"JSON report generated: {report_path}")
        return report_path
    
    def _generate_excel_report(
        self,
        output_dir: str,
        title: str,
        include_quality: bool
    ) -> str:
        """Generate Excel report"""
        report_path = os.path.join(output_dir, 'report.xlsx')
        
        with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_df = pd.DataFrame([self.analyzer.get_call_summary()])
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Top callers
            top_callers = self.analyzer.users.get_top_callers(50)
            top_callers.to_excel(writer, sheet_name='Top Callers', index=False)
            
            # Top called
            top_called = self.analyzer.users.get_top_called(50)
            top_called.to_excel(writer, sheet_name='Top Called', index=False)
            
            # Daily trend
            daily = self.analyzer.time.get_daily_call_volume()
            daily.to_excel(writer, sheet_name='Daily Trend', index=False)
            
            # Weekly trend
            weekly = self.analyzer.time.get_weekly_trends()
            weekly.to_excel(writer, sheet_name='Weekly Trend', index=False)
            
            # Call types
            call_types = self.analyzer.time.get_calls_by_day_of_week()
            call_types.to_excel(writer, sheet_name='By Day of Week', index=False)
            
            # Device summary
            devices = self.analyzer.devices.get_device_summary()
            if not devices.empty:
                devices.to_excel(writer, sheet_name='Devices', index=False)
            
            # Quality data
            if include_quality and self.cmr is not None:
                quality_df = pd.DataFrame([self.analyzer.get_quality_summary()])
                quality_df.to_excel(writer, sheet_name='Quality Summary', index=False)
                
                # Quality issues
                issues = self.analyzer.quality.get_quality_issues()
                if not issues.empty:
                    issues.head(100).to_excel(writer, sheet_name='Quality Issues', index=False)
        
        logger.info(f"Excel report generated: {report_path}")
        return report_path
    
    def export_raw_data(
        self,
        output_dir: Optional[str] = None,
        format: str = 'csv'
    ) -> Dict[str, str]:
        """
        Export raw processed data
        
        :param output_dir: Output directory
        :param format: 'csv' or 'parquet'
        :return: Dictionary of exported file paths
        """
        output_dir = output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        exported = {}
        
        if self.cdr is not None:
            if format == 'csv':
                path = os.path.join(output_dir, 'processed_cdr.csv')
                self.cdr.to_csv(path, index=False)
            else:
                path = os.path.join(output_dir, 'processed_cdr.parquet')
                self.cdr.to_parquet(path, index=False)
            exported['cdr'] = path
        
        if self.cmr is not None:
            if format == 'csv':
                path = os.path.join(output_dir, 'processed_cmr.csv')
                self.cmr.to_csv(path, index=False)
            else:
                path = os.path.join(output_dir, 'processed_cmr.parquet')
                self.cmr.to_parquet(path, index=False)
            exported['cmr'] = path
        
        if self.merged is not None:
            if format == 'csv':
                path = os.path.join(output_dir, 'merged_data.csv')
                self.merged.to_csv(path, index=False)
            else:
                path = os.path.join(output_dir, 'merged_data.parquet')
                self.merged.to_parquet(path, index=False)
            exported['merged'] = path
        
        logger.info(f"Data exported to {output_dir}")
        return exported


# Import matplotlib for chart generation
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt