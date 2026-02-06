"""
Validation utilities for CDR/CMR data
Includes data validation, schema checking, and input sanitization
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple, Union
import re
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """Validator for CDR/CMR data integrity and quality"""
    
    # Expected CDR columns with their types
    CDR_SCHEMA = {
        'globalCallID_callManagerId': {'type': 'numeric', 'required': True},
        'globalCallID_callId': {'type': 'numeric', 'required': True},
        'dateTimeOrigination': {'type': 'timestamp', 'required': True},
        'dateTimeConnect': {'type': 'timestamp', 'required': False},
        'dateTimeDisconnect': {'type': 'timestamp', 'required': False},
        'callingPartyNumber': {'type': 'string', 'required': True},
        'finalCalledPartyNumber': {'type': 'string', 'required': True},
        'duration': {'type': 'numeric', 'required': True, 'min': 0},
        'origDeviceName': {'type': 'string', 'required': False},
        'destDeviceName': {'type': 'string', 'required': False},
        'origCause_value': {'type': 'numeric', 'required': False},
        'destCause_value': {'type': 'numeric', 'required': False},
    }
    
    # Expected CMR columns with their types
    CMR_SCHEMA = {
        'globalCallID_callManagerId': {'type': 'numeric', 'required': True},
        'globalCallID_callId': {'type': 'numeric', 'required': True},
        'origdeviceName': {'type': 'string', 'required': False},
        'destdeviceName': {'type': 'string', 'required': False},
        'orignumberPacketsSent': {'type': 'numeric', 'required': False, 'min': 0},
        'orignumberPacketsReceived': {'type': 'numeric', 'required': False, 'min': 0},
        'orignumberPacketsLost': {'type': 'numeric', 'required': False, 'min': 0},
        'destnumberPacketsSent': {'type': 'numeric', 'required': False, 'min': 0},
        'destnumberPacketsReceived': {'type': 'numeric', 'required': False, 'min': 0},
        'destnumberPacketsLost': {'type': 'numeric', 'required': False, 'min': 0},
        'origjitter': {'type': 'numeric', 'required': False, 'min': 0},
        'destjitter': {'type': 'numeric', 'required': False, 'min': 0},
        'origlatency': {'type': 'numeric', 'required': False, 'min': 0},
        'destlatency': {'type': 'numeric', 'required': False, 'min': 0},
    }
    
    def __init__(self):
        self.validation_errors: List[Dict[str, Any]] = []
        self.validation_warnings: List[Dict[str, Any]] = []
    
    def validate_cdr(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate CDR DataFrame against schema
        
        :param df: CDR DataFrame to validate
        :return: Tuple of (is_valid, validation_report)
        """
        self.validation_errors = []
        self.validation_warnings = []
        
        report = {
            'total_rows': len(df),
            'columns_found': list(df.columns),
            'missing_required': [],
            'missing_optional': [],
            'type_errors': [],
            'value_errors': [],
            'data_quality': {},
        }
        
        # Check required columns
        for col, spec in self.CDR_SCHEMA.items():
            if col not in df.columns:
                if spec['required']:
                    report['missing_required'].append(col)
                    self._add_error('missing_column', f"Required column '{col}' is missing")
                else:
                    report['missing_optional'].append(col)
        
        # Validate column types and values
        for col, spec in self.CDR_SCHEMA.items():
            if col not in df.columns:
                continue
            
            # Type validation
            type_errors = self._validate_column_type(df[col], spec['type'], col)
            report['type_errors'].extend(type_errors)
            
            # Value validation
            if 'min' in spec:
                value_errors = self._validate_min_value(df[col], spec['min'], col)
                report['value_errors'].extend(value_errors)
            
            if 'max' in spec:
                value_errors = self._validate_max_value(df[col], spec['max'], col)
                report['value_errors'].extend(value_errors)
        
        # Data quality checks
        report['data_quality'] = self._check_cdr_data_quality(df)
        
        # Determine overall validity
        is_valid = len(report['missing_required']) == 0 and len(report['type_errors']) == 0
        
        report['is_valid'] = is_valid
        report['error_count'] = len(self.validation_errors)
        report['warning_count'] = len(self.validation_warnings)
        report['errors'] = self.validation_errors
        report['warnings'] = self.validation_warnings
        
        return is_valid, report
    
    def validate_cmr(self, df: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate CMR DataFrame against schema
        
        :param df: CMR DataFrame to validate
        :return: Tuple of (is_valid, validation_report)
        """
        self.validation_errors = []
        self.validation_warnings = []
        
        report = {
            'total_rows': len(df),
            'columns_found': list(df.columns),
            'missing_required': [],
            'missing_optional': [],
            'type_errors': [],
            'value_errors': [],
            'data_quality': {},
        }
        
        # Check required columns
        for col, spec in self.CMR_SCHEMA.items():
            if col not in df.columns:
                if spec['required']:
                    report['missing_required'].append(col)
                    self._add_error('missing_column', f"Required column '{col}' is missing")
                else:
                    report['missing_optional'].append(col)
        
        # Validate column types and values
        for col, spec in self.CMR_SCHEMA.items():
            if col not in df.columns:
                continue
            
            type_errors = self._validate_column_type(df[col], spec['type'], col)
            report['type_errors'].extend(type_errors)
            
            if 'min' in spec:
                value_errors = self._validate_min_value(df[col], spec['min'], col)
                report['value_errors'].extend(value_errors)
        
        # Data quality checks
        report['data_quality'] = self._check_cmr_data_quality(df)
        
        is_valid = len(report['missing_required']) == 0
        
        report['is_valid'] = is_valid
        report['error_count'] = len(self.validation_errors)
        report['warning_count'] = len(self.validation_warnings)
        report['errors'] = self.validation_errors
        report['warnings'] = self.validation_warnings
        
        return is_valid, report
    
    def _validate_column_type(
        self, 
        series: pd.Series, 
        expected_type: str,
        col_name: str
    ) -> List[Dict[str, Any]]:
        """Validate column data type"""
        errors = []
        
        if expected_type == 'numeric':
            non_numeric = pd.to_numeric(series, errors='coerce').isna() & series.notna()
            if non_numeric.any():
                count = non_numeric.sum()
                errors.append({
                    'column': col_name,
                    'error': 'non_numeric_values',
                    'count': int(count),
                    'sample': series[non_numeric].head(3).tolist(),
                })
                self._add_warning('type_mismatch', 
                                 f"Column '{col_name}' has {count} non-numeric values")
        
        elif expected_type == 'timestamp':
            # Check if values are valid Unix timestamps
            try:
                numeric_series = pd.to_numeric(series, errors='coerce')
                invalid = (numeric_series < 0) | (numeric_series > 2147483647)
                if invalid.any():
                    count = invalid.sum()
                    errors.append({
                        'column': col_name,
                        'error': 'invalid_timestamp',
                        'count': int(count),
                    })
            except Exception:
                pass
        
        elif expected_type == 'string':
            # String columns should not be entirely null
            if series.isna().all():
                self._add_warning('all_null', f"Column '{col_name}' is entirely null")
        
        return errors
    
    def _validate_min_value(
        self, 
        series: pd.Series, 
        min_val: float,
        col_name: str
    ) -> List[Dict[str, Any]]:
        """Validate minimum value constraint"""
        errors = []
        
        try:
            numeric_series = pd.to_numeric(series, errors='coerce')
            below_min = numeric_series < min_val
            if below_min.any():
                count = below_min.sum()
                errors.append({
                    'column': col_name,
                    'error': 'below_minimum',
                    'min_value': min_val,
                    'count': int(count),
                    'min_found': float(numeric_series.min()),
                })
                self._add_warning('value_range', 
                                 f"Column '{col_name}' has {count} values below {min_val}")
        except Exception:
            pass
        
        return errors
    
    def _validate_max_value(
        self, 
        series: pd.Series, 
        max_val: float,
        col_name: str
    ) -> List[Dict[str, Any]]:
        """Validate maximum value constraint"""
        errors = []
        
        try:
            numeric_series = pd.to_numeric(series, errors='coerce')
            above_max = numeric_series > max_val
            if above_max.any():
                count = above_max.sum()
                errors.append({
                    'column': col_name,
                    'error': 'above_maximum',
                    'max_value': max_val,
                    'count': int(count),
                    'max_found': float(numeric_series.max()),
                })
        except Exception:
            pass
        
        return errors
    
    def _check_cdr_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform data quality checks on CDR data"""
        quality = {
            'null_percentages': {},
            'duplicate_records': 0,
            'suspicious_values': [],
        }
        
        # Null percentages
        for col in df.columns:
            null_pct = df[col].isna().mean() * 100
            if null_pct > 0:
                quality['null_percentages'][col] = round(null_pct, 2)
        
        # Duplicate call IDs
        if 'globalCallID_callId' in df.columns:
            duplicates = df.duplicated(subset=['globalCallID_callManagerId', 'globalCallID_callId'])
            quality['duplicate_records'] = int(duplicates.sum())
            if duplicates.any():
                self._add_warning('duplicates', 
                                 f"Found {duplicates.sum()} duplicate call records")
        
        # Duration checks
        if 'duration' in df.columns:
            duration = pd.to_numeric(df['duration'], errors='coerce')
            
            # Very long calls (>4 hours)
            very_long = duration > 14400
            if very_long.any():
                quality['suspicious_values'].append({
                    'type': 'very_long_calls',
                    'count': int(very_long.sum()),
                    'description': 'Calls longer than 4 hours',
                })
            
            # Negative durations
            negative = duration < 0
            if negative.any():
                quality['suspicious_values'].append({
                    'type': 'negative_duration',
                    'count': int(negative.sum()),
                    'description': 'Calls with negative duration',
                })
                self._add_error('invalid_data', 
                               f"Found {negative.sum()} calls with negative duration")
        
        # Timestamp consistency
        if all(col in df.columns for col in ['dateTimeOrigination', 'dateTimeDisconnect']):
            orig = pd.to_numeric(df['dateTimeOrigination'], errors='coerce')
            disc = pd.to_numeric(df['dateTimeDisconnect'], errors='coerce')
            
            # Disconnect before origination
            invalid_order = disc < orig
            if invalid_order.any():
                quality['suspicious_values'].append({
                    'type': 'invalid_timestamp_order',
                    'count': int(invalid_order.sum()),
                    'description': 'Disconnect time before origination time',
                })
        
        # Empty phone numbers
        if 'callingPartyNumber' in df.columns:
            empty_caller = (
                df['callingPartyNumber'].isna() | 
                (df['callingPartyNumber'].astype(str).str.strip() == '')
            )
            if empty_caller.any():
                quality['suspicious_values'].append({
                    'type': 'empty_caller',
                    'count': int(empty_caller.sum()),
                    'description': 'Records with empty calling party number',
                })
        
        return quality
    
    def _check_cmr_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Perform data quality checks on CMR data"""
        quality = {
            'null_percentages': {},
            'suspicious_values': [],
            'metric_ranges': {},
        }
        
        # Null percentages for key columns
        key_cols = ['origjitter', 'destjitter', 'origlatency', 'destlatency',
                   'orignumberPacketsSent', 'orignumberPacketsLost']
        
        for col in key_cols:
            if col in df.columns:
                null_pct = df[col].isna().mean() * 100
                quality['null_percentages'][col] = round(null_pct, 2)
        
        # Jitter range check
        if 'origjitter' in df.columns:
            jitter = pd.to_numeric(df['origjitter'], errors='coerce')
            quality['metric_ranges']['jitter'] = {
                'min': float(jitter.min()) if not jitter.isna().all() else None,
                'max': float(jitter.max()) if not jitter.isna().all() else None,
                'mean': float(jitter.mean()) if not jitter.isna().all() else None,
            }
            
            # Unrealistic jitter (>500ms)
            high_jitter = jitter > 500
            if high_jitter.any():
                quality['suspicious_values'].append({
                    'type': 'unrealistic_jitter',
                    'count': int(high_jitter.sum()),
                    'description': 'Jitter values exceeding 500ms',
                })
        
        # Latency range check
        if 'origlatency' in df.columns:
            latency = pd.to_numeric(df['origlatency'], errors='coerce')
            quality['metric_ranges']['latency'] = {
                'min': float(latency.min()) if not latency.isna().all() else None,
                'max': float(latency.max()) if not latency.isna().all() else None,
                'mean': float(latency.mean()) if not latency.isna().all() else None,
            }
            
            # Unrealistic latency (>2000ms)
            high_latency = latency > 2000
            if high_latency.any():
                quality['suspicious_values'].append({
                    'type': 'unrealistic_latency',
                    'count': int(high_latency.sum()),
                    'description': 'Latency values exceeding 2000ms',
                })
        
        # Packet loss validation
        if 'orignumberPacketsSent' in df.columns and 'orignumberPacketsLost' in df.columns:
            sent = pd.to_numeric(df['orignumberPacketsSent'], errors='coerce')
            lost = pd.to_numeric(df['orignumberPacketsLost'], errors='coerce')
            
            # Lost > Sent
            invalid_loss = lost > sent
            if invalid_loss.any():
                quality['suspicious_values'].append({
                    'type': 'invalid_packet_loss',
                    'count': int(invalid_loss.sum()),
                    'description': 'Packets lost exceeds packets sent',
                })
                self._add_error('invalid_data',
                               f"Found {invalid_loss.sum()} records where packets lost > packets sent")
        
        return quality
    
    def _add_error(self, error_type: str, message: str):
        """Add validation error"""
        self.validation_errors.append({
            'type': error_type,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        })
        logger.error(f"Validation error: {message}")
    
    def _add_warning(self, warning_type: str, message: str):
        """Add validation warning"""
        self.validation_warnings.append({
            'type': warning_type,
            'message': message,
            'timestamp': datetime.now().isoformat(),
        })
        logger.warning(f"Validation warning: {message}")


class InputValidator:
    """Validator for user inputs and parameters"""
    
    @staticmethod
    def validate_date(
        date_input: Union[str, date, datetime],
        param_name: str = 'date'
    ) -> date:
        """
        Validate and convert date input
        
        :param date_input: Date string, date, or datetime object
        :param param_name: Parameter name for error messages
        :return: Validated date object
        :raises ValueError: If date is invalid
        """
        if isinstance(date_input, datetime):
            return date_input.date()
        
        if isinstance(date_input, date):
            return date_input
        
        if isinstance(date_input, str):
            # Try common date formats
            formats = [
                '%Y-%m-%d',
                '%Y/%m/%d',
                '%d-%m-%Y',
                '%d/%m/%Y',
                '%Y%m%d',
                '%m-%d-%Y',
                '%m/%d/%Y',
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_input, fmt).date()
                except ValueError:
                    continue
            
            raise ValueError(
                f"Invalid date format for '{param_name}': {date_input}. "
                f"Expected formats: YYYY-MM-DD, DD-MM-YYYY, etc."
            )
        
        raise TypeError(
            f"Invalid type for '{param_name}': expected date string or date object, "
            f"got {type(date_input).__name__}"
        )
    
    @staticmethod
    def validate_date_range(
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime]
    ) -> Tuple[date, date]:
        """
        Validate date range
        
        :param start_date: Start date
        :param end_date: End date
        :return: Tuple of (start_date, end_date)
        :raises ValueError: If date range is invalid
        """
        start = InputValidator.validate_date(start_date, 'start_date')
        end = InputValidator.validate_date(end_date, 'end_date')
        
        if start > end:
            raise ValueError(
                f"Invalid date range: start_date ({start}) is after end_date ({end})"
            )
        
        return start, end
    
    @staticmethod
    def validate_phone_number(
        phone: str,
        allow_extension: bool = True,
        param_name: str = 'phone'
    ) -> str:
        """
        Validate phone number format
        
        :param phone: Phone number string
        :param allow_extension: Allow short extension numbers
        :param param_name: Parameter name for error messages
        :return: Cleaned phone number
        :raises ValueError: If phone number is invalid
        """
        if not phone or not isinstance(phone, str):
            raise ValueError(f"Invalid {param_name}: empty or not a string")
        
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\.\(\)\+]', '', phone)
        
        # Check if it's numeric
        if not cleaned.isdigit():
            # Allow 'x' prefix for extensions
            if not (cleaned.lower().startswith('x') and cleaned[1:].isdigit()):
                raise ValueError(
                    f"Invalid {param_name}: '{phone}' contains non-numeric characters"
                )
        
        # Length validation
        if len(cleaned) < 3:
            raise ValueError(
                f"Invalid {param_name}: '{phone}' is too short (minimum 3 digits)"
            )
        
        if len(cleaned) > 15:
            raise ValueError(
                f"Invalid {param_name}: '{phone}' is too long (maximum 15 digits)"
            )
        
        if not allow_extension and len(cleaned) < 7:
            raise ValueError(
                f"Invalid {param_name}: '{phone}' appears to be an extension, "
                f"but extensions are not allowed"
            )
        
        return cleaned
    
    @staticmethod
    def validate_device_name(
        device: str,
        param_name: str = 'device'
    ) -> str:
        """
        Validate device name format
        
        :param device: Device name string
        :param param_name: Parameter name for error messages
        :return: Validated device name
        :raises ValueError: If device name is invalid
        """
        if not device or not isinstance(device, str):
            raise ValueError(f"Invalid {param_name}: empty or not a string")
        
        device = device.strip()
        
        if len(device) < 3:
            raise ValueError(
                f"Invalid {param_name}: '{device}' is too short"
            )
        
        if len(device) > 128:
            raise ValueError(
                f"Invalid {param_name}: '{device}' exceeds maximum length of 128"
            )
        
        # Check for valid device name patterns
        valid_patterns = [
            r'^SEP[A-Fa-f0-9]{12}$',      # IP Phone
            r'^CSF.+$',                     # Jabber
            r'^TCT.+$',                     # Jabber mobile
            r'^TAB.+$',                     # Jabber tablet
            r'^CIPC.+$',                    # IP Communicator
            r'^ATA.+$',                     # Analog adapter
            r'^AN.+$',                      # Analog
            r'^CTI.+$',                     # CTI port
            r'^.*(TRUNK|GW|CUBE|SBC).*$',  # Trunk/Gateway
        ]
        
        is_valid = any(re.match(pattern, device, re.IGNORECASE) for pattern in valid_patterns)
        
        if not is_valid:
            logger.warning(
                f"Device name '{device}' does not match known patterns. "
                f"This may be valid but unusual."
            )
        
        return device
    
    @staticmethod
    def validate_positive_integer(
        value: Union[int, str],
        param_name: str = 'value',
        min_val: int = 1,
        max_val: Optional[int] = None
    ) -> int:
        """
        Validate positive integer
        
        :param value: Value to validate
        :param param_name: Parameter name for error messages
        :param min_val: Minimum allowed value
        :param max_val: Maximum allowed value (optional)
        :return: Validated integer
        :raises ValueError: If value is invalid
        """
        try:
            int_value = int(value)
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid {param_name}: '{value}' is not a valid integer"
            )
        
        if int_value < min_val:
            raise ValueError(
                f"Invalid {param_name}: {int_value} is less than minimum {min_val}"
            )
        
        if max_val is not None and int_value > max_val:
            raise ValueError(
                f"Invalid {param_name}: {int_value} exceeds maximum {max_val}"
            )
        
        return int_value
    
    @staticmethod
    def validate_percentage(
        value: Union[float, int, str],
        param_name: str = 'percentage'
    ) -> float:
        """
        Validate percentage value (0-100)
        
        :param value: Value to validate
        :param param_name: Parameter name for error messages
        :return: Validated float
        :raises ValueError: If value is invalid
        """
        try:
            float_value = float(value)
        except (ValueError, TypeError):
            raise ValueError(
                f"Invalid {param_name}: '{value}' is not a valid number"
            )
        
        if float_value < 0 or float_value > 100:
            raise ValueError(
                f"Invalid {param_name}: {float_value} must be between 0 and 100"
            )
        
        return float_value
    
    @staticmethod
    def validate_period(
        period: str,
        allowed: Optional[List[str]] = None
    ) -> str:
        """
        Validate time period string
        
        :param period: Period string (e.g., 'daily', 'weekly')
        :param allowed: List of allowed period values
        :return: Validated period string
        :raises ValueError: If period is invalid
        """
        if allowed is None:
            allowed = ['hourly', 'daily', 'weekly', 'monthly', 'yearly']
        
        period = period.lower().strip()
        
        if period not in allowed:
            raise ValueError(
                f"Invalid period: '{period}'. Allowed values: {', '.join(allowed)}"
            )
        
        return period
    
    @staticmethod
    def validate_user_list(
        users: Union[str, List[str]],
        min_count: int = 1,
        max_count: Optional[int] = None
    ) -> List[str]:
        """
        Validate list of users/extensions
        
        :param users: Single user string or list of users
        :param min_count: Minimum number of users required
        :param max_count: Maximum number of users allowed
        :return: Validated list of users
        :raises ValueError: If validation fails
        """
        if isinstance(users, str):
            users = [users]
        
        if not isinstance(users, list):
            raise TypeError(
                f"Invalid users: expected string or list, got {type(users).__name__}"
            )
        
        # Clean and validate each user
        validated = []
        for user in users:
            if user and isinstance(user, str):
                cleaned = user.strip()
                if cleaned:
                    validated.append(cleaned)
        
        if len(validated) < min_count:
            raise ValueError(
                f"Insufficient users: got {len(validated)}, minimum required is {min_count}"
            )
        
        if max_count is not None and len(validated) > max_count:
            raise ValueError(
                f"Too many users: got {len(validated)}, maximum allowed is {max_count}"
            )
        
        return validated
    
    @staticmethod
    def validate_department_mapping(
        mapping: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """
        Validate department to extension mapping
        
        :param mapping: Dictionary mapping department names to extension lists
        :return: Validated mapping
        :raises ValueError: If mapping is invalid
        """
        if not isinstance(mapping, dict):
            raise TypeError(
                f"Invalid department mapping: expected dict, got {type(mapping).__name__}"
            )
        
        if not mapping:
            raise ValueError("Department mapping cannot be empty")
        
        validated = {}
        
        for dept, extensions in mapping.items():
            if not isinstance(dept, str) or not dept.strip():
                raise ValueError(f"Invalid department name: {dept}")
            
            if not isinstance(extensions, list):
                raise TypeError(
                    f"Extensions for '{dept}' must be a list, got {type(extensions).__name__}"
                )
            
            if not extensions:
                raise ValueError(f"Extension list for '{dept}' cannot be empty")
            
            validated_extensions = []
            for ext in extensions:
                if ext and isinstance(ext, str):
                    validated_extensions.append(ext.strip())
            
            validated[dept.strip()] = validated_extensions
        
        return validated
    
    @staticmethod
    def validate_threshold_config(
        config: Dict[str, float],
        required_keys: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Validate threshold configuration dictionary
        
        :param config: Threshold configuration
        :param required_keys: Required configuration keys
        :return: Validated configuration
        :raises ValueError: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise TypeError(
                f"Invalid threshold config: expected dict, got {type(config).__name__}"
            )
        
        if required_keys:
            missing = set(required_keys) - set(config.keys())
            if missing:
                raise ValueError(
                    f"Missing required threshold keys: {', '.join(missing)}"
                )
        
        validated = {}
        
        for key, value in config.items():
            try:
                float_value = float(value)
                if float_value < 0:
                    raise ValueError(f"Threshold '{key}' cannot be negative")
                validated[key] = float_value
            except (ValueError, TypeError):
                raise ValueError(
                    f"Invalid threshold value for '{key}': {value}"
                )
        
        return validated


class FileValidator:
    """Validator for file inputs"""
    
    ALLOWED_EXTENSIONS = ['.csv', '.txt', '.tsv']
    MAX_FILE_SIZE_MB = 500
    
    @staticmethod
    def validate_file_path(
        file_path: str,
        must_exist: bool = True
    ) -> str:
        """
        Validate file path
        
        :param file_path: Path to file
        :param must_exist: Whether file must exist
        :return: Validated file path
        :raises ValueError: If path is invalid
        :raises FileNotFoundError: If file doesn't exist and must_exist is True
        """
        import os
        
        if not file_path or not isinstance(file_path, str):
            raise ValueError("File path cannot be empty")
        
        file_path = file_path.strip()
        
        if must_exist and not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return file_path
    
    @staticmethod
    def validate_file_extension(
        file_path: str,
        allowed: Optional[List[str]] = None
    ) -> str:
        """
        Validate file extension
        
        :param file_path: Path to file
        :param allowed: List of allowed extensions
        :return: File extension
        :raises ValueError: If extension is not allowed
        """
        import os
        
        if allowed is None:
            allowed = FileValidator.ALLOWED_EXTENSIONS
        
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        if ext not in allowed:
            raise ValueError(
                f"Invalid file extension: '{ext}'. Allowed: {', '.join(allowed)}"
            )
        
        return ext
    
    @staticmethod
    def validate_file_size(
        file_path: str,
        max_size_mb: Optional[float] = None
    ) -> float:
        """
        Validate file size
        
        :param file_path: Path to file
        :param max_size_mb: Maximum allowed size in MB
        :return: File size in MB
        :raises ValueError: If file is too large
        """
        import os
        
        if max_size_mb is None:
            max_size_mb = FileValidator.MAX_FILE_SIZE_MB
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_size_mb:
            raise ValueError(
                f"File too large: {size_mb:.2f}MB exceeds maximum {max_size_mb}MB"
            )
        
        return size_mb
    
    @staticmethod
    def validate_csv_file(
        file_path: str,
        required_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Validate CSV file structure
        
        :param file_path: Path to CSV file
        :param required_columns: List of required column names
        :return: Dictionary with file info
        :raises ValueError: If file is invalid
        """
        import os
        
        # Validate path and extension
        FileValidator.validate_file_path(file_path, must_exist=True)
        FileValidator.validate_file_extension(file_path, ['.csv', '.txt', '.tsv'])
        
        # Check file size
        size_mb = FileValidator.validate_file_size(file_path)
        
        # Try to read header
        try:
            # Read just the first line to get columns
            with open(file_path, 'r', encoding='utf-8') as f:
                header = f.readline().strip()
            
            # Detect separator
            if '\t' in header:
                sep = '\t'
            elif ';' in header:
                sep = ';'
            else:
                sep = ','
            
            columns = [c.strip().strip('"') for c in header.split(sep)]
            
            # Count lines (approximate for large files)
            with open(file_path, 'r', encoding='utf-8') as f:
                line_count = sum(1 for _ in f) - 1  # Subtract header
            
        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    header = f.readline().strip()
                columns = header.split(',')
                line_count = -1  # Unknown
            except Exception as e:
                raise ValueError(f"Cannot read file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error reading CSV file: {str(e)}")
        
        # Check required columns
        missing_columns = []
        if required_columns:
            missing_columns = [c for c in required_columns if c not in columns]
        
        return {
            'file_path': file_path,
            'file_name': os.path.basename(file_path),
            'size_mb': round(size_mb, 2),
            'columns': columns,
            'column_count': len(columns),
            'line_count': line_count,
            'separator': sep,
            'missing_columns': missing_columns,
            'is_valid': len(missing_columns) == 0,
        }