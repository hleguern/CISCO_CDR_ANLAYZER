#!/usr/bin/env python3
"""
Cisco CDR/CMR Analyzer - Main Application Entry Point

A comprehensive tool for analyzing Cisco Unified Communications Manager
Call Detail Records (CDR) and Call Management Records (CMR)

Usage:
    python -m cisco_cdr_analyzer --cdr path/to/cdr.csv --cmr path/to/cmr.csv
    python -m cisco_cdr_analyzer --cdr path/to/cdr.csv --report
    python -m cisco_cdr_analyzer --help
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cisco_cdr_analyzer import CiscoCDRAnalyzer
from cisco_cdr_analyzer.config.settings import Settings
from cisco_cdr_analyzer.visualization.reports import ReportGenerator
from cisco_cdr_analyzer.core.csv_importer import CSVImporter

DEFAULT_DB_PATH = os.path.join("data", "cdr_store.db")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cdr_analyzer.log')
    ]
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Cisco CDR/CMR Analyzer - Comprehensive call data analysis tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --cdr data/cdr.csv --cmr data/cmr.csv
  %(prog)s --cdr data/cdr.csv --report --output reports/
  %(prog)s --cdr "data/cdr_*.csv" --summary
  %(prog)s --cdr data/cdr.csv --user 1234 --days 30

CSV import into the local store:
  %(prog)s --import exports/ --import-only
  %(prog)s --import "exports/cdr_*.csv" --db data/cdr_store.db --summary
  %(prog)s --db data/cdr_store.db --report --store-days 30
  %(prog)s --db data/cdr_store.db --store-stats
        """
    )

    # Input files
    parser.add_argument(
        '--cdr', '-c',
        type=str,
        help='Path to CDR file(s). Supports glob patterns (e.g., "data/cdr_*.csv")'
    )

    # CSV import / store options
    parser.add_argument(
        '--import', '-i',
        dest='import_paths',
        action='append',
        metavar='PATH',
        help='Import CDR/CMR CSV file, directory or glob into the store (repeatable). '
             'Record type is detected from the header.'
    )

    parser.add_argument(
        '--db',
        type=str,
        default=None,
        help='SQLite store path (default: data/cdr_store.db). '
             'Without --cdr, analysis runs on the store.'
    )

    parser.add_argument(
        '--import-only',
        action='store_true',
        help='Only import files, skip analysis'
    )

    parser.add_argument(
        '--force-import',
        action='store_true',
        help='Re-import files even if already imported (duplicates are still ignored)'
    )

    parser.add_argument(
        '--store-days',
        type=int,
        default=None,
        help='When analyzing the store, only use records from the last N days'
    )

    parser.add_argument(
        '--store-stats',
        action='store_true',
        help='Print store statistics and import history'
    )
    
    parser.add_argument(
        '--cmr', '-m',
        type=str,
        help='Path to CMR file(s). Optional.'
    )
    
    # Output options
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='output',
        help='Output directory for reports and exports (default: output)'
    )
    
    parser.add_argument(
        '--report', '-r',
        action='store_true',
        help='Generate HTML report'
    )
    
    parser.add_argument(
        '--report-format',
        type=str,
        choices=['html', 'json', 'xlsx'],
        default='html',
        help='Report format (default: html)'
    )
    
    parser.add_argument(
        '--export-data',
        action='store_true',
        help='Export processed data to CSV'
    )
    
    # Analysis options
    parser.add_argument(
        '--summary', '-s',
        action='store_true',
        help='Print summary to console'
    )
    
    parser.add_argument(
        '--user', '-u',
        type=str,
        help='Analyze specific user/extension'
    )
    
    parser.add_argument(
        '--device', '-d',
        type=str,
        help='Analyze specific device'
    )
    
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to analyze (default: 30)'
    )
    
    # Quality options
    parser.add_argument(
        '--quality', '-q',
        action='store_true',
        help='Include quality analysis (requires CMR)'
    )
    
    parser.add_argument(
        '--security',
        action='store_true',
        help='Include security analysis'
    )
    
    # Visualization options
    parser.add_argument(
        '--charts',
        action='store_true',
        help='Generate chart images'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Generate interactive HTML charts (requires plotly)'
    )
    
    # Other options
    parser.add_argument(
        '--encoding',
        type=str,
        default='utf-8',
        help='File encoding (default: utf-8)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Debug mode with detailed logging'
    )
    
    return parser.parse_args()


