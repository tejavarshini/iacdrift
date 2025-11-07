#!/usr/bin/env python3
"""
IaC Drift Detection Database Manager
Handles persistent storage of drift reports and historical data
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

class DriftDatabase:
    """Database manager for drift detection reports"""
    
    def __init__(self, db_path: str = '../data/drift_detection.db'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS drift_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    drift_detected BOOLEAN NOT NULL,
                    total_issues INTEGER NOT NULL,
                    high_severity INTEGER NOT NULL,
                    medium_severity INTEGER NOT NULL,
                    low_severity INTEGER NOT NULL,
                    report_data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS drift_details (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL,
                    drift_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    resource TEXT,
                    message TEXT NOT NULL,
                    expected_value TEXT,
                    actual_value TEXT,
                    FOREIGN KEY (report_id) REFERENCES drift_reports (id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS infrastructure_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id INTEGER NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_name TEXT NOT NULL,
                    expected_state TEXT,
                    actual_state TEXT,
                    state_timestamp TEXT NOT NULL,
                    FOREIGN KEY (report_id) REFERENCES drift_reports (id)
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON drift_reports (timestamp)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_reports_environment ON drift_reports (environment)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_details_report ON drift_details (report_id)
            ''')
            
            conn.commit()
    
    def store_report(self, report: Dict) -> int:
        """Store a drift detection report in the database"""
        with sqlite3.connect(self.db_path) as conn:
            # Insert main report
            cursor = conn.execute('''
                INSERT INTO drift_reports (
                    timestamp, environment, drift_detected, total_issues,
                    high_severity, medium_severity, low_severity, report_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report.get('timestamp', datetime.now().isoformat()),
                report.get('environment', 'unknown'),
                report.get('drift_detected', False),
                report.get('summary', {}).get('total_issues', 0),
                report.get('summary', {}).get('high_severity', 0),
                report.get('summary', {}).get('medium_severity', 0),
                report.get('summary', {}).get('low_severity', 0),
                json.dumps(report),
                datetime.now().isoformat()
            ))
            
            report_id = cursor.lastrowid
            
            # Insert drift details
            for detail in report.get('drift_details', []):
                conn.execute('''
                    INSERT INTO drift_details (
                        report_id, drift_type, severity, resource, message,
                        expected_value, actual_value
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    report_id,
                    detail.get('type', 'unknown'),
                    detail.get('severity', 'unknown'),
                    detail.get('resource', ''),
                    detail.get('message', ''),
                    str(detail.get('expected', '')),
                    str(detail.get('actual', ''))
                ))
            
            # Store infrastructure state
            infra_state = report.get('infrastructure_state', {})
            timestamp = report.get('timestamp', datetime.now().isoformat())
            
            # Store expected state
            expected = infra_state.get('expected', {})
            for resource_type, count in expected.items():
                conn.execute('''
                    INSERT INTO infrastructure_state (
                        report_id, resource_type, resource_name, expected_state,
                        actual_state, state_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    report_id, f'expected_{resource_type}', resource_type,
                    str(count), '', timestamp
                ))
            
            # Store actual state
            actual = infra_state.get('actual', {})
            for resource_type, count in actual.items():
                conn.execute('''
                    INSERT INTO infrastructure_state (
                        report_id, resource_type, resource_name, expected_state,
                        actual_state, state_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    report_id, f'actual_{resource_type}', resource_type,
                    '', str(count), timestamp
                ))
            
            conn.commit()
            return report_id
    
    def get_latest_report(self, environment: str = None) -> Optional[Dict]:
        """Get the most recent drift report"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = '''
                SELECT * FROM drift_reports 
                WHERE 1=1
            '''
            params = []
            
            if environment:
                query += ' AND environment = ?'
                params.append(environment)
            
            query += ' ORDER BY timestamp DESC LIMIT 1'
            
            row = conn.execute(query, params).fetchone()
            
            if row:
                report = json.loads(row['report_data'])
                report['id'] = row['id']
                return report
            
            return None
    
    def get_reports(self, environment: str = None, limit: int = 10, 
                   start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get drift reports with optional filters"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = '''
                SELECT * FROM drift_reports 
                WHERE 1=1
            '''
            params = []
            
            if environment:
                query += ' AND environment = ?'
                params.append(environment)
            
            if start_date:
                query += ' AND timestamp >= ?'
                params.append(start_date)
            
            if end_date:
                query += ' AND timestamp <= ?'
                params.append(end_date)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            rows = conn.execute(query, params).fetchall()
            
            reports = []
            for row in rows:
                report = json.loads(row['report_data'])
                report['id'] = row['id']
                reports.append(report)
            
            return reports
    
    def get_drift_statistics(self, environment: str = None, days: int = 7) -> Dict:
        """Get drift detection statistics for the specified period"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            query = '''
                SELECT 
                    COUNT(*) as total_reports,
                    SUM(CASE WHEN drift_detected = 1 THEN 1 ELSE 0 END) as drift_reports,
                    AVG(total_issues) as avg_issues,
                    MAX(total_issues) as max_issues,
                    SUM(high_severity) as total_high,
                    SUM(medium_severity) as total_medium,
                    SUM(low_severity) as total_low
                FROM drift_reports 
                WHERE timestamp >= ?
            '''
            params = [start_date]
            
            if environment:
                query += ' AND environment = ?'
                params.append(environment)
            
            row = conn.execute(query, params).fetchone()
            
            # Get drift trend data
            trend_query = '''
                SELECT 
                    DATE(timestamp) as report_date,
                    COUNT(*) as reports_count,
                    SUM(CASE WHEN drift_detected = 1 THEN 1 ELSE 0 END) as drift_count,
                    AVG(total_issues) as avg_issues
                FROM drift_reports 
                WHERE timestamp >= ?
            '''
            trend_params = [start_date]
            
            if environment:
                trend_query += ' AND environment = ?'
                trend_params.append(environment)
            
            trend_query += ' GROUP BY DATE(timestamp) ORDER BY report_date'
            
            trend_rows = conn.execute(trend_query, trend_params).fetchall()
            
            return {
                'summary': {
                    'total_reports': row['total_reports'] or 0,
                    'drift_reports': row['drift_reports'] or 0,
                    'drift_percentage': (row['drift_reports'] / max(row['total_reports'], 1)) * 100,
                    'avg_issues': row['avg_issues'] or 0,
                    'max_issues': row['max_issues'] or 0,
                    'total_high_severity': row['total_high'] or 0,
                    'total_medium_severity': row['total_medium'] or 0,
                    'total_low_severity': row['total_low'] or 0
                },
                'trend': [dict(row) for row in trend_rows],
                'period': f'{days} days',
                'start_date': start_date,
                'end_date': datetime.now().isoformat()
            }
    
    def get_infrastructure_trends(self, environment: str = None, days: int = 7) -> Dict:
        """Get infrastructure resource trends"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            query = '''
                SELECT 
                    state_timestamp,
                    resource_type,
                    resource_name,
                    expected_state,
                    actual_state
                FROM infrastructure_state 
                WHERE state_timestamp >= ?
            '''
            params = [start_date]
            
            if environment:
                query += '''
                    AND report_id IN (
                        SELECT id FROM drift_reports WHERE environment = ?
                    )
                '''
                params.append(environment)
            
            query += ' ORDER BY state_timestamp'
            
            rows = conn.execute(query, params).fetchall()
            
            trends = {}
            for row in rows:
                resource_type = row['resource_type']
                if resource_type not in trends:
                    trends[resource_type] = []
                
                trends[resource_type].append({
                    'timestamp': row['state_timestamp'],
                    'resource_name': row['resource_name'],
                    'expected': row['expected_state'],
                    'actual': row['actual_state']
                })
            
            return trends
    
    def cleanup_old_reports(self, days: int = 30) -> int:
        """Remove old reports to keep database size manageable"""
        with sqlite3.connect(self.db_path) as conn:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get report IDs to delete
            cursor = conn.execute('''
                SELECT id FROM drift_reports WHERE timestamp < ?
            ''', (cutoff_date,))
            
            report_ids = [row[0] for row in cursor.fetchall()]
            
            if not report_ids:
                return 0
            
            # Delete related records
            placeholders = ','.join('?' * len(report_ids))
            
            conn.execute(f'''
                DELETE FROM drift_details WHERE report_id IN ({placeholders})
            ''', report_ids)
            
            conn.execute(f'''
                DELETE FROM infrastructure_state WHERE report_id IN ({placeholders})
            ''', report_ids)
            
            conn.execute(f'''
                DELETE FROM drift_reports WHERE id IN ({placeholders})
            ''', report_ids)
            
            conn.commit()
            return len(report_ids)
    
    def export_reports(self, filename: str, environment: str = None, 
                      start_date: str = None, end_date: str = None):
        """Export reports to JSON file"""
        reports = self.get_reports(
            environment=environment,
            limit=1000,  # Large limit for export
            start_date=start_date,
            end_date=end_date
        )
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'environment': environment,
            'start_date': start_date,
            'end_date': end_date,
            'total_reports': len(reports),
            'reports': reports
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)

# Example usage and testing
if __name__ == '__main__':
    # Initialize database
    db = DriftDatabase()
    
    # Example report
    sample_report = {
        'timestamp': datetime.now().isoformat(),
        'environment': 'dev',
        'drift_detected': True,
        'summary': {
            'total_issues': 2,
            'high_severity': 1,
            'medium_severity': 1,
            'low_severity': 0
        },
        'drift_details': [
            {
                'type': 'container_status_drift',
                'severity': 'high',
                'resource': 'web-container-1',
                'message': 'Container is not running',
                'expected': 'running',
                'actual': 'stopped'
            },
            {
                'type': 'port_drift',
                'severity': 'medium',
                'resource': 'web-container-1',
                'message': 'Port configuration changed',
                'expected': '8080',
                'actual': '8081'
            }
        ],
        'infrastructure_state': {
            'expected': {
                'containers': 3,
                'networks': 1,
                'volumes': 2
            },
            'actual': {
                'containers': 2,
                'containers_running': 2,
                'networks': 1,
                'volumes': 2
            }
        }
    }
    
    # Store the report
    report_id = db.store_report(sample_report)
    print(f"Stored report with ID: {report_id}")
    
    # Get latest report
    latest = db.get_latest_report('dev')
    print(f"Latest report: {latest['timestamp'] if latest else 'None'}")
    
    # Get statistics
    stats = db.get_drift_statistics('dev', days=7)
    print(f"Statistics: {stats['summary']}")