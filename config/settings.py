"""
Configuration settings for the CDR/CMR Analyzer
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import time


@dataclass
class QualityThresholds:
    """Quality metric thresholds for identifying issues"""
    jitter_warning: int = 30      # ms
    jitter_critical: int = 50     # ms
    latency_warning: int = 150    # ms
    latency_critical: int = 300   # ms
    packet_loss_warning: float = 1.0   # %
    packet_loss_critical: float = 3.0  # %
    mos_good: float = 4.0
    mos_acceptable: float = 3.5
    mos_poor: float = 3.0
    

@dataclass
class BusinessHours:
    """Business hours configuration"""
    start_hour: int = 8
    end_hour: int = 18
    business_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri
    timezone: str = "UTC"


@dataclass
class SecurityThresholds:
    """Security detection thresholds"""
    long_call_threshold: int = 3600       # 1 hour in seconds
    high_frequency_threshold: int = 50    # calls per hour
    after_hours_threshold: int = 10       # suspicious after-hours calls
    international_prefixes: List[str] = field(
        default_factory=lambda: ['00', '+', '011']
    )
    blocked_prefixes: List[str] = field(default_factory=list)


@dataclass
class Settings:
    """Main application settings"""
    # File settings
    default_encoding: str = 'utf-8'
    csv_separator: str = ','
    
    # Analysis settings
    quality: QualityThresholds = field(default_factory=QualityThresholds)
    business_hours: BusinessHours = field(default_factory=BusinessHours)
    security: SecurityThresholds = field(default_factory=SecurityThresholds)
    
    # Output settings
    output_dir: str = 'output'
    report_format: str = 'html'  # html, pdf, xlsx
    chart_dpi: int = 150
    chart_format: str = 'png'
    
    # Device type patterns
    device_patterns: Dict[str, str] = field(default_factory=lambda: {
        'SEP': 'IP Phone',
        'CIPC': 'Cisco IP Communicator',
        'CSF': 'Jabber',
        'TCT': 'Jabber Mobile',
        'TAB': 'Jabber Tablet',
        'BOT': 'Bot/IVR',
        'ATA': 'Analog Adapter',
        'AALN': 'Analog Line',
        'AN': 'Analog',
        'MGCP': 'MGCP Gateway',
        'TRUNK': 'SIP Trunk',
        'CTI': 'CTI Port',
    })
    
    # Call type patterns
    trunk_patterns: List[str] = field(
        default_factory=lambda: ['TRUNK', 'GW', 'CUBE', 'SBC']
    )
    
    # Codec mappings
    codec_names: Dict[int, str] = field(default_factory=lambda: {
        1: 'G.711 A-law',
        2: 'G.711 μ-law', 
        3: 'G.722',
        4: 'G.723.1',
        5: 'G.728',
        6: 'G.729',
        7: 'G.729a',
        8: 'G.729b',
        9: 'G.729ab',
        10: 'GSM',
        11: 'GSM-EFR',
        12: 'iLBC',
        13: 'iSAC',
        14: 'AMR',
        15: 'AMR-WB',
        16: 'OPUS',
        40: 'G.722.1',
        41: 'G.722.1-C',
        86: 'AAC-LD',
        100: 'H.264',
        101: 'H.263',
    })
    
    # Cause codes mapping
    cause_codes: Dict[int, str] = field(default_factory=lambda: {
        0: 'No Error',
        1: 'Unallocated Number',
        2: 'No Route to Network',
        3: 'No Route to Destination',
        16: 'Normal Clearing',
        17: 'User Busy',
        18: 'No User Response',
        19: 'No Answer from User',
        20: 'Subscriber Absent',
        21: 'Call Rejected',
        22: 'Number Changed',
        27: 'Destination Out of Order',
        28: 'Invalid Number Format',
        29: 'Facility Rejected',
        31: 'Normal Unspecified',
        34: 'No Circuit Available',
        38: 'Network Out of Order',
        41: 'Temporary Failure',
        42: 'Switching Equipment Congestion',
        47: 'Resource Unavailable',
        50: 'Requested Facility Not Subscribed',
        52: 'Outgoing Calls Barred',
        54: 'Incoming Calls Barred',
        57: 'Bearer Capability Not Authorized',
        58: 'Bearer Capability Not Available',
        63: 'Service Not Available',
        65: 'Bearer Capability Not Implemented',
        79: 'Service Not Implemented',
        88: 'Incompatible Destination',
        95: 'Invalid Message',
        97: 'Message Type Non-Existent',
        99: 'Info Element Non-Existent',
        100: 'Invalid Info Element',
        102: 'Recovery on Timer Expiry',
        111: 'Protocol Error',
        127: 'Interworking Unspecified',
        393216: 'Conference Drop Any Party',
        458752: 'Conference Drop Last Party',
        131337: 'Calling Party Drop',
        131338: 'Called Party Drop',
    })
    
    @classmethod
    def load_from_file(cls, filepath: str) -> 'Settings':
        """Load settings from JSON/YAML file"""
        import json
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    def save_to_file(self, filepath: str):
        """Save settings to JSON file"""
        import json
        from dataclasses import asdict
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f, indent=2)