def main():
    """Main application entry point"""
    args = parse_arguments()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.verbose:
        logging.getLogger().setLevel(logging.INFO)
    else:
        logging.getLogger().setLevel(logging.WARNING)
    
    print("\n" + "=" * 70)
    print("         CISCO CDR/CMR ANALYZER v2.0")
    print("=" * 70 + "\n")
    
    # Initialize analyzer
    settings = Settings()
    settings.output_dir = args.output
    analyzer = CiscoCDRAnalyzer(settings)
    
    db_path = args.db or DEFAULT_DB_PATH
    use_store = not args.cdr

    if not args.cdr and not args.import_paths and not args.db and not args.store_stats:
        print("❌ Provide --cdr <file> or --import <path> / --db <store>")
        return 2

    try:
        # Import CSV files into the store
        if args.import_paths:
            importer = CSVImporter(db_path)
            print(f"📥 Importing into store: {db_path}")
            failed = 0
            for path in args.import_paths:
                for result in importer.import_path(path, force=args.force_import):
                    print(f"   {'✓' if result.ok else '✗'} {result}")
                    for warning in result.warnings:
                        print(f"     ⚠ {warning}")
                    failed += 0 if result.ok else 1
            print()
            if args.import_only:
                return 1 if failed else 0

        if args.store_stats:
            importer = CSVImporter(db_path)
            stats = importer.stats()
            print("🗄  STORE STATISTICS")
            print("-" * 50)
            for key, value in stats.items():
                print(f"  {key:<15}: {value}")
            history = importer.import_history(limit=10)
            if not history.empty:
                print("\n  Recent imports:")
                for _, row in history.iterrows():
                    print(f"    {row['imported_at']}  {row['record_type'].upper()}  "
                          f"{row['file_name']}  (+{row['rows_inserted']}, "
                          f"{row['rows_duplicate']} dup)")
            print()
            if use_store and not (args.summary or args.report or args.user or args.device
                                  or args.quality or args.security or args.charts):
                return 0

        if use_store:
            # Load CDR/CMR data from the store
            print(f"📂 Loading data from store: {db_path}")
            analyzer.load_from_store(db_path, days=args.store_days)
            print(f"   ✓ Loaded {len(analyzer.cdr_df):,} CDR records")
            if analyzer.cmr_df is not None:
                print(f"   ✓ Loaded {len(analyzer.cmr_df):,} CMR records\n")
                print("🔗 Merging CDR and CMR data...")
                analyzer.merge_data()
                print(f"   ✓ Merged {len(analyzer.merged_df):,} records\n")
            else:
                print()
        else:
            # Load CDR data
            print(f"📂 Loading CDR data from: {args.cdr}")
            analyzer.load_cdr(args.cdr, encoding=args.encoding)
            print(f"   ✓ Loaded {len(analyzer.cdr_df):,} CDR records\n")

        # Load CMR data if provided
        if args.cmr and not use_store:
            print(f"📂 Loading CMR data from: {args.cmr}")
            analyzer.load_cmr(args.cmr, encoding=args.encoding)
            print(f"   ✓ Loaded {len(analyzer.cmr_df):,} CMR records\n")
            
            # Merge data
            print("🔗 Merging CDR and CMR data...")
            analyzer.merge_data()
            print(f"   ✓ Merged {len(analyzer.merged_df):,} records\n")
        
        # Print summary if requested
        if args.summary or (not args.report and not args.user and not args.device):
            analyzer.print_summary()
        
        # User analysis
        if args.user:
            print(f"\n📱 Analyzing user: {args.user}")
            print("-" * 50)
            
            user_stats = analyzer.users.get_user_statistics(args.user)
            
            if 'error' in user_stats:
                print(f"   ❌ {user_stats['error']}")
            else:
                print(f"   Total Calls:     {user_stats['total_calls']:,}")
                print(f"   Outgoing:        {user_stats['outgoing']['total']:,}")
                print(f"   Incoming:        {user_stats['incoming']['total']:,}")
                print(f"   Total Duration:  {user_stats['total_duration_sec']:,}s")
                print(f"   Avg Duration:    {user_stats['avg_call_duration_sec']}s")
                print(f"   Devices Used:    {', '.join(user_stats['devices_used'][:3])}")
            
            # User activity pattern
            activity = analyzer.users.get_user_activity_pattern(args.user)
            if activity and 'peak_hour' in activity:
                print(f"\n   Activity Pattern:")
                print(f"   - Peak Hour:      {activity['peak_hour_label']}")
                print(f"   - Peak Day:       {activity['peak_day']}")
                print(f"   - Business Hours: {activity['business_hours_pct']}%")
        
        # Device analysis
        if args.device:
            print(f"\n📟 Analyzing device: {args.device}")
            print("-" * 50)
            
            device_stats = analyzer.devices.get_device_statistics(args.device)
            
            if 'error' in device_stats:
                print(f"   ❌ {device_stats['error']}")
            else:
                print(f"   Device Type:     {device_stats['device_type']}")
                print(f"   Total Calls:     {device_stats['total_calls']:,}")
                print(f"   Originated:      {device_stats['originated_calls']:,}")
                print(f"   Received:        {device_stats['received_calls']:,}")
                print(f"   Answer Rate:     {device_stats['answer_rate']}%")
        
        # Quality analysis
        if args.quality and analyzer.cmr_df is not None:
            print("\n📶 Quality Analysis")
            print("-" * 50)
            
            quality = analyzer.get_quality_summary()
            print(f"   Avg Jitter:      {quality['metrics']['jitter']['orig_avg']:.2f} ms")
            print(f"   Avg Latency:     {quality['metrics']['latency']['orig_avg']:.2f} ms")
            print(f"   Packet Loss:     {quality['metrics']['packet_loss']['orig_avg_pct']:.4f}%")
            
            if 'mos' in quality:
                print(f"   Average MOS:     {quality['mos']['average']:.2f}")
            
            # Quality issues
            issues = analyzer.quality.get_quality_issues()
            if not issues.empty:
                print(f"\n   ⚠️  Found {len(issues)} calls with quality issues")
        
        # Security analysis
        if args.security:
            print("\n🔒 Security Analysis")
            print("-" * 50)
            
            security = analyzer.security.get_security_summary()
            print(f"   Risk Level:      {security['overall_risk_level']}")
            print(f"   Total Alerts:    {security['total_alerts']}")
            
            if security['total_alerts'] > 0:
                print(f"   - High Severity:   {security['high_severity_alerts']}")
                print(f"   - Medium Severity: {security['medium_severity_alerts']}")
                
                print("\n   Recommendations:")
                for rec in security['recommendations'][:3]:
                    print(f"   • {rec}")
        
        # Generate charts
        if args.charts:
            print("\n📊 Generating charts...")
            os.makedirs(args.output, exist_ok=True)
            
            from cisco_cdr_analyzer.visualization.charts import ChartGenerator
            chart_gen = ChartGenerator(analyzer)
            
            charts_dir = os.path.join(args.output, 'charts')
            os.makedirs(charts_dir, exist_ok=True)
            
            # Generate various charts
            fig = chart_gen.plot_calls_by_hour()
            if fig:
                fig.savefig(os.path.join(charts_dir, 'calls_by_hour.png'), dpi=150, bbox_inches='tight')
                print("   ✓ calls_by_hour.png")
            
            fig = chart_gen.plot_daily_trend(days=args.days)
            if fig:
                fig.savefig(os.path.join(charts_dir, 'daily_trend.png'), dpi=150, bbox_inches='tight')
                print("   ✓ daily_trend.png")
            
            fig = chart_gen.plot_call_types()
            if fig:
                fig.savefig(os.path.join(charts_dir, 'call_types.png'), dpi=150, bbox_inches='tight')
                print("   ✓ call_types.png")
            
            fig = chart_gen.plot_top_callers()
            if fig:
                fig.savefig(os.path.join(charts_dir, 'top_callers.png'), dpi=150, bbox_inches='tight')
                print("   ✓ top_callers.png")
            
            if analyzer.cmr_df is not None:
                fig = chart_gen.plot_quality_metrics()
                if fig:
                    fig.savefig(os.path.join(charts_dir, 'quality_metrics.png'), dpi=150, bbox_inches='tight')
                    print("   ✓ quality_metrics.png")
            
            print(f"\n   Charts saved to: {charts_dir}/")
        
        # Generate interactive charts
        if args.interactive:
            print("\n📈 Generating interactive charts...")
            
            try:
                from cisco_cdr_analyzer.visualization.interactive import InteractiveVisualizer
                interactive = InteractiveVisualizer(analyzer)
                
                charts_dir = os.path.join(args.output, 'interactive')
                os.makedirs(charts_dir, exist_ok=True)
                
                fig = interactive.plot_daily_trend_interactive(days=args.days)
                if fig:
                    fig.write_html(os.path.join(charts_dir, 'daily_trend.html'))
                    print("   ✓ daily_trend.html")
                
                fig = interactive.plot_hourly_heatmap_interactive()
                if fig:
                    fig.write_html(os.path.join(charts_dir, 'hourly_heatmap.html'))
                    print("   ✓ hourly_heatmap.html")
                
                fig = interactive.plot_call_flow_sankey()
                if fig:
                    fig.write_html(os.path.join(charts_dir, 'call_flow.html'))
                    print("   ✓ call_flow.html")
                
                fig = interactive.plot_kpi_gauges()
                if fig:
                    fig.write_html(os.path.join(charts_dir, 'kpi_gauges.html'))
                    print("   ✓ kpi_gauges.html")
                
                print(f"\n   Interactive charts saved to: {charts_dir}/")
                
            except ImportError:
                print("   ⚠️  Plotly not installed. Install with: pip install plotly")
        
        # Generate report
        if args.report:
            print(f"\n📄 Generating {args.report_format.upper()} report...")
            
            report_gen = ReportGenerator(analyzer)
            report_path = report_gen.generate_report(
                output_dir=args.output,
                title='CDR Analysis Report',
                include_charts=True,
                include_quality=analyzer.cmr_df is not None,
                include_security=True,
                format=args.report_format
            )
            
            print(f"   ✓ Report saved to: {report_path}")
        
        # Export data
        if args.export_data:
            print("\n💾 Exporting processed data...")
            
            report_gen = ReportGenerator(analyzer)
            exported = report_gen.export_raw_data(args.output, format='csv')
            
            for name, path in exported.items():
                print(f"   ✓ {name}: {path}")
        
        print("\n" + "=" * 70)
        print("                    Analysis Complete!")
        print("=" * 70 + "\n")
        
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error during analysis: {e}")
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())