#!/usr/bin/env python3
"""
IaC Drift Detection Dashboard
A simple web interface to display drift detection results and system status
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import glob

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'scripts' / 'drift-detection'))

from flask import Flask, render_template, jsonify, request
try:
    from drift_detector import DriftDetector
except ImportError:
    # Fallback - create a minimal DriftDetector for testing
    class DriftDetector:
        def __init__(self, config_file):
            self.config_file = config_file
        
        def get_terraform_state(self):
            return {'expected_infrastructure': {'containers': {}, 'networks': {}, 'volumes': {}}}
        
        def get_docker_state(self):
            return {'actual_infrastructure': {'containers': {}, 'networks': {}, 'volumes': {}}}
        
        def analyze_drift(self, terraform_state, docker_state):
            return False, []
        
        def run_drift_detection(self):
            return {'drift_detected': False, 'timestamp': datetime.now().isoformat()}

app = Flask(__name__)

class DashboardManager:
    def __init__(self, config_file='../config/drift-detection.json'):
        self.config_file = config_file
        self.detector = DriftDetector(config_file)
        self.logs_dir = Path('../logs')
        # Also set up database path
        self.database_path = Path('../data/drift_detection.db')
        # Add database directory to path
        database_dir = Path('../database')
        sys.path.append(str(database_dir))
        try:
            from drift_database import DriftDatabase
            self.db = DriftDatabase(str(self.database_path))
        except ImportError:
            self.db = None
        
    def get_latest_report(self):
        """Get the most recent drift report from database or files"""
        try:
            # Try database first
            if self.db:
                latest_report = self.db.get_latest_report()
                if latest_report:
                    return latest_report
            
            # Fallback to file system
            report_files = glob.glob(str(self.logs_dir / 'drift-report-*.json'))
            if not report_files:
                return self._create_default_report()
                
            # Sort by timestamp in filename
            latest_file = max(report_files, key=os.path.getctime)
            
            with open(latest_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading latest report: {e}")
            return self._create_default_report()
    
    def _create_default_report(self):
        """Create a default report when no data is available"""
        return {
            "timestamp": datetime.now().isoformat(),
            "environment": "dev",
            "drift_detected": False,
            "summary": {
                "total_issues": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0
            },
            "drift_details": [],
            "infrastructure_state": {
                "expected": {"containers": 0, "networks": 0, "volumes": 0},
                "actual": {"containers": 0, "networks": 0, "volumes": 0}
            }
        }
    
    def get_report_history(self, limit=10):
        """Get historical drift reports from database or files"""
        try:
            # Try database first
            if self.db:
                reports = self.db.get_reports(limit=limit)
                if reports:
                    return reports
            
            # Fallback to file system
            report_files = glob.glob(str(self.logs_dir / 'drift-report-*.json'))
            if not report_files:
                return []
                
            # Sort by creation time, most recent first
            report_files.sort(key=os.path.getctime, reverse=True)
            
            reports = []
            for file_path in report_files[:limit]:
                with open(file_path, 'r') as f:
                    report = json.load(f)
                    report['filename'] = os.path.basename(file_path)
                    reports.append(report)
            
            return reports
        except Exception as e:
            print(f"Error reading report history: {e}")
            return []
    
    def get_system_status(self):
        """Get current system status"""
        try:
            # Run a quick drift detection
            terraform_state = self.detector.get_terraform_state()
            docker_state = self.detector.get_docker_state()
            
            if not docker_state:
                return {
                    'status': 'error',
                    'message': 'Unable to fetch Docker state',
                    'terraform_available': terraform_state is not None,
                    'docker_available': False
                }
            
            # Get actual infrastructure data
            actual_infra = docker_state.get('actual_infrastructure', {})
            
            # Analyze drift if terraform state is available
            drift_detected = False
            drift_details = []
            
            if terraform_state:
                drift_detected, drift_details = self.detector.analyze_drift(terraform_state, docker_state)
                expected_infra = terraform_state.get('expected_infrastructure', {})
            else:
                # If no terraform state, show actual state without drift analysis
                expected_infra = {}
            
            # Get detailed container information
            containers_info = actual_infra.get('containers', {})
            containers_total = len(containers_info)
            containers_running = len([c for c in containers_info.values() if c.get('running', False)])
            containers_healthy = len([c for c in containers_info.values() if c.get('health_status') in ['healthy', 'none']])
            
            # Get network information
            networks_info = actual_infra.get('networks', {})
            networks_total = len(networks_info)
            
            # Get volume information  
            volumes_info = actual_infra.get('volumes', {})
            volumes_total = len(volumes_info)
            
            return {
                'status': 'healthy' if not drift_detected else 'drift',
                'drift_detected': drift_detected,
                'drift_count': len(drift_details),
                'last_check': datetime.now().isoformat(),
                'terraform_available': terraform_state is not None,
                'docker_available': True,
                'infrastructure': {
                    'expected': {
                        'containers': len(expected_infra.get('containers', {})),
                        'networks': len(expected_infra.get('networks', {})),
                        'volumes': len(expected_infra.get('volumes', {}))
                    },
                    'actual': {
                        'containers': containers_total,
                        'containers_running': containers_running,
                        'containers_healthy': containers_healthy,
                        'networks': networks_total,
                        'volumes': volumes_total
                    }
                },
                'detailed_info': {
                    'containers': [
                        {
                            'name': name,
                            'status': info.get('status', 'unknown'),
                            'running': info.get('running', False),
                            'image': info.get('image', '').split(':')[0] if ':' in info.get('image', '') else info.get('image', ''),
                            'health': info.get('health_status', 'none'),
                            'ports': len(info.get('ports', [])),
                            'networks': info.get('networks', [])
                        }
                        for name, info in containers_info.items()
                    ],
                    'networks': [
                        {
                            'name': name,
                            'driver': info.get('driver', ''),
                            'subnet': info.get('subnet', ''),
                            'containers': info.get('containers', 0)
                        }
                        for name, info in networks_info.items()
                    ],
                    'volumes': [
                        {
                            'name': name,
                            'driver': info.get('driver', ''),
                            'mountpoint': info.get('mountpoint', '')
                        }
                        for name, info in volumes_info.items()
                    ]
                }
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f'System status check failed: {str(e)}',
                'terraform_available': False,
                'docker_available': False
            }

# Initialize dashboard manager
dashboard = DashboardManager()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    """Get current system status"""
    return jsonify(dashboard.get_system_status())

@app.route('/api/latest-report')
def api_latest_report():
    """Get the latest drift report"""
    report = dashboard.get_latest_report()
    if report:
        return jsonify(report)
    else:
        return jsonify({'error': 'No drift reports found'}), 404

@app.route('/api/reports')
def api_reports():
    """Get drift report history"""
    limit = request.args.get('limit', 10, type=int)
    reports = dashboard.get_report_history(limit)
    return jsonify(reports)

@app.route('/api/run-check')
def api_run_check():
    """Trigger a manual drift detection check"""
    try:
        report = dashboard.detector.run_drift_detection()
        return jsonify({
            'success': True,
            'report': report,
            'message': 'Drift detection completed'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Drift detection failed'
        }), 500

@app.route('/api/containers')
def api_containers():
    """Get detailed container information"""
    try:
        docker_state = dashboard.detector.get_docker_state()
        if docker_state:
            containers = docker_state.get('actual_infrastructure', {}).get('containers', {})
            return jsonify({
                'success': True,
                'containers': containers,
                'count': len(containers)
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Unable to fetch container data'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/networks')
def api_networks():
    """Get detailed network information"""
    try:
        docker_state = dashboard.detector.get_docker_state()
        if docker_state:
            networks = docker_state.get('actual_infrastructure', {}).get('networks', {})
            return jsonify({
                'success': True,
                'networks': networks,
                'count': len(networks)
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Unable to fetch network data'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/infrastructure')
def api_infrastructure():
    """Get complete infrastructure overview"""
    try:
        status = dashboard.get_system_status()
        return jsonify({
            'success': True,
            'infrastructure': status.get('infrastructure', {}),
            'detailed_info': status.get('detailed_info', {}),
            'drift_detected': status.get('drift_detected', False),
            'drift_count': status.get('drift_count', 0)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'drift-detection-dashboard'
    })

if __name__ == '__main__':
    # Create logs directory if it doesn't exist
    dashboard.logs_dir.mkdir(exist_ok=True)
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)