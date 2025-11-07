#!/usr/bin/env python3
"""
IaC Drift Detection Script
This script detects configuration drift between desired and actual infrastructure state
"""

import os
import sys
import json
import subprocess
import argparse
import logging
from datetime import datetime
from pathlib import Path
import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs', 'drift-detection.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DriftDetector:
    def __init__(self, config_file=None):
        if config_file is None:
            # Get absolute path to config file from script location
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_file = os.path.join(script_dir, 'config', 'drift-detection.json')
        self.config_file = config_file
        self.config = self.load_config()
        terraform_dir = self.config.get('terraform', {}).get('config_dir', '../../terraform')
        # Convert relative path to absolute path
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.terraform_dir = os.path.join(script_dir, 'terraform')
        
    def load_config(self):
        """Load drift detection configuration"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_file}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return {}
    
    def get_terraform_state(self):
        """Get current Terraform state"""
        try:
            current_dir = os.getcwd()
            os.chdir(self.terraform_dir)
            
            # Use terraform from PATH
            terraform_cmd = 'terraform'
            result = subprocess.run(
                [terraform_cmd, 'show', '-json'],
                capture_output=True,
                text=True,
                check=True
            )
            
            state_data = json.loads(result.stdout)
            
            # Extract expected infrastructure configuration from state
            expected_infrastructure = self.extract_expected_infrastructure(state_data)
            
            return {
                'raw_state': state_data,
                'expected_infrastructure': expected_infrastructure
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get Terraform state: {e.stderr}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Terraform state JSON: {e}")
            return None
        finally:
            os.chdir(current_dir)
    
    def extract_expected_infrastructure(self, state_data):
        """Extract expected infrastructure configuration from Terraform state"""
        expected = {
            'containers': {},
            'networks': {},
            'volumes': {},
            'images': {}
        }
        
        if not state_data or 'values' not in state_data:
            return expected
            
        resources = state_data.get('values', {}).get('root_module', {}).get('resources', [])
        
        for resource in resources:
            resource_type = resource.get('type')
            resource_name = resource.get('name')
            values = resource.get('values', {})
            
            if resource_type == 'docker_container':
                container_name = values.get('name')
                if container_name:
                    expected['containers'][container_name] = {
                        'name': container_name,
                        'image': values.get('image', '').split('sha256:')[0] if 'sha256:' in values.get('image', '') else values.get('image', ''),
                        'ports': values.get('ports', []),
                        'env': values.get('env', []),
                        'networks': [net.get('name') for net in values.get('networks_advanced', [])],
                        'restart': values.get('restart', ''),
                        'status': 'running' if values.get('must_run', False) else 'created'
                    }
            
            elif resource_type == 'docker_network':
                network_name = values.get('name')
                if network_name:
                    expected['networks'][network_name] = {
                        'name': network_name,
                        'driver': values.get('driver', ''),
                        'subnet': values.get('ipam_config', [{}])[0].get('subnet', '') if values.get('ipam_config') else ''
                    }
            
            elif resource_type == 'docker_volume':
                volume_name = values.get('name')
                if volume_name:
                    expected['volumes'][volume_name] = {
                        'name': volume_name,
                        'driver': values.get('driver', '')
                    }
            
            elif resource_type == 'docker_image':
                image_name = values.get('name')
                if image_name:
                    expected['images'][image_name] = {
                        'name': image_name,
                        'repo_digest': values.get('repo_digest', ''),
                        'image_id': values.get('image_id', '')
                    }
        
        return expected
    
    def get_terraform_plan(self):
        """Generate and analyze Terraform plan for drift detection"""
        try:
            current_dir = os.getcwd()
            os.chdir(self.terraform_dir)
            
            # Use the local terraform executable
            terraform_cmd = '.\\terraform.exe' if os.name == 'nt' else './terraform'
            
            # Generate plan
            plan_result = subprocess.run(
                [terraform_cmd, 'plan', '-detailed-exitcode', '-out=drift-plan.tfplan'],
                capture_output=True,
                text=True
            )
            
            # Convert plan to JSON
            json_result = subprocess.run(
                [terraform_cmd, 'show', '-json', 'drift-plan.tfplan'],
                capture_output=True,
                text=True,
                check=True
            )
            
            plan_data = json.loads(json_result.stdout)
            
            # Clean up plan file
            if os.path.exists('drift-plan.tfplan'):
                os.remove('drift-plan.tfplan')
            
            return {
                'exit_code': plan_result.returncode,
                'stdout': plan_result.stdout,
                'stderr': plan_result.stderr,
                'plan_data': plan_data
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate Terraform plan: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse plan JSON: {e}")
            return None
        finally:
            os.chdir(current_dir)
    
    def get_docker_state(self):
        """Get current Docker infrastructure state"""
        try:
            environment = self.config.get('environment', 'dev')
            project_name = 'iac-drift-detection'
            
            # Get detailed container information
            actual_infrastructure = {
                'containers': {},
                'networks': {},
                'volumes': {},
                'images': {}
            }
            
            # Get all containers for this project (not just running ones)
            containers_result = subprocess.run(
                ['docker', 'ps', '-a', '--format', 'json', '--filter', f'name={project_name}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if containers_result.stdout.strip():
                for line in containers_result.stdout.strip().split('\n'):
                    if line.strip():
                        container_info = json.loads(line)
                        container_name = container_info.get('Names', '')
                        
                        # Get detailed container inspection
                        inspect_result = subprocess.run(
                            ['docker', 'inspect', container_name],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        
                        if inspect_result.stdout:
                            container_details = json.loads(inspect_result.stdout)[0]
                            
                            actual_infrastructure['containers'][container_name] = {
                                'name': container_name,
                                'image': container_details.get('Config', {}).get('Image', ''),
                                'status': container_details.get('State', {}).get('Status', ''),
                                'running': container_details.get('State', {}).get('Running', False),
                                'ports': self.extract_container_ports(container_details),
                                'env': container_details.get('Config', {}).get('Env', []),
                                'networks': list(container_details.get('NetworkSettings', {}).get('Networks', {}).keys()),
                                'restart_policy': container_details.get('HostConfig', {}).get('RestartPolicy', {}),
                                'created': container_details.get('Created', ''),
                                'started_at': container_details.get('State', {}).get('StartedAt', ''),
                                'health_status': container_details.get('State', {}).get('Health', {}).get('Status', 'none')
                            }
            
            # Get networks for this project
            networks_result = subprocess.run(
                ['docker', 'network', 'ls', '--format', 'json', '--filter', f'name={project_name}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if networks_result.stdout.strip():
                for line in networks_result.stdout.strip().split('\n'):
                    if line.strip():
                        network_info = json.loads(line)
                        network_name = network_info.get('Name', '')
                        
                        # Get detailed network inspection
                        inspect_result = subprocess.run(
                            ['docker', 'network', 'inspect', network_name],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        
                        if inspect_result.stdout:
                            network_details = json.loads(inspect_result.stdout)[0]
                            ipam_config = network_details.get('IPAM', {}).get('Config', [])
                            subnet = ipam_config[0].get('Subnet', '') if ipam_config else ''
                            
                            actual_infrastructure['networks'][network_name] = {
                                'name': network_name,
                                'driver': network_details.get('Driver', ''),
                                'subnet': subnet,
                                'created': network_details.get('Created', ''),
                                'containers': len(network_details.get('Containers', {}))
                            }
            
            # Get volumes for this project
            volumes_result = subprocess.run(
                ['docker', 'volume', 'ls', '--format', 'json', '--filter', f'name={project_name}'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if volumes_result.stdout.strip():
                for line in volumes_result.stdout.strip().split('\n'):
                    if line.strip():
                        volume_info = json.loads(line)
                        volume_name = volume_info.get('Name', '')
                        
                        # Get detailed volume inspection
                        inspect_result = subprocess.run(
                            ['docker', 'volume', 'inspect', volume_name],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        
                        if inspect_result.stdout:
                            volume_details = json.loads(inspect_result.stdout)[0]
                            
                            actual_infrastructure['volumes'][volume_name] = {
                                'name': volume_name,
                                'driver': volume_details.get('Driver', ''),
                                'mountpoint': volume_details.get('Mountpoint', ''),
                                'created': volume_details.get('CreatedAt', '')
                            }
            
            return {
                'actual_infrastructure': actual_infrastructure,
                'timestamp': datetime.utcnow().isoformat(),
                'environment': environment
            }
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get Docker state: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Docker output: {e}")
            return None
    
    def extract_container_ports(self, container_details):
        """Extract port mappings from container details"""
        ports = []
        port_bindings = container_details.get('HostConfig', {}).get('PortBindings', {})
        
        for internal_port, bindings in port_bindings.items():
            if bindings:
                for binding in bindings:
                    ports.append({
                        'internal': int(internal_port.split('/')[0]),
                        'external': int(binding.get('HostPort', 0)),
                        'protocol': internal_port.split('/')[1] if '/' in internal_port else 'tcp',
                        'ip': binding.get('HostIp', '0.0.0.0')
                    })
        
        return ports
    
    def analyze_drift(self, terraform_state, docker_state):
        """Analyze drift between desired and actual state"""
        drift_detected = False
        drift_details = []
        
        if not terraform_state or not docker_state:
            logger.error("Missing terraform state or docker state for analysis")
            return False, []
        
        expected_infrastructure = terraform_state.get('expected_infrastructure', {})
        actual_infrastructure = docker_state.get('actual_infrastructure', {})
        
        # Analyze container drift
        drift_detected_containers, container_drift = self.analyze_container_drift(
            expected_infrastructure.get('containers', {}),
            actual_infrastructure.get('containers', {})
        )
        
        if drift_detected_containers:
            drift_detected = True
            drift_details.extend(container_drift)
        
        # Analyze network drift
        drift_detected_networks, network_drift = self.analyze_network_drift(
            expected_infrastructure.get('networks', {}),
            actual_infrastructure.get('networks', {})
        )
        
        if drift_detected_networks:
            drift_detected = True
            drift_details.extend(network_drift)
        
        # Analyze volume drift
        drift_detected_volumes, volume_drift = self.analyze_volume_drift(
            expected_infrastructure.get('volumes', {}),
            actual_infrastructure.get('volumes', {})
        )
        
        if drift_detected_volumes:
            drift_detected = True
            drift_details.extend(volume_drift)
        
        return drift_detected, drift_details
    
    def analyze_container_drift(self, expected_containers, actual_containers):
        """Analyze drift in container configuration"""
        drift_detected = False
        drift_details = []
        
        # Check for missing containers
        for expected_name, expected_config in expected_containers.items():
            if expected_name not in actual_containers:
                drift_detected = True
                drift_details.append({
                    'type': 'missing_container',
                    'severity': 'high',
                    'resource': expected_name,
                    'message': f'Expected container {expected_name} not found',
                    'expected': expected_config,
                    'actual': None
                })
            else:
                actual_config = actual_containers[expected_name]
                
                # Check container status
                if expected_config.get('status') == 'running' and not actual_config.get('running', False):
                    drift_detected = True
                    drift_details.append({
                        'type': 'container_status_drift',
                        'severity': 'high',
                        'resource': expected_name,
                        'message': f'Container {expected_name} is not running',
                        'expected': 'running',
                        'actual': actual_config.get('status', 'unknown')
                    })
                
                # Check image drift
                expected_image = expected_config.get('image', '').split(':')[0]  # Remove tag/hash
                actual_image = actual_config.get('image', '').split(':')[0]
                
                if expected_image and actual_image and expected_image not in actual_image:
                    drift_detected = True
                    drift_details.append({
                        'type': 'image_drift',
                        'severity': 'medium',
                        'resource': expected_name,
                        'message': f'Container {expected_name} has image drift',
                        'expected': expected_config.get('image'),
                        'actual': actual_config.get('image')
                    })
                
                # Check port configuration
                expected_ports = expected_config.get('ports', [])
                actual_ports = actual_config.get('ports', [])
                
                if len(expected_ports) != len(actual_ports):
                    drift_detected = True
                    drift_details.append({
                        'type': 'port_count_drift',
                        'severity': 'medium',
                        'resource': expected_name,
                        'message': f'Container {expected_name} has port count mismatch',
                        'expected': len(expected_ports),
                        'actual': len(actual_ports)
                    })
                
                # Check restart policy
                expected_restart = expected_config.get('restart', '')
                actual_restart = actual_config.get('restart_policy', {}).get('Name', '')
                
                if expected_restart and expected_restart != actual_restart:
                    drift_detected = True
                    drift_details.append({
                        'type': 'restart_policy_drift',
                        'severity': 'low',
                        'resource': expected_name,
                        'message': f'Container {expected_name} has restart policy drift',
                        'expected': expected_restart,
                        'actual': actual_restart
                    })
                
                # Check health status
                health_status = actual_config.get('health_status', 'none')
                if health_status not in ['healthy', 'none'] and actual_config.get('running'):
                    drift_detected = True
                    drift_details.append({
                        'type': 'health_drift',
                        'severity': 'high',
                        'resource': expected_name,
                        'message': f'Container {expected_name} is unhealthy',
                        'expected': 'healthy',
                        'actual': health_status
                    })
        
        # Check for unexpected containers
        for actual_name in actual_containers.keys():
            if actual_name not in expected_containers:
                drift_detected = True
                drift_details.append({
                    'type': 'unexpected_container',
                    'severity': 'medium',
                    'resource': actual_name,
                    'message': f'Unexpected container {actual_name} found',
                    'expected': None,
                    'actual': actual_containers[actual_name]
                })
        
        return drift_detected, drift_details
    
    def analyze_network_drift(self, expected_networks, actual_networks):
        """Analyze drift in network configuration"""
        drift_detected = False
        drift_details = []
        
        # Check for missing networks
        for expected_name, expected_config in expected_networks.items():
            if expected_name not in actual_networks:
                drift_detected = True
                drift_details.append({
                    'type': 'missing_network',
                    'severity': 'high',
                    'resource': expected_name,
                    'message': f'Expected network {expected_name} not found',
                    'expected': expected_config,
                    'actual': None
                })
            else:
                actual_config = actual_networks[expected_name]
                
                # Check driver
                expected_driver = expected_config.get('driver', '')
                actual_driver = actual_config.get('driver', '')
                
                if expected_driver and expected_driver != actual_driver:
                    drift_detected = True
                    drift_details.append({
                        'type': 'network_driver_drift',
                        'severity': 'medium',
                        'resource': expected_name,
                        'message': f'Network {expected_name} has driver mismatch',
                        'expected': expected_driver,
                        'actual': actual_driver
                    })
                
                # Check subnet
                expected_subnet = expected_config.get('subnet', '')
                actual_subnet = actual_config.get('subnet', '')
                
                if expected_subnet and expected_subnet != actual_subnet:
                    drift_detected = True
                    drift_details.append({
                        'type': 'network_subnet_drift',
                        'severity': 'medium',
                        'resource': expected_name,
                        'message': f'Network {expected_name} has subnet mismatch',
                        'expected': expected_subnet,
                        'actual': actual_subnet
                    })
        
        # Check for unexpected networks
        for actual_name in actual_networks.keys():
            if actual_name not in expected_networks:
                drift_detected = True
                drift_details.append({
                    'type': 'unexpected_network',
                    'severity': 'low',
                    'resource': actual_name,
                    'message': f'Unexpected network {actual_name} found',
                    'expected': None,
                    'actual': actual_networks[actual_name]
                })
        
        return drift_detected, drift_details
    
    def analyze_volume_drift(self, expected_volumes, actual_volumes):
        """Analyze drift in volume configuration"""
        drift_detected = False
        drift_details = []
        
        # Check for missing volumes
        for expected_name, expected_config in expected_volumes.items():
            if expected_name not in actual_volumes:
                drift_detected = True
                drift_details.append({
                    'type': 'missing_volume',
                    'severity': 'medium',
                    'resource': expected_name,
                    'message': f'Expected volume {expected_name} not found',
                    'expected': expected_config,
                    'actual': None
                })
            else:
                actual_config = actual_volumes[expected_name]
                
                # Check driver
                expected_driver = expected_config.get('driver', '')
                actual_driver = actual_config.get('driver', '')
                
                if expected_driver and expected_driver != actual_driver:
                    drift_detected = True
                    drift_details.append({
                        'type': 'volume_driver_drift',
                        'severity': 'low',
                        'resource': expected_name,
                        'message': f'Volume {expected_name} has driver mismatch',
                        'expected': expected_driver,
                        'actual': actual_driver
                    })
        
        # Check for unexpected volumes
        for actual_name in actual_volumes.keys():
            if actual_name not in expected_volumes:
                drift_detected = True
                drift_details.append({
                    'type': 'unexpected_volume',
                    'severity': 'low',
                    'resource': actual_name,
                    'message': f'Unexpected volume {actual_name} found',
                    'expected': None,
                    'actual': actual_volumes[actual_name]
                })
        
        return drift_detected, drift_details
    
    def generate_drift_report(self, drift_detected, drift_details, terraform_state, docker_state):
        """Generate comprehensive drift report"""
        
        # Extract infrastructure summaries
        expected_infra = terraform_state.get('expected_infrastructure', {}) if terraform_state else {}
        actual_infra = docker_state.get('actual_infrastructure', {}) if docker_state else {}
        
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'environment': self.config.get('environment', 'dev'),
            'drift_detected': drift_detected,
            'summary': {
                'total_issues': len(drift_details),
                'high_severity': len([d for d in drift_details if d.get('severity') == 'high']),
                'medium_severity': len([d for d in drift_details if d.get('severity') == 'medium']),
                'low_severity': len([d for d in drift_details if d.get('severity') == 'low'])
            },
            'drift_details': drift_details,
            'infrastructure_state': {
                'expected': {
                    'containers': len(expected_infra.get('containers', {})),
                    'networks': len(expected_infra.get('networks', {})),
                    'volumes': len(expected_infra.get('volumes', {})),
                    'images': len(expected_infra.get('images', {}))
                },
                'actual': {
                    'containers': len(actual_infra.get('containers', {})),
                    'containers_running': len([c for c in actual_infra.get('containers', {}).values() if c.get('running', False)]),
                    'networks': len(actual_infra.get('networks', {})),
                    'volumes': len(actual_infra.get('volumes', {}))
                }
            },
            'raw_data': {
                'terraform_state_available': terraform_state is not None,
                'docker_state_available': docker_state is not None,
                'last_check': datetime.utcnow().isoformat()
            }
        }
        
        return report
    
    def save_report(self, report):
        """Save drift report to file and database"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_file = f'../logs/drift-report-{timestamp}.json'
        
        try:
            # Save to file
            os.makedirs('../logs', exist_ok=True)
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Drift report saved to {report_file}")
            
            # Save to database
            try:
                # Add database directory to path
                script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                database_dir = os.path.join(script_dir, 'database')
                sys.path.append(database_dir)
                from drift_database import DriftDatabase
                
                db_path = os.path.join(script_dir, 'data', 'drift_detection.db')
                db = DriftDatabase(db_path)
                report_id = db.store_report(report)
                logger.info(f"Drift report saved to database with ID: {report_id}")
                
            except ImportError as e:
                logger.warning(f"Database storage not available: {e}")
            except Exception as e:
                logger.error(f"Failed to save to database: {e}")
            
            return report_file
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            return None
    
    def send_notification(self, report):
        """Send drift notification if configured"""
        webhook_url = self.config.get('monitoring', {}).get('webhook_url')
        
        if not webhook_url:
            logger.info("No webhook URL configured, skipping notification")
            return
        
        message = self.format_notification_message(report)
        
        try:
            import requests
            
            payload = {
                'text': message,
                'username': 'IaC Drift Detector',
                'icon_emoji': ':warning:' if report['drift_detected'] else ':white_check_mark:'
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("Notification sent successfully")
            
        except ImportError:
            logger.warning("requests library not available, cannot send webhook notification")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    def format_notification_message(self, report):
        """Format notification message"""
        if report['drift_detected']:
            message = f"🚨 *IaC Drift Detected* - {report['environment'].upper()}\n\n"
            message += f"**Summary:**\n"
            message += f"• Total Issues: {report['summary']['total_issues']}\n"
            message += f"• High Severity: {report['summary']['high_severity']}\n"
            message += f"• Medium Severity: {report['summary']['medium_severity']}\n\n"
            
            for detail in report['drift_details'][:5]:  # Show first 5 issues
                severity_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}.get(detail.get('severity', 'low'), '⚪')
                message += f"{severity_emoji} {detail.get('message', 'Unknown issue')}\n"
            
            if len(report['drift_details']) > 5:
                message += f"... and {len(report['drift_details']) - 5} more issues\n"
                
        else:
            message = f"✅ *No Drift Detected* - {report['environment'].upper()}\n\n"
            message += "Infrastructure is in sync with desired state."
        
        message += f"\nTimestamp: {report['timestamp']}"
        return message
    
    def run_drift_detection(self):
        """Main drift detection workflow"""
        logger.info("Starting drift detection...")
        
        # Get current states
        logger.info("Getting Terraform state...")
        terraform_state = self.get_terraform_state()
        
        logger.info("Getting Docker state...")
        docker_state = self.get_docker_state()
        
        # Analyze drift
        logger.info("Analyzing drift...")
        drift_detected, drift_details = self.analyze_drift(terraform_state, docker_state)
        
        # Generate report
        report = self.generate_drift_report(drift_detected, drift_details, terraform_state, docker_state)
        
        # Save report
        report_file = self.save_report(report)
        
        # Send notification
        if drift_detected or self.config.get('monitoring', {}).get('always_notify', False):
            self.send_notification(report)
        
        # Print summary
        if drift_detected:
            logger.warning(f"Drift detected! {len(drift_details)} issues found.")
            for detail in drift_details:
                logger.warning(f"  - {detail.get('message', 'Unknown issue')}")
        else:
            logger.info("No drift detected. Infrastructure is in sync.")
        
        return report

def main():
    parser = argparse.ArgumentParser(description='IaC Drift Detection Tool')
    parser.add_argument('--config', default='../config/drift-detection.json',
                       help='Path to configuration file')
    parser.add_argument('--output', help='Output file for drift report')
    parser.add_argument('--quiet', action='store_true', help='Suppress console output')
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    
    detector = DriftDetector(args.config)
    report = detector.run_drift_detection()
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"Report saved to {args.output}")
    
    # Exit with appropriate code
    sys.exit(1 if report['drift_detected'] else 0)

if __name__ == '__main__':
    main()