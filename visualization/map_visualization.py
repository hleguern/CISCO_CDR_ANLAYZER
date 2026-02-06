"""
Map visualization module for CDR/CMR data
Uses OpenStreetMap via Folium with timeline functionality
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union
import logging
import re
import os

try:
    import folium
    from folium import plugins
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

from .base_viz import BaseVisualizer

logger = logging.getLogger(__name__)


# Phone country code to approximate coordinates mapping
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
}

# German area codes to city mapping
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
}


class MapVisualizer(BaseVisualizer):
    """Generate interactive map visualizations with timeline"""
    
    def __init__(self, analyzer):
        super().__init__(analyzer)
        self._location_cache = {}
        if not FOLIUM_AVAILABLE:
            logger.warning("Folium not available. Install with: pip install folium")
    
    def _check_folium(self) -> bool:
        """Check if Folium is available"""
        if not FOLIUM_AVAILABLE:
            logger.error("Folium is required for map visualizations. Install with: pip install folium")
            return False
        return True
    
    def _parse_phone_location(self, phone_number: str) -> Optional[Tuple[str, float, float]]:
        """
        Parse phone number to get approximate location
        
        :param phone_number: Phone number string
        :return: Tuple of (location_name, latitude, longitude) or None
        """
        if not phone_number or str(phone_number) in ['', 'nan', '\\', 'None']:
            return None
        
        # Check cache
        if phone_number in self._location_cache:
            return self._location_cache[phone_number]
        
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
                area_code = local_num[:length]
                if area_code in GERMAN_AREA_CODES:
                    city, lat, lon = GERMAN_AREA_CODES[area_code]
                    # Add small random offset to prevent marker stacking
                    lat += np.random.uniform(-0.05, 0.05)
                    lon += np.random.uniform(-0.05, 0.05)
                    result = (city, lat, lon)
                    break
            
            if result is None:
                # Default to Germany center with offset
                result = ('Germany', 51.1657 + np.random.uniform(-1, 1), 
                         10.4515 + np.random.uniform(-1, 1))
        
        # Try country codes
        if result is None:
            for code_len in [3, 2, 1]:
                code = clean_num[:code_len]
                if code in COUNTRY_CODE_COORDS:
                    name, lat, lon = COUNTRY_CODE_COORDS[code]
                    lat += np.random.uniform(-0.5, 0.5)
                    lon += np.random.uniform(-0.5, 0.5)
                    result = (name, lat, lon)
                    break
        
        # Cache result
        self._location_cache[phone_number] = result
        return result
    
    def _get_call_location_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_calls: int = 500
    ) -> pd.DataFrame:
        """
        Extract location data from CDR records
        
        :return: DataFrame with location information
        """
        if self.cdr is None:
            return pd.DataFrame()
        
        df = self.cdr.copy()
        
        # Apply date filters
        if 'dateTimeOrigination_dt' in df.columns:
            if start_date:
                df = df[df['dateTimeOrigination_dt'] >= start_date]
            if end_date:
                df = df[df['dateTimeOrigination_dt'] <= end_date]
        
        # Limit records
        df = df.head(max_calls)
        
        # Parse locations for caller and called
        locations = []
        
        for idx, row in df.iterrows():
            caller_loc = self._parse_phone_location(row.get('callingPartyNumber', ''))
            called_loc = self._parse_phone_location(row.get('finalCalledPartyNumber', ''))
            
            # Skip if no valid locations
            if caller_loc is None and called_loc is None:
                continue
            
            # Get timestamp
            timestamp = row.get('dateTimeOrigination_dt')
            if pd.isna(timestamp):
                try:
                    timestamp = pd.to_datetime(row['dateTimeOrigination'], unit='s')
                except:
                    continue
            
            # Get CMR data if available
            cmr_data = self._get_cmr_for_call(row.get('globalCallID_callId'))
            
            locations.append({
                'call_id': row.get('globalCallID_callId', idx),
                'timestamp': timestamp,
                'caller': row.get('callingPartyNumber', ''),
                'called': row.get('finalCalledPartyNumber', ''),
                'caller_location': caller_loc[0] if caller_loc else 'Unknown',
                'caller_lat': caller_loc[1] if caller_loc else None,
                'caller_lon': caller_loc[2] if caller_loc else None,
                'called_location': called_loc[0] if called_loc else 'Unknown',
                'called_lat': called_loc[1] if called_loc else None,
                'called_lon': called_loc[2] if called_loc else None,
                'duration': row.get('duration', 0),
                'answered': row.get('answered', False),
                'call_type': row.get('call_type', 'unknown'),
                'orig_device': row.get('origDeviceName', ''),
                'dest_device': row.get('destDeviceName', ''),
                # CMR Quality data
                'origjitter': cmr_data.get('origjitter') if cmr_data else None,
                'destjitter': cmr_data.get('destjitter') if cmr_data else None,
                'origlatency': cmr_data.get('origlatency') if cmr_data else None,
                'destlatency': cmr_data.get('destlatency') if cmr_data else None,
                'orignumberPacketsLost': cmr_data.get('orignumberPacketsLost') if cmr_data else None,
                'destnumberPacketsLost': cmr_data.get('destnumberPacketsLost') if cmr_data else None,
                'avg_mos': cmr_data.get('avg_mos') if cmr_data else None,
            })
        
        return pd.DataFrame(locations)
    
    def _get_cmr_for_call(self, call_id) -> Optional[Dict]:
        """Get CMR data for a specific call ID"""
        if self.cmr is None or call_id is None:
            return None
        
        cmr_match = self.cmr[self.cmr['globalCallID_callId'] == call_id]
        if not cmr_match.empty:
            return cmr_match.iloc[0].to_dict()
        return None
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration as string"""
        if pd.isna(seconds):
            return "0s"
        seconds = int(seconds)
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}h {mins}m {secs}s"
        elif mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"
    
    def _get_call_details_html(self, call_data: Dict[str, Any]) -> str:
        """
        Generate HTML popup content for call details
        
        :param call_data: Call record data
        :return: HTML string
        """
        status_color = '#27ae60' if call_data.get('answered') else '#e74c3c'
        status_text = 'Answered' if call_data.get('answered') else 'Missed'
        duration_str = self._format_duration(call_data.get('duration', 0))
        
        # Format timestamp
        ts = call_data.get('timestamp')
        if isinstance(ts, pd.Timestamp):
            time_str = ts.strftime('%Y-%m-%d %H:%M:%S')
        else:
            time_str = str(ts)
        
        html = f"""
        <div style="min-width: 320px; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        color: white; padding: 12px; margin: -12px -12px 12px -12px; border-radius: 4px 4px 0 0;">
                <h4 style="margin: 0; font-size: 16px;">📞 Call Details</h4>
                <small>ID: {call_data.get('call_id', 'N/A')}</small>
            </div>
            
            <div style="margin-bottom: 12px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 6px 8px; background: #f8f9fa; font-weight: 600; width: 35%; border-bottom: 1px solid #eee;">⏰ Time</td>
                        <td style="padding: 6px 8px; border-bottom: 1px solid #eee;">{time_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 8px; background: #f8f9fa; font-weight: 600; border-bottom: 1px solid #eee;">📊 Status</td>
                        <td style="padding: 6px 8px; border-bottom: 1px solid #eee;">
                            <span style="background: {status_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px;">{status_text}</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 8px; background: #f8f9fa; font-weight: 600; border-bottom: 1px solid #eee;">⏱️ Duration</td>
                        <td style="padding: 6px 8px; border-bottom: 1px solid #eee;">{duration_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 8px; background: #f8f9fa; font-weight: 600; border-bottom: 1px solid #eee;">🏷️ Type</td>
                        <td style="padding: 6px 8px; border-bottom: 1px solid #eee;">{call_data.get('call_type', 'N/A')}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background: #e3f2fd; padding: 8px; border-radius: 4px; margin-bottom: 12px;">
                <div style="font-weight: 600; color: #1565c0; margin-bottom: 6px;">📱 Caller</div>
                <div style="font-size: 14px; font-weight: 500;">{call_data.get('caller', 'N/A')}</div>
                <div style="color: #666; font-size: 12px;">📍 {call_data.get('caller_location', 'Unknown')}</div>
                <div style="color: #888; font-size: 11px; margin-top: 4px;">Device: {call_data.get('orig_device', 'N/A')}</div>
            </div>
            
            <div style="background: #e8f5e9; padding: 8px; border-radius: 4px; margin-bottom: 12px;">
                <div style="font-weight: 600; color: #2e7d32; margin-bottom: 6px;">📞 Called</div>
                <div style="font-size: 14px; font-weight: 500;">{call_data.get('called', 'N/A')}</div>
                <div style="color: #666; font-size: 12px;">📍 {call_data.get('called_location', 'Unknown')}</div>
                <div style="color: #888; font-size: 11px; margin-top: 4px;">Device: {call_data.get('dest_device', 'N/A')}</div>
            </div>
        """
        
        # Add quality metrics if available
        has_quality = any([
            call_data.get('origjitter'),
            call_data.get('origlatency'),
            call_data.get('orignumberPacketsLost'),
            call_data.get('avg_mos')
        ])
        
        if has_quality:
            # Determine quality color based on MOS
            mos = call_data.get('avg_mos')
            if mos:
                if mos >= 4.0:
                    quality_color = '#27ae60'
                    quality_label = 'Good'
                elif mos >= 3.5:
                    quality_color = '#f39c12'
                    quality_label = 'Fair'
                else:
                    quality_color = '#e74c3c'
                    quality_label = 'Poor'
            else:
                quality_color = '#95a5a6'
                quality_label = 'N/A'
            
            html += f"""
            <div style="background: #fff3e0; padding: 8px; border-radius: 4px;">
                <div style="font-weight: 600; color: #e65100; margin-bottom: 8px;">📊 Quality Metrics</div>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <tr>
                        <td style="padding: 4px; border-bottom: 1px solid #ffe0b2;">Jitter</td>
                        <td style="padding: 4px; border-bottom: 1px solid #ffe0b2;">
                            Orig: {call_data.get('origjitter', 'N/A')}ms | Dest: {call_data.get('destjitter', 'N/A')}ms
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 4px; border-bottom: 1px solid #ffe0b2;">Latency</td>
                        <td style="padding: 4px; border-bottom: 1px solid #ffe0b2;">
                            Orig: {call_data.get('origlatency', 'N/A')}ms | Dest: {call_data.get('destlatency', 'N/A')}ms
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 4px; border-bottom: 1px solid #ffe0b2;">Packets Lost</td>
                        <td style="padding: 4px; border-bottom: 1px solid #ffe0b2;">
                            Orig: {call_data.get('orignumberPacketsLost', 'N/A')} | Dest: {call_data.get('destnumberPacketsLost', 'N/A')}
                        </td>
                    </tr>
            """
            
            if mos:
                html += f"""
                    <tr>
                        <td style="padding: 4px;">MOS Score</td>
                        <td style="padding: 4px;">
                            <span style="background: {quality_color}; color: white; padding: 2px 8px; border-radius: 12px; font-weight: bold;">
                                {mos:.2f} ({quality_label})
                            </span>
                        </td>
                    </tr>
                """
            
            html += """
                </table>
            </div>
            """
        
        html += "</div>"
        return html
    
    def create_call_timeline_map(
        self,
        max_calls: int = 500,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        center: Optional[Tuple[float, float]] = None,
        zoom_start: int = 6,
        show_connections: bool = True
    ) -> Optional['folium.Map']:
        """
        Create an interactive map with call timeline
        
        :param max_calls: Maximum number of calls to display
        :param start_date: Optional start date filter
        :param end_date: Optional end date filter
        :param center: Map center coordinates (lat, lon)
        :param zoom_start: Initial zoom level
        :param show_connections: Show lines connecting caller to called
        :return: Folium Map object
        """
        if not self._check_folium() or not self._check_data_loaded():
            return None
        
        # Get location data
        loc_df = self._get_call_location_data(start_date, end_date, max_calls)
        
        if loc_df.empty:
            logger.warning("No location data available for mapping")
            return None
        
        logger.info(f"Creating map with {len(loc_df)} calls")
        
        # Determine map center
        if center is None:
            valid_lats = pd.concat([
                loc_df['caller_lat'].dropna(),
                loc_df['called_lat'].dropna()
            ])
            valid_lons = pd.concat([
                loc_df['caller_lon'].dropna(),
                loc_df['called_lon'].dropna()
            ])
            
            if len(valid_lats) > 0 and len(valid_lons) > 0:
                center = (valid_lats.mean(), valid_lons.mean())
            else:
                center = (51.1657, 10.4515)  # Default to Germany
        
        # Create base map
        m = folium.Map(
            location=center,
            zoom_start=zoom_start,
            tiles='OpenStreetMap'
        )
        
        # Add alternative tile layers
        folium.TileLayer('cartodbpositron', name='Light Mode').add_to(m)
        folium.TileLayer('cartodbdark_matter', name='Dark Mode').add_to(m)
        
        # Sort by timestamp for timeline
        loc_df = loc_df.sort_values('timestamp')
        
        # Create features for TimestampedGeoJson
        features = []
        
        for _, row in loc_df.iterrows():
            call_data = row.to_dict()
            popup_html = self._get_call_details_html(call_data)
            
            # Format timestamp for timeline
            timestamp = row['timestamp']
            if isinstance(timestamp, pd.Timestamp):
                time_str = timestamp.strftime('%Y-%m-%dT%H:%M:%S')
            else:
                time_str = str(timestamp)
            
            # Determine colors based on answered status
            caller_color = '#3498db' if row['answered'] else '#e74c3c'
            called_color = '#2ecc71' if row['answered'] else '#f39c12'
            line_color = '#9b59b6' if row['answered'] else '#e74c3c'
            
            # Create feature for caller location
            if pd.notna(row['caller_lat']) and pd.notna(row['caller_lon']):
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [float(row['caller_lon']), float(row['caller_lat'])]
                    },
                    'properties': {
                        'time': time_str,
                        'popup': popup_html,
                        'icon': 'circle',
                        'iconstyle': {
                            'color': caller_color,
                            'fillColor': caller_color,
                            'fillOpacity': 0.8,
                            'radius': 10
                        },
                        'style': {'weight': 0}
                    }
                })
            
            # Create feature for called location
            if pd.notna(row['called_lat']) and pd.notna(row['called_lon']):
                features.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [float(row['called_lon']), float(row['called_lat'])]
                    },
                    'properties': {
                        'time': time_str,
                        'popup': popup_html,
                        'icon': 'circle',
                        'iconstyle': {
                            'color': called_color,
                            'fillColor': called_color,
                            'fillOpacity': 0.8,
                            'radius': 7
                        },
                        'style': {'weight': 0}
                    }
                })
                
                # Add line connecting caller to called
                if show_connections and pd.notna(row['caller_lat']):
                    features.append({
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': [
                                [float(row['caller_lon']), float(row['caller_lat'])],
                                [float(row['called_lon']), float(row['called_lat'])]
                            ]
                        },
                        'properties': {
                            'time': time_str,
                            'popup': popup_html,
                            'style': {
                                'color': line_color,
                                'weight': 2,
                                'opacity': 0.7
                            }
                        }
                    })
        
        if features:
            # Calculate time range for appropriate period
            time_range = (loc_df['timestamp'].max() - loc_df['timestamp'].min())
            if time_range.days > 7:
                period = 'P1D'  # 1 day
            elif time_range.days > 1:
                period = 'PT6H'  # 6 hours
            else:
                period = 'PT1H'  # 1 hour
            
            # Add timestamped GeoJSON layer
            plugins.TimestampedGeoJson(
                {
                    'type': 'FeatureCollection',
                    'features': features
                },
                period=period,
                add_last_point=True,
                auto_play=False,
                loop=False,
                max_speed=10,
                loop_button=True,
                date_options='YYYY-MM-DD HH:mm:ss',
                time_slider_drag_update=True,
                duration='P1D'
            ).add_to(m)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Add legend
        legend_html = """
        <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000; 
                    background-color: white; padding: 15px; border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-family: 'Segoe UI', Arial;">
            <h4 style="margin: 0 0 10px 0; font-size: 14px; color: #333;">📍 Legend</h4>
            <div style="font-size: 12px;">
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 12px; height: 12px; 
                   background: #3498db; border-radius: 50%; margin-right: 8px;"></span>Caller (Answered)</p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 12px; height: 12px; 
                   background: #e74c3c; border-radius: 50%; margin-right: 8px;"></span>Caller (Missed)</p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 12px; height: 12px; 
                   background: #2ecc71; border-radius: 50%; margin-right: 8px;"></span>Called (Answered)</p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 12px; height: 12px; 
                   background: #f39c12; border-radius: 50%; margin-right: 8px;"></span>Called (Missed)</p>
                <p style="margin: 5px 0;"><span style="display: inline-block; width: 20px; height: 2px; 
                   background: #9b59b6; margin-right: 8px; vertical-align: middle;"></span>Call Connection</p>
            </div>
            <hr style="margin: 10px 0; border: none; border-top: 1px solid #eee;">
            <p style="margin: 0; font-size: 11px; color: #666;">Click markers for call details</p>
            <p style="margin: 2px 0 0 0; font-size: 11px; color: #666;">Use timeline slider to navigate</p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Add title
        title_html = f"""
        <div style="position: fixed; top: 10px; left: 50px; z-index: 1000; 
                    background-color: white; padding: 10px 20px; border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.2); font-family: 'Segoe UI', Arial;">
            <h3 style="margin: 0; color: #333;">📞 Call Timeline Map</h3>
            <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
                Showing {len(loc_df)} calls | 
                {loc_df['timestamp'].min().strftime('%Y-%m-%d')} to {loc_df['timestamp'].max().strftime('%Y-%m-%d')}
            </p>
        </div>
        """
        m.get_root().html.add_child(folium.Element(title_html))
        
        return m
    
    def create_call_cluster_map(
        self,
        max_calls: int = 1000,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Optional['folium.Map']:
        """
        Create a clustered marker map of all calls (non-timeline version)
        Better for large datasets where timeline would be too slow
        
        :param max_calls: Maximum number of calls
        :param start_date: Optional start date filter
        :param end_date: Optional end date filter
        :return: Folium Map object
        """
        if not self._check_folium() or not self._check_data_loaded():
            return None
        
        loc_df = self._get_call_location_data(start_date, end_date, max_calls)
        
        if loc_df.empty:
            logger.warning("No location data available")
            return None
        
        # Determine center
        valid_lats = pd.concat([
            loc_df['caller_lat'].dropna(),
            loc_df['called_lat'].dropna()
        ])
        valid_lons = pd.concat([
            loc_df['caller_lon'].dropna(),
            loc_df['called_lon'].dropna()
        ])
        
        if len(valid_lats) > 0:
            center = (valid_lats.mean(), valid_lons.mean())
        else:
            center = (51.1657, 10.4515)
        
        m = folium.Map(location=center, zoom_start=6, tiles='OpenStreetMap')
        folium.TileLayer('cartodbpositron', name='Light Mode').add_to(m)
        
        # Create marker cluster
        marker_cluster = plugins.MarkerCluster(name='Calls').add_to(m)
        
        # Add markers
        for _, row in loc_df.iterrows():
            if pd.notna(row['caller_lat']) and pd.notna(row['caller_lon']):
                call_data = row.to_dict()
                popup_html = self._get_call_details_html(call_data)
                
                # Choose icon color
                if row['answered']:
                    color = 'blue'
                    icon_name = 'phone'
                else:
                    color = 'red'
                    icon_name = 'phone-slash'
                
                icon = folium.Icon(color=color, icon=icon_name, prefix='fa')
                
                tooltip = f"{row['caller']} → {row['called']}<br>{row['timestamp'].strftime('%Y-%m-%d %H:%M') if isinstance(row['timestamp'], pd.Timestamp) else row['timestamp']}"
                
                folium.Marker(
                    [row['caller_lat'], row['caller_lon']],
                    popup=folium.Popup(popup_html, max_width=400),
                    tooltip=tooltip,
                    icon=icon
                ).add_to(marker_cluster)
        
        folium.LayerControl().add_to(m)
        
        return m
    
    def save_map(
        self,
        map_obj: 'folium.Map',
        filename: str,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Save map to HTML file
        
        :param map_obj: Folium Map object
        :param filename: Output filename
        :param output_dir: Output directory
        :return: Path to saved file
        """
        output_dir = output_dir or self.output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        if not filename.endswith('.html'):
            filename += '.html'
        
        filepath = os.path.join(output_dir, filename)
        map_obj.save(filepath)
        
        logger.info(f"Map saved: {filepath}")
        return filepath