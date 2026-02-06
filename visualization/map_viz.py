"""
Advanced Map Visualization Module for CDR/CMR Data

Features:
- Full timelapse animation with proper show/hide of markers
- Animated connection lines between caller and called
- Real-time statistics panel
- Play/Pause/Speed controls
- Time window filtering (only shows calls within selected time range)
- Quality-based coloring
- Heat map overlay option
- Advanced filtering and controls
- **UNLIMITED CALLS support**
- **Day-by-day navigation**

Author: CDR Analyzer Team
Version: 4.0
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
import logging
import re
import os
import json

try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# PHONE NUMBER TO LOCATION MAPPING
# ============================================================================

COUNTRY_CODE_COORDS = {
    '1': ('USA', 37.0902, -95.7129),
    '44': ('UK', 55.3781, -3.4360),
    '49': ('Germany', 51.1657, 10.4515),
    '33': ('France', 46.2276, 2.2137),
    '39': ('Italy', 41.8719, 12.5674),
    '34': ('Spain', 40.4168, -3.7038),
    '31': ('Netherlands', 52.1326, 5.2913),
    '32': ('Belgium', 50.5039, 4.4699),
    '41': ('Switzerland', 46.8182, 8.2275),
    '43': ('Austria', 47.5162, 14.5501),
    '48': ('Poland', 51.9194, 19.1451),
    '420': ('Czech Republic', 49.8175, 15.4730),
    '46': ('Sweden', 60.1282, 18.6435),
    '47': ('Norway', 60.4720, 8.4689),
    '45': ('Denmark', 56.2639, 9.5018),
    '358': ('Finland', 61.9241, 25.7482),
    '7': ('Russia', 61.5240, 105.3188),
    '86': ('China', 35.8617, 104.1954),
    '81': ('Japan', 36.2048, 138.2529),
    '82': ('South Korea', 35.9078, 127.7669),
    '91': ('India', 20.5937, 78.9629),
    '61': ('Australia', -25.2744, 133.7751),
    '55': ('Brazil', -14.2350, -51.9253),
    '52': ('Mexico', 23.6345, -102.5528),
    '27': ('South Africa', -30.5595, 22.9375),
    '971': ('UAE', 23.4241, 53.8478),
    '966': ('Saudi Arabia', 23.8859, 45.0792),
    '90': ('Turkey', 38.9637, 35.2433),
    '380': ('Ukraine', 48.3794, 31.1656),
}

GERMAN_AREA_CODES = {
    '30': ('Berlin', 52.5200, 13.4050),
    '40': ('Hamburg', 53.5511, 9.9937),
    '89': ('Munich', 48.1351, 11.5820),
    '69': ('Frankfurt', 50.1109, 8.6821),
    '221': ('Cologne', 50.9375, 6.9603),
    '211': ('Düsseldorf', 51.2277, 6.7735),
    '711': ('Stuttgart', 48.7758, 9.1829),
    '351': ('Dresden', 51.0504, 13.7373),
    '341': ('Leipzig', 51.3397, 12.3731),
    '421': ('Bremen', 53.0793, 8.8017),
    '511': ('Hanover', 52.3759, 9.7320),
    '201': ('Essen', 51.4556, 7.0116),
    '231': ('Dortmund', 51.5136, 7.4653),
    '203': ('Duisburg', 51.4344, 6.7623),
    '234': ('Bochum', 51.4818, 7.2162),
    '202': ('Wuppertal', 51.2562, 7.1508),
    '521': ('Bielefeld', 52.0302, 8.5325),
    '228': ('Bonn', 50.7374, 7.0982),
    '251': ('Münster', 51.9607, 7.6261),
    '721': ('Karlsruhe', 49.0069, 8.4037),
    '621': ('Mannheim', 49.4875, 8.4660),
    '611': ('Wiesbaden', 50.0782, 8.2398),
    '381': ('Rostock', 54.0924, 12.0991),
    '391': ('Magdeburg', 52.1205, 11.6276),
    '345': ('Halle', 51.4969, 11.9688),
    '361': ('Erfurt', 50.9848, 11.0299),
    '371': ('Chemnitz', 50.8278, 12.9214),
    '531': ('Braunschweig', 52.2689, 10.5268),
    '541': ('Osnabrück', 52.2799, 8.0472),
    '441': ('Oldenburg', 53.1435, 8.2146),
    '561': ('Kassel', 51.3127, 9.4797),
    '461': ('Flensburg', 54.7937, 9.4469),
    '431': ('Kiel', 54.3233, 10.1228),
    '451': ('Lübeck', 53.8655, 10.6866),
    '911': ('Nürnberg', 49.4521, 11.0767),
    '821': ('Augsburg', 48.3705, 10.8978),
    '941': ('Regensburg', 49.0134, 12.1016),
    '851': ('Passau', 48.5665, 13.4314),
    '761': ('Freiburg', 47.9990, 7.8421),
    '731': ('Ulm', 48.4011, 9.9876),
    '841': ('Ingolstadt', 48.7665, 11.4257),
    '931': ('Würzburg', 49.7913, 9.9534),
    '303': ('Berlin area', 52.5200, 13.4050),
    '151': ('Mobile D1', 51.1657, 10.4515),
    '152': ('Mobile D1', 51.1657, 10.4515),
    '157': ('Mobile E-Plus', 51.1657, 10.4515),
    '160': ('Mobile D2', 51.1657, 10.4515),
    '170': ('Mobile D1', 51.1657, 10.4515),
    '171': ('Mobile D1', 51.1657, 10.4515),
    '172': ('Mobile D2', 51.1657, 10.4515),
    '173': ('Mobile D2', 51.1657, 10.4515),
    '174': ('Mobile D2', 51.1657, 10.4515),
    '175': ('Mobile D1', 51.1657, 10.4515),
    '176': ('Mobile O2', 51.1657, 10.4515),
    '177': ('Mobile E-Plus', 51.1657, 10.4515),
    '178': ('Mobile E-Plus', 51.1657, 10.4515),
    '179': ('Mobile O2', 51.1657, 10.4515),
}


class AdvancedMapVisualizer:
    """
    Advanced Map Visualizer with full timeline control and day navigation
    
    Creates interactive maps with:
    - Timeline slider showing only calls at selected time
    - Animated connection lines
    - Real-time statistics
    - Play/pause controls
    - Speed adjustment
    - Filtering options
    - **Day-by-day navigation**
    - **Unlimited calls support**
    """
    
    def __init__(self, analyzer):
        """
        Initialize the map visualizer
        
        :param analyzer: CiscoCDRAnalyzer instance
        """
        self.analyzer = analyzer
        self._location_cache = {}
        self.output_dir = getattr(analyzer.settings, 'output_dir', './output')
        
        if not FOLIUM_AVAILABLE:
            logger.warning("Folium not available. Install with: pip install folium")
    
    @property
    def cdr(self) -> Optional[pd.DataFrame]:
        """Get CDR DataFrame"""
        return self.analyzer.cdr_df
    
    @property
    def cmr(self) -> Optional[pd.DataFrame]:
        """Get CMR DataFrame"""
        return self.analyzer.cmr_df
    
    def _check_folium(self) -> bool:
        """Check if Folium is available"""
        if not FOLIUM_AVAILABLE:
            logger.error("Folium is required. Install with: pip install folium")
            return False
        return True
    
    def _check_data_loaded(self) -> bool:
        """Check if data is loaded"""
        if self.cdr is None:
            logger.error("CDR data not loaded")
            return False
        return True
    
    def _parse_phone_location(self, phone_number: str) -> Optional[Tuple[str, float, float]]:
        """
        Parse phone number to get approximate location
        
        :param phone_number: Phone number string
        :return: Tuple of (location_name, latitude, longitude) or None
        """
        if not phone_number or str(phone_number) in ['', 'nan', '\\', 'None', ' ']:
            return None
        
        # Check cache
        cache_key = str(phone_number)
        if cache_key in self._location_cache:
            return self._location_cache[cache_key]
        
        # Clean the number
        clean_num = re.sub(r'[^\d+]', '', str(phone_number))
        
        # Handle + prefix
        if clean_num.startswith('+'):
            clean_num = clean_num[1:]
        elif clean_num.startswith('00'):
            clean_num = clean_num[2:]
        
        result = None
        
        # Try to match German area codes first (for +49 numbers)
        if clean_num.startswith('49'):
            local_num = clean_num[2:]  # Remove country code
            
            # Try different area code lengths (3, 2 digits)
            for length in [3, 2]:
                if len(local_num) >= length:
                    area_code = local_num[:length]
                    if area_code in GERMAN_AREA_CODES:
                        city, lat, lon = GERMAN_AREA_CODES[area_code]
                        # Add small random offset to prevent marker stacking
                        lat += np.random.uniform(-0.03, 0.03)
                        lon += np.random.uniform(-0.03, 0.03)
                        result = (city, lat, lon)
                        break
            
            if result is None:
                # Default to Germany center with offset
                result = ('Germany', 51.1657 + np.random.uniform(-0.5, 0.5), 
                         10.4515 + np.random.uniform(-0.5, 0.5))
        
        # Try country codes
        if result is None:
            for code_len in [3, 2, 1]:
                if len(clean_num) >= code_len:
                    code = clean_num[:code_len]
                    if code in COUNTRY_CODE_COORDS:
                        name, lat, lon = COUNTRY_CODE_COORDS[code]
                        lat += np.random.uniform(-0.3, 0.3)
                        lon += np.random.uniform(-0.3, 0.3)
                        result = (name, lat, lon)
                        break
        
        # Default fallback
        if result is None:
            result = ('Unknown', 51.1657 + np.random.uniform(-1, 1), 
                     10.4515 + np.random.uniform(-1, 1))
        
        # Cache result
        self._location_cache[cache_key] = result
        return result
    
    def _get_cmr_for_call(self, call_id) -> Optional[Dict]:
        """Get CMR data for a specific call ID"""
        if self.cmr is None or call_id is None:
            return None
        
        try:
            cmr_match = self.cmr[self.cmr['globalCallID_callId'] == call_id]
            if not cmr_match.empty:
                return cmr_match.iloc[0].to_dict()
        except Exception as e:
            logger.debug(f"Error getting CMR data: {e}")
        return None
    
    def _format_duration(self, seconds) -> str:
        """Format duration as string"""
        if pd.isna(seconds):
            return "0s"
        try:
            seconds = int(seconds)
        except:
            return "0s"
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    def _prepare_call_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_calls: Optional[int] = None  # Changed to None for unlimited
    ) -> Tuple[List[Dict], List[str]]:
        """
        Prepare call data with location information
        
        :return: Tuple of (List of call dictionaries with location data, List of available dates)
        """
        if self.cdr is None:
            return [], []
        
        df = self.cdr.copy()
        
        # ========================================================
        # FIX: Ensure proper timestamp conversion from Unix epoch
        # ========================================================
        if 'dateTimeOrigination' in df.columns:
            # Debug: Show sample raw timestamp conversion
            if len(df) > 0:
                sample_ts = df['dateTimeOrigination'].iloc[0]
                try:
                    sample_converted = pd.Timestamp.utcfromtimestamp(int(float(sample_ts)))
                    logger.info(f"DEBUG: Raw timestamp {sample_ts} -> {sample_converted}")
                except Exception as e:
                    logger.warning(f"DEBUG: Could not convert sample timestamp: {e}")
            
            # Always convert from Unix timestamp to ensure correctness
            df['dateTimeOrigination_dt'] = pd.to_datetime(
                pd.to_numeric(df['dateTimeOrigination'], errors='coerce'),
                unit='s',
                utc=True
            )
        
        # Apply date filters
        if 'dateTimeOrigination_dt' in df.columns:
            # Remove timezone for comparison if needed
            df['dateTimeOrigination_dt'] = df['dateTimeOrigination_dt'].dt.tz_localize(None)
            
            if start_date:
                df = df[df['dateTimeOrigination_dt'] >= start_date]
            if end_date:
                df = df[df['dateTimeOrigination_dt'] <= end_date]
        
        # Sort by time
        if 'dateTimeOrigination_dt' in df.columns:
            df = df.sort_values('dateTimeOrigination_dt')
        
        # Get all unique dates for day navigation
        available_dates = []
        if 'dateTimeOrigination_dt' in df.columns:
            df['date_only'] = df['dateTimeOrigination_dt'].dt.date
            available_dates = sorted(df['date_only'].dropna().unique())
            available_dates = [d.strftime('%Y-%m-%d') for d in available_dates]
        
        # Limit records only if max_calls is specified
        if max_calls is not None and max_calls > 0:
            df = df.head(max_calls)
        
        calls = []
        
        for idx, row in df.iterrows():
            try:
                # Parse locations
                caller_loc = self._parse_phone_location(row.get('callingPartyNumber', ''))
                called_loc = self._parse_phone_location(row.get('finalCalledPartyNumber', ''))
                
                # Skip if no valid locations
                if caller_loc is None and called_loc is None:
                    continue
                
                # ========================================================
                # FIX: Proper timestamp handling from raw Unix timestamp
                # ========================================================
                timestamp = None
                raw_ts = row.get('dateTimeOrigination')
                
                if pd.notna(raw_ts):
                    try:
                        # Convert Unix timestamp (seconds since 1970-01-01)
                        unix_ts = int(float(raw_ts))
                        timestamp = pd.Timestamp.utcfromtimestamp(unix_ts)
                        # Remove timezone info for consistency
                        timestamp = timestamp.tz_localize(None)
                    except (ValueError, TypeError, OSError) as e:
                        logger.debug(f"Error converting timestamp {raw_ts}: {e}")
                        timestamp = row.get('dateTimeOrigination_dt')
                else:
                    timestamp = row.get('dateTimeOrigination_dt')
                
                if timestamp is None or pd.isna(timestamp):
                    logger.debug(f"Skipping row {idx}: No valid timestamp")
                    continue
                
                # Ensure timestamp is a pandas Timestamp
                if not isinstance(timestamp, pd.Timestamp):
                    timestamp = pd.Timestamp(timestamp)
                
                # Get end time based on duration
                duration = row.get('duration', 0) or 0
                try:
                    duration = int(duration)
                except (ValueError, TypeError):
                    duration = 0
                
                # End time: call duration + at least 1 minute visibility
                end_time = timestamp + timedelta(seconds=max(duration, 60))
                
                # Get CMR data
                cmr_data = self._get_cmr_for_call(row.get('globalCallID_callId'))
                
                # Determine answered status
                answered = bool(row.get('answered', False))
                if duration > 0:
                    answered = True
                
                # Calculate quality score (MOS estimate if not available)
                mos = None
                if cmr_data:
                    mos = cmr_data.get('avg_mos')
                    if mos is None:
                        jitter = cmr_data.get('origjitter', 0) or 0
                        latency = cmr_data.get('origlatency', 0) or 0
                        if jitter < 10 and latency < 50:
                            mos = 4.5
                        elif jitter < 30 and latency < 150:
                            mos = 4.0
                        elif jitter < 50 and latency < 300:
                            mos = 3.5
                        else:
                            mos = 3.0
                
                # Get the date string for this call
                call_date = timestamp.strftime('%Y-%m-%d')
                
                # ========================================================
                # Build call data dictionary
                # ========================================================
                call_data = {
                    'id': str(row.get('globalCallID_callId', idx)),
                    'timestamp': timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
                    'timestamp_ms': int(timestamp.timestamp() * 1000),
                    'end_time': end_time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'end_time_ms': int(end_time.timestamp() * 1000),
                    'date': call_date,  # Add date for day filtering
                    'caller': str(row.get('callingPartyNumber', 'Unknown')),
                    'called': str(row.get('finalCalledPartyNumber', 'Unknown')),
                    'caller_location': caller_loc[0] if caller_loc else 'Unknown',
                    'caller_lat': float(caller_loc[1]) if caller_loc else None,
                    'caller_lon': float(caller_loc[2]) if caller_loc else None,
                    'called_location': called_loc[0] if called_loc else 'Unknown',
                    'called_lat': float(called_loc[1]) if called_loc else None,
                    'called_lon': float(called_loc[2]) if called_loc else None,
                    'duration': duration,
                    'duration_str': self._format_duration(duration),
                    'answered': answered,
                    'call_type': str(row.get('call_type', 'unknown')),
                    'orig_device': str(row.get('origDeviceName', 'N/A')),
                    'dest_device': str(row.get('destDeviceName', 'N/A')),
                    'mos': float(mos) if mos else None,
                    'jitter': float(cmr_data.get('origjitter', 0)) if cmr_data and cmr_data.get('origjitter') else None,
                    'latency': float(cmr_data.get('origlatency', 0)) if cmr_data and cmr_data.get('origlatency') else None,
                    'packets_lost': int(cmr_data.get('orignumberPacketsLost', 0)) if cmr_data and cmr_data.get('orignumberPacketsLost') else None,
                }
                
                # Only add if we have at least one valid location
                if call_data['caller_lat'] is not None or call_data['called_lat'] is not None:
                    calls.append(call_data)
                    
            except Exception as e:
                logger.debug(f"Error processing row {idx}: {e}")
                continue
        
        # Log the date range for debugging
        if calls:
            timestamps_list = [c['timestamp'] for c in calls]
            logger.info(f"Call data prepared: {len(calls)} calls")
            logger.info(f"Date range: {min(timestamps_list)} to {max(timestamps_list)}")
            logger.info(f"Available dates: {len(available_dates)} days")
        else:
            logger.warning("No calls prepared - check data and filters")
        
        return calls, available_dates

    def create_advanced_timeline_map(
        self,
        max_calls: Optional[int] = None,  # None = unlimited
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        center: Optional[Tuple[float, float]] = None,
        zoom_start: int = 6,
        time_window_minutes: int = 60,
        show_heatmap: bool = True,
        dark_mode: bool = False,
        enable_day_navigation: bool = True  # New parameter
    ) -> Optional[str]:
        """
        Create an advanced interactive map with proper timeline control and day navigation
        
        Features:
        - Timeline slider that shows only calls within the time window
        - Animated connection lines
        - Real-time statistics
        - Play/pause/speed controls
        - Call filtering
        - **Day-by-day navigation**
        - **Unlimited calls support**
        
        :param max_calls: Maximum number of calls to display (None = unlimited)
        :param start_date: Optional start date filter
        :param end_date: Optional end date filter
        :param center: Map center coordinates (lat, lon)
        :param zoom_start: Initial zoom level
        :param time_window_minutes: Time window size in minutes
        :param show_heatmap: Show heat map option
        :param dark_mode: Use dark map theme
        :param enable_day_navigation: Enable day-by-day navigation
        :return: HTML string of the complete map
        """
        if not self._check_folium() or not self._check_data_loaded():
            return None
        
        # Prepare call data
        calls, available_dates = self._prepare_call_data(start_date, end_date, max_calls)
        
        if not calls:
            logger.warning("No call data available for mapping")
            return None
        
        logger.info(f"Creating advanced timeline map with {len(calls)} calls across {len(available_dates)} days")
        
        # Determine map center
        if center is None:
            valid_lats = [c['caller_lat'] for c in calls if c['caller_lat']] + \
                        [c['called_lat'] for c in calls if c['called_lat']]
            valid_lons = [c['caller_lon'] for c in calls if c['caller_lon']] + \
                        [c['called_lon'] for c in calls if c['called_lon']]
            
            if valid_lats and valid_lons:
                center = (np.mean(valid_lats), np.mean(valid_lons))
            else:
                center = (51.1657, 10.4515)
        
        # Get time range
        timestamps = [c['timestamp_ms'] for c in calls if c['timestamp_ms']]
        if timestamps:
            min_time = min(timestamps)
            max_time = max(timestamps)
        else:
            min_time = int(datetime.now().timestamp() * 1000) - 86400000
            max_time = int(datetime.now().timestamp() * 1000)
        
        # Calculate statistics
        total_calls = len(calls)
        answered_calls = sum(1 for c in calls if c['answered'])
        total_duration = sum(c['duration'] for c in calls)
        avg_duration = total_duration / total_calls if total_calls > 0 else 0
        
        # Generate the complete HTML with embedded JavaScript
        html_content = self._generate_advanced_map_html(
            calls=calls,
            available_dates=available_dates,
            center=center,
            zoom_start=zoom_start,
            min_time=min_time,
            max_time=max_time,
            time_window_minutes=time_window_minutes,
            total_calls=total_calls,
            answered_calls=answered_calls,
            avg_duration=avg_duration,
            dark_mode=dark_mode,
            show_heatmap=show_heatmap,
            enable_day_navigation=enable_day_navigation
        )
        
        return html_content
    
    def _generate_advanced_map_html(
        self,
        calls: List[Dict],
        available_dates: List[str],
        center: Tuple[float, float],
        zoom_start: int,
        min_time: int,
        max_time: int,
        time_window_minutes: int,
        total_calls: int,
        answered_calls: int,
        avg_duration: float,
        dark_mode: bool,
        show_heatmap: bool,
        enable_day_navigation: bool
    ) -> str:
        """Generate the complete HTML for the advanced map"""
        
        # Convert calls to JSON
        calls_json = json.dumps(calls)
        dates_json = json.dumps(available_dates)
        
        # Choose tile layer
        if dark_mode:
            tile_url = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
            tile_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        else:
            tile_url = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
            tile_attr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CDR Call Timeline Map</title>
    
    <!-- Leaflet CSS -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    
    <!-- Font Awesome for icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: {'#1a1a2e' if dark_mode else '#f5f7fa'};
        }}
        
        #map {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }}
        
        /* Header Panel */
        .header-panel {{
            position: fixed;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: {'rgba(26, 26, 46, 0.95)' if dark_mode else 'rgba(255, 255, 255, 0.98)'};
            padding: 12px 25px;
            border-radius: 50px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 20px;
            backdrop-filter: blur(10px);
        }}
        
        .header-panel h1 {{
            font-size: 18px;
            font-weight: 600;
            color: {'#fff' if dark_mode else '#2c3e50'};
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .header-panel .badge {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }}
        
        /* Day Navigation Panel */
        .day-nav-panel {{
            position: fixed;
            top: 75px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: {'rgba(26, 26, 46, 0.95)' if dark_mode else 'rgba(255, 255, 255, 0.98)'};
            padding: 10px 20px;
            border-radius: 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            display: flex;
            align-items: center;
            gap: 15px;
            backdrop-filter: blur(10px);
        }}
        
        .day-nav-btn {{
            width: 36px;
            height: 36px;
            border: none;
            border-radius: 50%;
            background: {'#333' if dark_mode else '#ecf0f1'};
            color: {'#fff' if dark_mode else '#2c3e50'};
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            transition: all 0.2s ease;
        }}
        
        .day-nav-btn:hover:not(:disabled) {{
            background: #667eea;
            color: white;
            transform: scale(1.1);
        }}
        
        .day-nav-btn:disabled {{
            opacity: 0.4;
            cursor: not-allowed;
        }}
        
        .current-day-display {{
            font-size: 16px;
            font-weight: 600;
            color: {'#fff' if dark_mode else '#2c3e50'};
            min-width: 150px;
            text-align: center;
        }}
        
        .day-selector {{
            padding: 8px 12px;
            border-radius: 8px;
            border: 1px solid {'rgba(255,255,255,0.2)' if dark_mode else 'rgba(0,0,0,0.1)'};
            background: {'#333' if dark_mode else '#fff'};
            color: {'#fff' if dark_mode else '#2c3e50'};
            font-size: 14px;
            cursor: pointer;
            font-family: inherit;
        }}
        
        .day-call-count {{
            font-size: 12px;
            color: {'#888' if dark_mode else '#7f8c8d'};
            margin-left: 5px;
        }}
        
        .view-mode-toggle {{
            display: flex;
            background: {'#222' if dark_mode else '#e0e0e0'};
            border-radius: 20px;
            padding: 3px;
        }}
        
        .view-mode-btn {{
            padding: 6px 12px;
            border: none;
            border-radius: 17px;
            background: transparent;
            color: {'#888' if dark_mode else '#666'};
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
        }}
        
        .view-mode-btn.active {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }}
        
        /* Stats Panel */
        .stats-panel {{
            position: fixed;
            top: 140px;
            right: 20px;
            z-index: 1000;
            background: {'rgba(26, 26, 46, 0.95)' if dark_mode else 'rgba(255, 255, 255, 0.98)'};
            padding: 20px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            min-width: 280px;
            backdrop-filter: blur(10px);
        }}
        
        .stats-panel h3 {{
            font-size: 14px;
            font-weight: 600;
            color: {'#a0a0a0' if dark_mode else '#7f8c8d'};
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .stat-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid {'rgba(255,255,255,0.1)' if dark_mode else 'rgba(0,0,0,0.05)'};
        }}
        
        .stat-item:last-child {{
            border-bottom: none;
        }}
        
        .stat-label {{
            color: {'#ccc' if dark_mode else '#555'};
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .stat-value {{
            font-size: 16px;
            font-weight: 600;
            color: {'#fff' if dark_mode else '#2c3e50'};
        }}
        
        .stat-value.success {{ color: #27ae60; }}
        .stat-value.warning {{ color: #f39c12; }}
        .stat-value.danger {{ color: #e74c3c; }}
        .stat-value.info {{ color: #3498db; }}
        
        /* Day Summary Stats */
        .day-summary {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 2px solid {'rgba(255,255,255,0.1)' if dark_mode else 'rgba(0,0,0,0.05)'};
        }}
        
        .day-summary h4 {{
            font-size: 12px;
            font-weight: 600;
            color: #667eea;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        /* Timeline Control */
        .timeline-control {{
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 1000;
            background: {'rgba(26, 26, 46, 0.98)' if dark_mode else 'rgba(255, 255, 255, 0.98)'};
            padding: 20px 30px;
            border-radius: 20px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
            width: 90%;
            max-width: 900px;
            backdrop-filter: blur(10px);
        }}
        
        .timeline-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .current-time {{
            font-size: 24px;
            font-weight: 600;
            color: {'#fff' if dark_mode else '#2c3e50'};
            font-variant-numeric: tabular-nums;
        }}
        
        .time-range {{
            font-size: 12px;
            color: {'#888' if dark_mode else '#7f8c8d'};
        }}
        
        .playback-controls {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .control-btn {{
            width: 40px;
            height: 40px;
            border: none;
            border-radius: 50%;
            background: {'#333' if dark_mode else '#ecf0f1'};
            color: {'#fff' if dark_mode else '#2c3e50'};
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            transition: all 0.2s ease;
        }}
        
        .control-btn:hover {{
            background: #667eea;
            color: white;
            transform: scale(1.1);
        }}
        
        .control-btn.active {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }}
        
        .speed-control {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: 15px;
            padding-left: 15px;
            border-left: 1px solid {'rgba(255,255,255,0.2)' if dark_mode else 'rgba(0,0,0,0.1)'};
        }}
        
        .speed-control label {{
            font-size: 12px;
            color: {'#888' if dark_mode else '#7f8c8d'};
        }}
        
        .speed-control select {{
            padding: 5px 10px;
            border-radius: 8px;
            border: 1px solid {'rgba(255,255,255,0.2)' if dark_mode else 'rgba(0,0,0,0.1)'};
            background: {'#333' if dark_mode else '#fff'};
            color: {'#fff' if dark_mode else '#2c3e50'};
            font-size: 12px;
            cursor: pointer;
        }}
        
        .timeline-slider {{
            width: 100%;
            margin: 10px 0;
        }}
        
        .timeline-slider input[type="range"] {{
            width: 100%;
            height: 8px;
            -webkit-appearance: none;
            background: {'#333' if dark_mode else '#e0e0e0'};
            border-radius: 4px;
            outline: none;
        }}
        
        .timeline-slider input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(102, 126, 234, 0.5);
        }}
        
        .timeline-labels {{
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: {'#666' if dark_mode else '#999'};
            margin-top: 5px;
        }}
        
        /* Window Size Control */
        .window-control {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid {'rgba(255,255,255,0.1)' if dark_mode else 'rgba(0,0,0,0.05)'};
        }}
        
        .window-control label {{
            font-size: 12px;
            color: {'#888' if dark_mode else '#7f8c8d'};
        }}
        
        .window-control input[type="range"] {{
            flex: 1;
            height: 4px;
            -webkit-appearance: none;
            background: {'#333' if dark_mode else '#e0e0e0'};
            border-radius: 2px;
        }}
        
        .window-control input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 14px;
            height: 14px;
            background: #667eea;
            border-radius: 50%;
            cursor: pointer;
        }}
        
        .window-value {{
            font-size: 12px;
            font-weight: 600;
            color: {'#fff' if dark_mode else '#2c3e50'};
            min-width: 60px;
            text-align: right;
        }}
        
        /* Legend */
        .legend {{
            position: fixed;
            bottom: 200px;
            left: 20px;
            z-index: 1000;
            background: {'rgba(26, 26, 46, 0.95)' if dark_mode else 'rgba(255, 255, 255, 0.98)'};
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }}
        
        .legend h4 {{
            font-size: 12px;
            font-weight: 600;
            color: {'#a0a0a0' if dark_mode else '#7f8c8d'};
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 8px 0;
            font-size: 12px;
            color: {'#ccc' if dark_mode else '#555'};
        }}
        
        .legend-marker {{
            width: 14px;
            height: 14px;
            border-radius: 50%;
        }}
        
        .legend-line {{
            width: 25px;
            height: 3px;
            border-radius: 2px;
        }}
        
        /* Filter Panel */
        .filter-panel {{
            position: fixed;
            top: 140px;
            left: 20px;
            z-index: 1000;
            background: {'rgba(26, 26, 46, 0.95)' if dark_mode else 'rgba(255, 255, 255, 0.98)'};
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
        }}
        
        .filter-panel h4 {{
            font-size: 12px;
            font-weight: 600;
            color: {'#a0a0a0' if dark_mode else '#7f8c8d'};
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .filter-option {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 8px 0;
            font-size: 13px;
            color: {'#ccc' if dark_mode else '#555'};
            cursor: pointer;
        }}
        
        .filter-option input {{
            cursor: pointer;
        }}
        
        /* Popup Styles */
        .leaflet-popup-content-wrapper {{
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        }}
        
        .leaflet-popup-content {{
            margin: 0;
            min-width: 300px;
        }}
        
        .call-popup {{
            font-family: 'Inter', sans-serif;
        }}
        
        .call-popup-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            margin: -1px;
            border-radius: 12px 12px 0 0;
        }}
        
        .call-popup-header h3 {{
            margin: 0 0 5px 0;
            font-size: 16px;
            font-weight: 600;
        }}
        
        .call-popup-header small {{
            opacity: 0.8;
            font-size: 11px;
        }}
        
        .call-popup-body {{
            padding: 15px;
        }}
        
        .call-popup-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .call-popup-row:last-child {{
            border-bottom: none;
        }}
        
        .call-popup-label {{
            color: #7f8c8d;
            font-size: 12px;
        }}
        
        .call-popup-value {{
            font-weight: 500;
            font-size: 13px;
            color: #2c3e50;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        .status-badge.answered {{
            background: #d4edda;
            color: #155724;
        }}
        
        .status-badge.missed {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        .quality-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}
        
        .quality-badge.good {{
            background: #d4edda;
            color: #155724;
        }}
        
        .quality-badge.fair {{
            background: #fff3cd;
            color: #856404;
        }}
        
        .quality-badge.poor {{
            background: #f8d7da;
            color: #721c24;
        }}
        
        /* Call parties styling */
        .call-party {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
        }}
        
        .call-party.caller {{
            border-left: 4px solid #3498db;
        }}
        
        .call-party.called {{
            border-left: 4px solid #2ecc71;
        }}
        
        .call-party-label {{
            font-size: 11px;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }}
        
        .call-party-number {{
            font-size: 14px;
            font-weight: 600;
            color: #2c3e50;
        }}
        
        .call-party-location {{
            font-size: 12px;
            color: #7f8c8d;
            margin-top: 3px;
        }}
        
        /* Animation for active calls */
        @keyframes pulse {{
            0% {{ transform: scale(1); opacity: 1; }}
            50% {{ transform: scale(1.2); opacity: 0.7; }}
            100% {{ transform: scale(1); opacity: 1; }}
        }}
        
        .pulse-marker {{
            animation: pulse 1.5s ease-in-out infinite;
        }}
        
        /* Loading indicator */
        .loading {{
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 2000;
            background: {'rgba(26, 26, 46, 0.95)' if dark_mode else 'rgba(255, 255, 255, 0.98)'};
            padding: 30px 50px;
            border-radius: 16px;
            text-align: center;
            display: none;
        }}
        
        .loading.show {{
            display: block;
        }}
        
        .loading-spinner {{
            width: 40px;
            height: 40px;
            border: 4px solid {'#333' if dark_mode else '#e0e0e0'};
            border-top-color: #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        /* Progress bar for large datasets */
        .progress-bar {{
            width: 100%;
            height: 4px;
            background: {'#333' if dark_mode else '#e0e0e0'};
            border-radius: 2px;
            overflow: hidden;
            margin-top: 10px;
        }}
        
        .progress-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            width: 0%;
            transition: width 0.3s ease;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    
    <!-- Header -->
    <div class="header-panel">
        <h1>
            <i class="fas fa-phone-alt"></i>
            CDR Call Timeline Map
        </h1>
        <span class="badge" id="total-calls-badge">{total_calls} Total Calls</span>
    </div>
    
    <!-- Day Navigation Panel -->
    <div class="day-nav-panel" id="day-nav-panel" style="{'display: flex;' if enable_day_navigation else 'display: none;'}">
        <button class="day-nav-btn" id="btn-prev-day" title="Previous Day">
            <i class="fas fa-chevron-left"></i>
        </button>
        
        <select class="day-selector" id="day-selector">
            <!-- Options will be populated by JavaScript -->
        </select>
        
        <button class="day-nav-btn" id="btn-next-day" title="Next Day">
            <i class="fas fa-chevron-right"></i>
        </button>
        
        <div class="view-mode-toggle">
            <button class="view-mode-btn active" id="btn-view-day" title="View Single Day">
                Day
            </button>
            <button class="view-mode-btn" id="btn-view-all" title="View All Days">
                All
            </button>
        </div>
        
        <span class="day-call-count" id="day-call-count">0 calls</span>
    </div>
    
    <!-- Stats Panel -->
    <div class="stats-panel">
        <h3><i class="fas fa-chart-bar"></i> Current View Statistics</h3>
        <div class="stat-item">
            <span class="stat-label"><i class="fas fa-phone"></i> Visible Calls</span>
            <span class="stat-value info" id="stat-visible">0</span>
        </div>
        <div class="stat-item">
            <span class="stat-label"><i class="fas fa-check-circle"></i> Answered</span>
            <span class="stat-value success" id="stat-answered">0</span>
        </div>
        <div class="stat-item">
            <span class="stat-label"><i class="fas fa-times-circle"></i> Missed</span>
            <span class="stat-value danger" id="stat-missed">0</span>
        </div>
        <div class="stat-item">
            <span class="stat-label"><i class="fas fa-clock"></i> Avg Duration</span>
            <span class="stat-value" id="stat-duration">0s</span>
        </div>
        <div class="stat-item">
            <span class="stat-label"><i class="fas fa-signal"></i> Avg Quality</span>
            <span class="stat-value" id="stat-quality">N/A</span>
        </div>
        
        <div class="day-summary" id="day-summary">
            <h4><i class="fas fa-calendar-day"></i> Day Summary</h4>
            <div class="stat-item">
                <span class="stat-label">Total Calls Today</span>
                <span class="stat-value info" id="stat-day-total">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Peak Hour</span>
                <span class="stat-value" id="stat-peak-hour">N/A</span>
            </div>
        </div>
    </div>
    
    <!-- Filter Panel -->
    <div class="filter-panel">
        <h4><i class="fas fa-filter"></i> Filters</h4>
        <label class="filter-option">
            <input type="checkbox" id="filter-answered" checked>
            <span>Show Answered</span>
        </label>
        <label class="filter-option">
            <input type="checkbox" id="filter-missed" checked>
            <span>Show Missed</span>
        </label>
        <label class="filter-option">
            <input type="checkbox" id="filter-connections" checked>
            <span>Show Connections</span>
        </label>
        <label class="filter-option">
            <input type="checkbox" id="filter-animate">
            <span>Animate Markers</span>
        </label>
    </div>
    
    <!-- Legend -->
    <div class="legend">
        <h4><i class="fas fa-info-circle"></i> Legend</h4>
        <div class="legend-item">
            <div class="legend-marker" style="background: #3498db;"></div>
            <span>Caller (Answered)</span>
        </div>
        <div class="legend-item">
            <div class="legend-marker" style="background: #e74c3c;"></div>
            <span>Caller (Missed)</span>
        </div>
        <div class="legend-item">
            <div class="legend-marker" style="background: #2ecc71;"></div>
            <span>Called (Answered)</span>
        </div>
        <div class="legend-item">
            <div class="legend-marker" style="background: #f39c12;"></div>
            <span>Called (Missed)</span>
        </div>
        <div class="legend-item">
            <div class="legend-line" style="background: linear-gradient(90deg, #9b59b6, #3498db);"></div>
            <span>Call Connection</span>
        </div>
    </div>
    
    <!-- Timeline Control -->
    <div class="timeline-control">
        <div class="timeline-header">
            <div>
                <div class="current-time" id="current-time">--:--:--</div>
                <div class="time-range" id="time-range">Loading...</div>
            </div>
            <div class="playback-controls">
                <button class="control-btn" id="btn-start" title="Go to start">
                    <i class="fas fa-fast-backward"></i>
                </button>
                <button class="control-btn" id="btn-backward" title="Step backward">
                    <i class="fas fa-step-backward"></i>
                </button>
                <button class="control-btn active" id="btn-play" title="Play/Pause">
                    <i class="fas fa-play"></i>
                </button>
                <button class="control-btn" id="btn-forward" title="Step forward">
                    <i class="fas fa-step-forward"></i>
                </button>
                <button class="control-btn" id="btn-end" title="Go to end">
                    <i class="fas fa-fast-forward"></i>
                </button>
                
                <div class="speed-control">
                    <label>Speed:</label>
                    <select id="speed-select">
                        <option value="0.25">0.25x</option>
                        <option value="0.5">0.5x</option>
                        <option value="1" selected>1x</option>
                        <option value="2">2x</option>
                        <option value="5">5x</option>
                        <option value="10">10x</option>
                        <option value="30">30x</option>
                        <option value="60">60x</option>
                    </select>
                </div>
            </div>
        </div>
        
        <div class="timeline-slider">
            <input type="range" id="timeline-slider" min="{min_time}" max="{max_time}" value="{min_time}">
        </div>
        
        <div class="timeline-labels">
            <span id="label-start">Start</span>
            <span id="label-end">End</span>
        </div>
        
        <div class="window-control">
            <label><i class="fas fa-clock"></i> Time Window:</label>
            <input type="range" id="window-slider" min="5" max="360" value="{time_window_minutes}">
            <span class="window-value" id="window-value">{time_window_minutes} min</span>
        </div>
    </div>
    
    <!-- Loading Indicator -->
    <div class="loading" id="loading">
        <div class="loading-spinner"></div>
        <div style="color: {'#fff' if dark_mode else '#2c3e50'};">Loading calls...</div>
        <div class="progress-bar">
            <div class="progress-bar-fill" id="progress-fill"></div>
        </div>
    </div>
    
    <!-- Leaflet JS -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    
    <script>
        // ============================================================
        // CALL DATA - ALL CALLS (UNLIMITED)
        // ============================================================
        const allCallData = {calls_json};
        const availableDates = {dates_json};
        
        // ============================================================
        // CONFIGURATION
        // ============================================================
        const config = {{
            center: [{center[0]}, {center[1]}],
            zoom: {zoom_start},
            globalMinTime: {min_time},
            globalMaxTime: {max_time},
            minTime: {min_time},
            maxTime: {max_time},
            timeWindowMs: {time_window_minutes} * 60 * 1000,
            isPlaying: false,
            playbackSpeed: 1,
            stepMs: 60000, // 1 minute steps
            animateMarkers: false,
            currentDayIndex: 0,
            viewMode: 'day', // 'day' or 'all'
            enableDayNav: {str(enable_day_navigation).lower()}
        }};
        
        // Current filtered data based on day selection
        let currentCallData = [];
        
        // ============================================================
        // MAP INITIALIZATION
        // ============================================================
        const map = L.map('map').setView(config.center, config.zoom);
        
        L.tileLayer('{tile_url}', {{
            attribution: '{tile_attr}',
            maxZoom: 19
        }}).addTo(map);
        
        // Layers for markers and lines
        const markersLayer = L.layerGroup().addTo(map);
        const linesLayer = L.layerGroup().addTo(map);
        
        // ============================================================
        // DAY NAVIGATION FUNCTIONS
        // ============================================================
        function populateDaySelector() {{
            const selector = document.getElementById('day-selector');
            selector.innerHTML = '';
            
            availableDates.forEach((date, index) => {{
                const option = document.createElement('option');
                option.value = index;
                const callCount = allCallData.filter(c => c.date === date).length;
                option.textContent = `${{formatDateDisplay(date)}} (${{callCount}} calls)`;
                selector.appendChild(option);
            }});
            
            if (availableDates.length > 0) {{
                selector.value = 0;
                config.currentDayIndex = 0;
            }}
        }}
        
        function formatDateDisplay(dateStr) {{
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-GB', {{
                weekday: 'short',
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            }});
        }}
        
        function filterCallsByDay(dayIndex) {{
            if (config.viewMode === 'all') {{
                currentCallData = allCallData;
            }} else {{
                const selectedDate = availableDates[dayIndex];
                currentCallData = allCallData.filter(c => c.date === selectedDate);
            }}
            
            updateTimelineForCurrentData();
            updateDayStats();
        }}
        
        function updateTimelineForCurrentData() {{
            if (currentCallData.length === 0) {{
                config.minTime = config.globalMinTime;
                config.maxTime = config.globalMaxTime;
            }} else {{
                const timestamps = currentCallData.map(c => c.timestamp_ms);
                config.minTime = Math.min(...timestamps);
                config.maxTime = Math.max(...timestamps);
            }}
            
            const slider = document.getElementById('timeline-slider');
            slider.min = config.minTime;
            slider.max = config.maxTime;
            slider.value = config.minTime;
            
            document.getElementById('label-start').textContent = formatTime(config.minTime);
            document.getElementById('label-end').textContent = formatTime(config.maxTime);
            
            updateTimeline(config.minTime);
        }}
        
        function updateDayStats() {{
            const dayCallCount = currentCallData.length;
            document.getElementById('day-call-count').textContent = `${{dayCallCount}} calls`;
            document.getElementById('stat-day-total').textContent = dayCallCount;
            
            // Calculate peak hour
            if (dayCallCount > 0) {{
                const hourCounts = {{}};
                currentCallData.forEach(c => {{
                    const hour = new Date(c.timestamp).getHours();
                    hourCounts[hour] = (hourCounts[hour] || 0) + 1;
                }});
                
                let peakHour = 0;
                let peakCount = 0;
                Object.entries(hourCounts).forEach(([hour, count]) => {{
                    if (count > peakCount) {{
                        peakCount = count;
                        peakHour = parseInt(hour);
                    }}
                }});
                
                document.getElementById('stat-peak-hour').textContent = 
                    `${{peakHour.toString().padStart(2, '0')}}:00 (${{peakCount}} calls)`;
            }} else {{
                document.getElementById('stat-peak-hour').textContent = 'N/A';
            }}
        }}
        
        function goToPreviousDay() {{
            if (config.currentDayIndex > 0) {{
                config.currentDayIndex--;
                document.getElementById('day-selector').value = config.currentDayIndex;
                filterCallsByDay(config.currentDayIndex);
                updateNavButtons();
            }}
        }}
        
        function goToNextDay() {{
            if (config.currentDayIndex < availableDates.length - 1) {{
                config.currentDayIndex++;
                document.getElementById('day-selector').value = config.currentDayIndex;
                filterCallsByDay(config.currentDayIndex);
                updateNavButtons();
            }}
        }}
        
        function updateNavButtons() {{
            document.getElementById('btn-prev-day').disabled = config.currentDayIndex <= 0;
            document.getElementById('btn-next-day').disabled = config.currentDayIndex >= availableDates.length - 1;
        }}
        
        function setViewMode(mode) {{
            config.viewMode = mode;
            
            document.getElementById('btn-view-day').classList.toggle('active', mode === 'day');
            document.getElementById('btn-view-all').classList.toggle('active', mode === 'all');
            
            // Disable/enable day navigation when in "all" mode
            document.getElementById('btn-prev-day').disabled = mode === 'all';
            document.getElementById('btn-next-day').disabled = mode === 'all';
            document.getElementById('day-selector').disabled = mode === 'all';
            
            if (mode === 'all') {{
                currentCallData = allCallData;
                updateTimelineForCurrentData();
                updateDayStats();
            }} else {{
                filterCallsByDay(config.currentDayIndex);
                updateNavButtons();
            }}
        }}
        
        // ============================================================
        // HELPER FUNCTIONS
        // ============================================================
        function formatTime(ms) {{
            const date = new Date(ms);
            return date.toLocaleString('en-GB', {{
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            }});
        }}
        
        function formatDuration(seconds) {{
            if (!seconds) return '0s';
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            const hours = Math.floor(mins / 60);
            const remMins = mins % 60;
            
            if (hours > 0) return `${{hours}}h ${{remMins}}m ${{secs}}s`;
            if (mins > 0) return `${{mins}}m ${{secs}}s`;
            return `${{secs}}s`;
        }}
        
        function getQualityClass(mos) {{
            if (!mos) return '';
            if (mos >= 4.0) return 'good';
            if (mos >= 3.5) return 'fair';
            return 'poor';
        }}
        
        function getQualityLabel(mos) {{
            if (!mos) return 'N/A';
            if (mos >= 4.0) return 'Good';
            if (mos >= 3.5) return 'Fair';
            return 'Poor';
        }}
        
        // ============================================================
        // MARKER CREATION
        // ============================================================
        function createCallPopup(call) {{
            const statusClass = call.answered ? 'answered' : 'missed';
            const statusText = call.answered ? 'Answered' : 'Missed';
            const qualityClass = getQualityClass(call.mos);
            const qualityText = call.mos ? `${{call.mos.toFixed(2)}} (${{getQualityLabel(call.mos)}})` : 'N/A';
            
            return `
                <div class="call-popup">
                    <div class="call-popup-header">
                        <h3><i class="fas fa-phone-alt"></i> Call Details</h3>
                        <small>ID: ${{call.id}}</small>
                    </div>
                    <div class="call-popup-body">
                        <div class="call-popup-row">
                            <span class="call-popup-label">Time</span>
                            <span class="call-popup-value">${{new Date(call.timestamp).toLocaleString()}}</span>
                        </div>
                        <div class="call-popup-row">
                            <span class="call-popup-label">Status</span>
                            <span class="status-badge ${{statusClass}}">${{statusText}}</span>
                        </div>
                        <div class="call-popup-row">
                            <span class="call-popup-label">Duration</span>
                            <span class="call-popup-value">${{call.duration_str}}</span>
                        </div>
                        <div class="call-popup-row">
                            <span class="call-popup-label">Type</span>
                            <span class="call-popup-value">${{call.call_type}}</span>
                        </div>
                        
                        <div class="call-party caller">
                            <div class="call-party-label"><i class="fas fa-user"></i> Caller</div>
                            <div class="call-party-number">${{call.caller}}</div>
                            <div class="call-party-location"><i class="fas fa-map-marker-alt"></i> ${{call.caller_location}}</div>
                        </div>
                        
                        <div class="call-party called">
                            <div class="call-party-label"><i class="fas fa-user-check"></i> Called</div>
                            <div class="call-party-number">${{call.called}}</div>
                            <div class="call-party-location"><i class="fas fa-map-marker-alt"></i> ${{call.called_location}}</div>
                        </div>
                        
                        ${{call.mos ? `
                        <div class="call-popup-row">
                            <span class="call-popup-label">Quality (MOS)</span>
                            <span class="quality-badge ${{qualityClass}}">${{qualityText}}</span>
                        </div>
                        ` : ''}}
                        
                        ${{call.jitter ? `
                        <div class="call-popup-row">
                            <span class="call-popup-label">Jitter</span>
                            <span class="call-popup-value">${{call.jitter}}ms</span>
                        </div>
                        ` : ''}}
                        
                        ${{call.latency ? `
                        <div class="call-popup-row">
                            <span class="call-popup-label">Latency</span>
                            <span class="call-popup-value">${{call.latency}}ms</span>
                        </div>
                        ` : ''}}
                    </div>
                </div>
            `;
        }}
        
        function createMarker(lat, lon, color, size, popup, animate) {{
            const markerHtml = `
                <div style="
                    width: ${{size}}px;
                    height: ${{size}}px;
                    background: ${{color}};
                    border-radius: 50%;
                    border: 3px solid white;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                    ${{animate ? 'animation: pulse 1.5s ease-in-out infinite;' : ''}}
                "></div>
            `;
            
            const icon = L.divIcon({{
                html: markerHtml,
                className: '',
                iconSize: [size, size],
                iconAnchor: [size/2, size/2]
            }});
            
            return L.marker([lat, lon], {{ icon: icon }}).bindPopup(popup, {{ maxWidth: 400 }});
        }}
        
        function createConnectionLine(call) {{
            if (!call.caller_lat || !call.called_lat) return null;
            
            const color = call.answered ? '#9b59b6' : '#e74c3c';
            
            // Create curved line using bezier approximation
            const latlngs = [
                [call.caller_lat, call.caller_lon],
                [call.called_lat, call.called_lon]
            ];
            
            // Add midpoint with offset for curve effect
            const midLat = (call.caller_lat + call.called_lat) / 2;
            const midLon = (call.caller_lon + call.called_lon) / 2;
            const offset = 0.5; // Curve offset
            
            const curvedLatlngs = [
                [call.caller_lat, call.caller_lon],
                [midLat + offset, midLon + offset * 0.5],
                [call.called_lat, call.called_lon]
            ];
            
            return L.polyline(curvedLatlngs, {{
                color: color,
                weight: 3,
                opacity: 0.7,
                dashArray: call.answered ? null : '10, 10',
                smoothFactor: 1
            }}).bindPopup(createCallPopup(call), {{ maxWidth: 400 }});
        }}
        
        // ============================================================
        // RENDERING FUNCTIONS
        // ============================================================
        function getVisibleCalls(currentTime, windowMs) {{
            const showAnswered = document.getElementById('filter-answered').checked;
            const showMissed = document.getElementById('filter-missed').checked;
            
            return currentCallData.filter(call => {{
                // Time filter - call is visible if current time is within call's active period
                const callStart = call.timestamp_ms;
                const callEnd = call.end_time_ms || (callStart + (call.duration * 1000) + 60000); // At least 1 minute visibility
                
                // Show call if current time window overlaps with call duration
                const windowStart = currentTime;
                const windowEnd = currentTime + windowMs;
                
                const isInWindow = (callStart <= windowEnd && callEnd >= windowStart);
                
                if (!isInWindow) return false;
                
                // Status filter
                if (call.answered && !showAnswered) return false;
                if (!call.answered && !showMissed) return false;
                
                return true;
            }});
        }}
        
        function renderCalls(currentTime) {{
            // Clear existing markers and lines
            markersLayer.clearLayers();
            linesLayer.clearLayers();
            
            const visibleCalls = getVisibleCalls(currentTime, config.timeWindowMs);
            const showConnections = document.getElementById('filter-connections').checked;
            const animate = document.getElementById('filter-animate').checked;
            
            // Batch render for performance with large datasets
            const batchSize = 100;
            let processed = 0;
            
            function renderBatch() {{
                const end = Math.min(processed + batchSize, visibleCalls.length);
                
                for (let i = processed; i < end; i++) {{
                    const call = visibleCalls[i];
                    const popup = createCallPopup(call);
                    
                    // Add caller marker
                    if (call.caller_lat && call.caller_lon) {{
                        const callerColor = call.answered ? '#3498db' : '#e74c3c';
                        const callerMarker = createMarker(
                            call.caller_lat, 
                            call.caller_lon, 
                            callerColor, 
                            16, 
                            popup,
                            animate
                        );
                        markersLayer.addLayer(callerMarker);
                    }}
                    
                    // Add called marker
                    if (call.called_lat && call.called_lon) {{
                        const calledColor = call.answered ? '#2ecc71' : '#f39c12';
                        const calledMarker = createMarker(
                            call.called_lat, 
                            call.called_lon, 
                            calledColor, 
                            12, 
                            popup,
                            animate
                        );
                        markersLayer.addLayer(calledMarker);
                    }}
                    
                    // Add connection line
                    if (showConnections) {{
                        const line = createConnectionLine(call);
                        if (line) {{
                            linesLayer.addLayer(line);
                        }}
                    }}
                }}
                
                processed = end;
                
                if (processed < visibleCalls.length) {{
                    requestAnimationFrame(renderBatch);
                }}
            }}
            
            renderBatch();
            
            // Update statistics
            updateStats(visibleCalls);
        }}
        
        function updateStats(visibleCalls) {{
            const answered = visibleCalls.filter(c => c.answered).length;
            const missed = visibleCalls.length - answered;
            const totalDuration = visibleCalls.reduce((sum, c) => sum + (c.duration || 0), 0);
            const avgDuration = visibleCalls.length > 0 ? totalDuration / visibleCalls.length : 0;
            
            const mosValues = visibleCalls.filter(c => c.mos).map(c => c.mos);
            const avgMos = mosValues.length > 0 
                ? (mosValues.reduce((a, b) => a + b, 0) / mosValues.length).toFixed(2)
                : 'N/A';
            
            document.getElementById('stat-visible').textContent = visibleCalls.length;
            document.getElementById('stat-answered').textContent = answered;
            document.getElementById('stat-missed').textContent = missed;
            document.getElementById('stat-duration').textContent = formatDuration(Math.round(avgDuration));
            
            const qualityEl = document.getElementById('stat-quality');
            qualityEl.textContent = avgMos;
            qualityEl.className = 'stat-value';
            if (avgMos !== 'N/A') {{
                if (parseFloat(avgMos) >= 4.0) qualityEl.classList.add('success');
                else if (parseFloat(avgMos) >= 3.5) qualityEl.classList.add('warning');
                else qualityEl.classList.add('danger');
            }}
        }}
        
        // ============================================================
        // TIMELINE CONTROLS
        // ============================================================
        const slider = document.getElementById('timeline-slider');
        const currentTimeDisplay = document.getElementById('current-time');
        const timeRangeDisplay = document.getElementById('time-range');
        const windowSlider = document.getElementById('window-slider');
        const windowValue = document.getElementById('window-value');
        
        let playInterval = null;
        
        function updateTimeline(time) {{
            slider.value = time;
            currentTimeDisplay.textContent = formatTime(time);
            
            const startDate = new Date(config.minTime);
            const endDate = new Date(config.maxTime);
            
            if (config.viewMode === 'day') {{
                timeRangeDisplay.textContent = startDate.toLocaleDateString('en-GB', {{
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                }});
            }} else {{
                timeRangeDisplay.textContent = `${{startDate.toLocaleDateString()}} - ${{endDate.toLocaleDateString()}}`;
            }}
            
            renderCalls(time);
        }}
        
        // Slider events
        slider.addEventListener('input', function() {{
            updateTimeline(parseInt(this.value));
        }});
        
        // Window slider
        windowSlider.addEventListener('input', function() {{
            const minutes = parseInt(this.value);
            config.timeWindowMs = minutes * 60 * 1000;
            windowValue.textContent = `${{minutes}} min`;
            renderCalls(parseInt(slider.value));
        }});
        
        // Playback controls
        document.getElementById('btn-play').addEventListener('click', function() {{
            config.isPlaying = !config.isPlaying;
            this.innerHTML = config.isPlaying ? '<i class="fas fa-pause"></i>' : '<i class="fas fa-play"></i>';
            
            if (config.isPlaying) {{
                playInterval = setInterval(() => {{
                    let newTime = parseInt(slider.value) + (config.stepMs * config.playbackSpeed);
                    if (newTime > config.maxTime) {{
                        // When reaching end of day, optionally go to next day
                        if (config.viewMode === 'day' && config.currentDayIndex < availableDates.length - 1) {{
                            goToNextDay();
                            newTime = config.minTime;
                        }} else {{
                            newTime = config.minTime;
                        }}
                    }}
                    updateTimeline(newTime);
                }}, 100);
            }} else {{
                clearInterval(playInterval);
            }}
        }});
        
        document.getElementById('btn-start').addEventListener('click', function() {{
            updateTimeline(config.minTime);
        }});
        
        document.getElementById('btn-end').addEventListener('click', function() {{
            updateTimeline(config.maxTime);
        }});
        
        document.getElementById('btn-forward').addEventListener('click', function() {{
            let newTime = parseInt(slider.value) + config.stepMs * 10;
            if (newTime > config.maxTime) newTime = config.maxTime;
            updateTimeline(newTime);
        }});
        
        document.getElementById('btn-backward').addEventListener('click', function() {{
            let newTime = parseInt(slider.value) - config.stepMs * 10;
            if (newTime < config.minTime) newTime = config.minTime;
            updateTimeline(newTime);
        }});
        
        document.getElementById('speed-select').addEventListener('change', function() {{
            config.playbackSpeed = parseFloat(this.value);
        }});
        
        // Day navigation events
        document.getElementById('btn-prev-day').addEventListener('click', goToPreviousDay);
        document.getElementById('btn-next-day').addEventListener('click', goToNextDay);
        
        document.getElementById('day-selector').addEventListener('change', function() {{
            config.currentDayIndex = parseInt(this.value);
            filterCallsByDay(config.currentDayIndex);
            updateNavButtons();
        }});
        
        document.getElementById('btn-view-day').addEventListener('click', function() {{
            setViewMode('day');
        }});
        
        document.getElementById('btn-view-all').addEventListener('click', function() {{
            setViewMode('all');
        }});
        
        // Filter events
        ['filter-answered', 'filter-missed', 'filter-connections', 'filter-animate'].forEach(id => {{
            document.getElementById(id).addEventListener('change', function() {{
                renderCalls(parseInt(slider.value));
            }});
        }});
        
        // ============================================================
        // KEYBOARD SHORTCUTS
        // ============================================================
        document.addEventListener('keydown', function(e) {{
            switch(e.key) {{
                case ' ':
                    e.preventDefault();
                    document.getElementById('btn-play').click();
                    break;
                case 'ArrowRight':
                    if (e.ctrlKey || e.metaKey) {{
                        goToNextDay();
                    }} else {{
                        document.getElementById('btn-forward').click();
                    }}
                    break;
                case 'ArrowLeft':
                    if (e.ctrlKey || e.metaKey) {{
                        goToPreviousDay();
                    }} else {{
                        document.getElementById('btn-backward').click();
                    }}
                    break;
                case 'Home':
                    document.getElementById('btn-start').click();
                    break;
                case 'End':
                    document.getElementById('btn-end').click();
                    break;
                case 'd':
                case 'D':
                    setViewMode('day');
                    break;
                case 'a':
                case 'A':
                    setViewMode('all');
                    break;
            }}
        }});
        
        // ============================================================
        // INITIALIZATION
        // ============================================================
        // Populate day selector
        populateDaySelector();
        
        // Initialize with first day or all calls
        if (config.enableDayNav && availableDates.length > 0) {{
            filterCallsByDay(0);
            updateNavButtons();
        }} else {{
            currentCallData = allCallData;
            updateTimelineForCurrentData();
            updateDayStats();
        }}
        
        // Fit map to show all markers
        if (allCallData.length > 0) {{
            const bounds = [];
            allCallData.forEach(call => {{
                if (call.caller_lat && call.caller_lon) {{
                    bounds.push([call.caller_lat, call.caller_lon]);
                }}
                if (call.called_lat && call.called_lon) {{
                    bounds.push([call.called_lat, call.called_lon]);
                }}
            }});
            if (bounds.length > 0) {{
                map.fitBounds(bounds, {{ padding: [50, 50] }});
            }}
        }}
        
        console.log('Map initialized with', allCallData.length, 'total calls across', availableDates.length, 'days');
        console.log('Keyboard shortcuts: Space=Play/Pause, Arrows=Navigate, Ctrl+Arrows=Change Day, D=Day view, A=All view');
    </script>
</body>
</html>'''
        
        return html
    
    def save_map(
        self,
        html_content: str,
        filename: str = 'call_timeline_map.html',
        output_dir: Optional[str] = None
    ) -> str:
        """
        Save map HTML to file
        
        :param html_content: HTML string
        :param filename: Output filename
        :param output_dir: Output directory
        :return: Path to saved file
        """
        output_dir = output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        if not filename.endswith('.html'):
            filename += '.html'
        
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Map saved: {filepath}")
        return filepath
    
    def create_and_save_timeline_map(
        self,
        filename: str = 'call_timeline_map.html',
        output_dir: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Convenience method to create and save map in one step
        
        :param filename: Output filename
        :param output_dir: Output directory
        :param kwargs: Arguments passed to create_advanced_timeline_map
        :return: Path to saved file or None
        """
        html = self.create_advanced_timeline_map(**kwargs)
        if html:
            return self.save_map(html, filename, output_dir)
        return None