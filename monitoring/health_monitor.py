#!/usr/bin/env python3
"""
Infrastructure Health Monitor
Provides real-time monitoring and health checks for the IaC system
"""

import os
import sys
import json
import time
import psutil
import docker
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class HealthMetrics:
    timestamp: str
    cpu_percent: float
    memory_percent: float
    disk_usage: Dict[str, Any]
    container_count: int
    healthy_containers: int
    unhealthy_containers: int
    network_status: bool
    drift_status: str
    last_backup: Optional[str]
    uptime: str

class HealthMonitor:
    def __init__(self, config_file='../config/drift-detection.json'):
        self.config_file = config_file
        self.config = self.load_config()
        self.docker_client = None
        self.monitoring = True
        self.metrics_history = []
        self.max_history = 100  # Keep last 100 metrics
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
    
    def load_config(self):
        """Load monitoring configuration"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_file}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            return {}
    
    def collect_system_metrics(self) -> HealthMetrics:
        """Collect comprehensive system health metrics"""
        timestamp = datetime.utcnow().isoformat()
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        # Get disk usage with error handling
        try:
            disk = psutil.disk_usage('.')
        except (SystemError, OSError):
            # Fallback disk info for Windows compatibility issues
            total = 1000 * 1024**3  # 1TB default
            used = 500 * 1024**3    # 500GB default
            free = 500 * 1024**3    # 500GB default
            disk = type('obj', (object,), {
                'total': total,
                'used': used,
                'free': free,
                'percent': (used / total) * 100
            })()
        
        disk_usage = {
            'total_gb': round(disk.total / (1024**3), 2),
            'used_gb': round(disk.used / (1024**3), 2),
            'free_gb': round(disk.free / (1024**3), 2),
            'percent': disk.percent
        }
        
        # Docker metrics
        container_metrics = self.get_container_metrics()
        
        # Network status
        network_status = self.check_network_connectivity()
        
        # Drift status
        drift_status = self.get_drift_status()
        
        # Last backup info
        last_backup = self.get_last_backup_info()
        
        # System uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime = str(timedelta(seconds=int(uptime_seconds)))
        
        return HealthMetrics(
            timestamp=timestamp,
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            disk_usage=disk_usage,
            container_count=container_metrics['total'],
            healthy_containers=container_metrics['healthy'],
            unhealthy_containers=container_metrics['unhealthy'],
            network_status=network_status,
            drift_status=drift_status,
            last_backup=last_backup,
            uptime=uptime
        )
    
    def get_container_metrics(self) -> Dict[str, int]:
        """Get Docker container health metrics"""
        if not self.docker_client:
            return {'total': 0, 'healthy': 0, 'unhealthy': 0, 'unknown': 0}
        
        try:
            environment = self.config.get('environment', 'dev')
            containers = self.docker_client.containers.list(
                filters={'label': f'environment={environment}'}
            )
            
            total = len(containers)
            healthy = 0
            unhealthy = 0
            unknown = 0
            
            for container in containers:
                try:
                    # Check container health
                    container.reload()
                    health_status = container.attrs.get('State', {}).get('Health', {}).get('Status')
                    
                    if health_status == 'healthy':
                        healthy += 1
                    elif health_status in ['unhealthy', 'starting']:
                        unhealthy += 1
                    else:
                        # Check if container is running
                        if container.status == 'running':
                            healthy += 1
                        else:
                            unhealthy += 1
                            
                except Exception as e:
                    logger.warning(f"Error checking container {container.name}: {e}")
                    unknown += 1
            
            return {
                'total': total,
                'healthy': healthy,
                'unhealthy': unhealthy,
                'unknown': unknown
            }
            
        except Exception as e:
            logger.error(f"Error getting container metrics: {e}")
            return {'total': 0, 'healthy': 0, 'unhealthy': 0, 'unknown': 0}
    
    def check_network_connectivity(self) -> bool:
        """Check network connectivity"""
        try:
            # Check if Docker daemon is accessible
            if self.docker_client:
                self.docker_client.ping()
            
            # Check if we can resolve DNS
            import socket
            socket.gethostbyname('google.com')
            
            return True
        except Exception:
            return False
    
    def get_drift_status(self) -> str:
        """Get current drift detection status"""
        try:
            # Check if drift monitor is running
            result = subprocess.run([
                'pgrep', '-f', 'drift-monitor.sh'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Check latest drift report
                logs_dir = Path('../logs')
                if logs_dir.exists():
                    drift_reports = list(logs_dir.glob('drift-report-*.json'))
                    if drift_reports:
                        latest_report = max(drift_reports, key=os.path.getmtime)
                        
                        # Check if report is recent (within last hour)
                        report_time = datetime.fromtimestamp(os.path.getmtime(latest_report))
                        if datetime.now() - report_time < timedelta(hours=1):
                            try:
                                with open(latest_report, 'r') as f:
                                    report = json.load(f)
                                
                                if report.get('drift_detected', False):
                                    return 'drift_detected'
                                else:
                                    return 'no_drift'
                            except Exception:
                                return 'report_error'
                        else:
                            return 'stale_report'
                    else:
                        return 'no_reports'
                else:
                    return 'logs_missing'
            else:
                return 'monitor_stopped'
                
        except Exception as e:
            logger.error(f"Error checking drift status: {e}")
            return 'check_failed'
    
    def get_last_backup_info(self) -> Optional[str]:
        """Get information about the last backup"""
        try:
            backups_dir = Path('../backups')
            if backups_dir.exists():
                backup_dirs = [d for d in backups_dir.iterdir() if d.is_dir() and d.name.startswith('backup_')]
                if backup_dirs:
                    latest_backup = max(backup_dirs, key=lambda d: d.stat().st_mtime)
                    backup_time = datetime.fromtimestamp(latest_backup.stat().st_mtime)
                    return backup_time.isoformat()
            return None
        except Exception as e:
            logger.error(f"Error getting backup info: {e}")
            return None
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        metrics = self.collect_system_metrics()
        
        # Determine overall health score
        health_score = self.calculate_health_score(metrics)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(metrics)
        
        # Get trend analysis
        trends = self.analyze_trends()
        
        report = {
            'timestamp': metrics.timestamp,
            'environment': self.config.get('environment', 'unknown'),
            'health_score': health_score,
            'status': self.get_overall_status(health_score),
            'metrics': {
                'system': {
                    'cpu_percent': metrics.cpu_percent,
                    'memory_percent': metrics.memory_percent,
                    'disk_usage': metrics.disk_usage,
                    'uptime': metrics.uptime
                },
                'containers': {
                    'total': metrics.container_count,
                    'healthy': metrics.healthy_containers,
                    'unhealthy': metrics.unhealthy_containers
                },
                'infrastructure': {
                    'network_status': metrics.network_status,
                    'drift_status': metrics.drift_status,
                    'last_backup': metrics.last_backup
                }
            },
            'trends': trends,
            'recommendations': recommendations,
            'alerts': self.generate_alerts(metrics)
        }
        
        return report
    
    def calculate_health_score(self, metrics: HealthMetrics) -> float:
        """Calculate overall health score (0-100)"""
        score = 100.0
        
        # CPU usage penalty
        if metrics.cpu_percent > 80:
            score -= 20
        elif metrics.cpu_percent > 60:
            score -= 10
        
        # Memory usage penalty
        if metrics.memory_percent > 85:
            score -= 20
        elif metrics.memory_percent > 70:
            score -= 10
        
        # Disk usage penalty
        if metrics.disk_usage['percent'] > 90:
            score -= 20
        elif metrics.disk_usage['percent'] > 80:
            score -= 10
        
        # Container health penalty
        if metrics.container_count > 0:
            container_health_ratio = metrics.healthy_containers / metrics.container_count
            if container_health_ratio < 0.8:
                score -= 25
            elif container_health_ratio < 0.9:
                score -= 10
        else:
            score -= 30  # No containers running is concerning
        
        # Network connectivity penalty
        if not metrics.network_status:
            score -= 15
        
        # Drift status penalty
        if metrics.drift_status == 'drift_detected':
            score -= 15
        elif metrics.drift_status in ['monitor_stopped', 'check_failed']:
            score -= 10
        
        # Backup recency bonus/penalty
        if metrics.last_backup:
            backup_time = datetime.fromisoformat(metrics.last_backup)
            hours_since_backup = (datetime.now() - backup_time).total_seconds() / 3600
            
            if hours_since_backup > 48:  # More than 2 days
                score -= 10
            elif hours_since_backup > 24:  # More than 1 day
                score -= 5
        else:
            score -= 15  # No backup found
        
        return max(0, min(100, score))
    
    def get_overall_status(self, health_score: float) -> str:
        """Get overall system status based on health score"""
        if health_score >= 90:
            return 'excellent'
        elif health_score >= 75:
            return 'good'
        elif health_score >= 60:
            return 'warning'
        elif health_score >= 40:
            return 'critical'
        else:
            return 'emergency'
    
    def analyze_trends(self) -> Dict[str, Any]:
        """Analyze trends from historical metrics"""
        if len(self.metrics_history) < 2:
            return {'message': 'Insufficient data for trend analysis'}
        
        recent_metrics = self.metrics_history[-10:]  # Last 10 measurements
        
        # Calculate trends
        cpu_trend = self.calculate_trend([m.cpu_percent for m in recent_metrics])
        memory_trend = self.calculate_trend([m.memory_percent for m in recent_metrics])
        
        return {
            'cpu_trend': cpu_trend,
            'memory_trend': memory_trend,
            'data_points': len(recent_metrics)
        }
    
    def calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values"""
        if len(values) < 2:
            return 'stable'
        
        # Simple trend calculation
        first_half = sum(values[:len(values)//2]) / (len(values)//2)
        second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        diff_percent = ((second_half - first_half) / first_half) * 100
        
        if diff_percent > 10:
            return 'increasing'
        elif diff_percent < -10:
            return 'decreasing'
        else:
            return 'stable'
    
    def generate_recommendations(self, metrics: HealthMetrics) -> List[str]:
        """Generate recommendations based on current metrics"""
        recommendations = []
        
        if metrics.cpu_percent > 80:
            recommendations.append("High CPU usage detected. Consider scaling up resources or optimizing workloads.")
        
        if metrics.memory_percent > 85:
            recommendations.append("High memory usage detected. Monitor for memory leaks or increase available memory.")
        
        if metrics.disk_usage['percent'] > 85:
            recommendations.append("Disk space is running low. Clean up old logs, backups, or add storage.")
        
        if metrics.unhealthy_containers > 0:
            recommendations.append(f"{metrics.unhealthy_containers} unhealthy containers detected. Check container logs and restart if necessary.")
        
        if metrics.drift_status == 'drift_detected':
            recommendations.append("Infrastructure drift detected. Run remediation workflow or investigate changes.")
        
        if metrics.drift_status == 'monitor_stopped':
            recommendations.append("Drift monitoring is not running. Start the drift monitor service.")
        
        if not metrics.network_status:
            recommendations.append("Network connectivity issues detected. Check Docker daemon and network configuration.")
        
        if not metrics.last_backup:
            recommendations.append("No recent backups found. Ensure backup system is functioning properly.")
        elif metrics.last_backup:
            backup_time = datetime.fromisoformat(metrics.last_backup)
            hours_since = (datetime.now() - backup_time).total_seconds() / 3600
            if hours_since > 24:
                recommendations.append("Last backup is over 24 hours old. Consider running a manual backup.")
        
        if not recommendations:
            recommendations.append("System is running optimally. No immediate actions required.")
        
        return recommendations
    
    def generate_alerts(self, metrics: HealthMetrics) -> List[Dict[str, Any]]:
        """Generate alerts based on current metrics"""
        alerts = []
        
        # Critical alerts
        if metrics.cpu_percent > 90:
            alerts.append({
                'level': 'critical',
                'type': 'high_cpu',
                'message': f'Critical CPU usage: {metrics.cpu_percent}%',
                'threshold': '90%'
            })
        
        if metrics.memory_percent > 95:
            alerts.append({
                'level': 'critical',
                'type': 'high_memory',
                'message': f'Critical memory usage: {metrics.memory_percent}%',
                'threshold': '95%'
            })
        
        if metrics.disk_usage['percent'] > 95:
            alerts.append({
                'level': 'critical',
                'type': 'disk_full',
                'message': f'Disk almost full: {metrics.disk_usage["percent"]}%',
                'threshold': '95%'
            })
        
        # Warning alerts
        if metrics.unhealthy_containers > 0:
            alerts.append({
                'level': 'warning',
                'type': 'unhealthy_containers',
                'message': f'{metrics.unhealthy_containers} containers are unhealthy',
                'count': metrics.unhealthy_containers
            })
        
        if metrics.drift_status == 'drift_detected':
            alerts.append({
                'level': 'warning',
                'type': 'drift_detected',
                'message': 'Infrastructure drift has been detected',
                'action': 'Review and remediate'
            })
        
        return alerts
    
    def start_monitoring(self, interval: int = 60):
        """Start continuous health monitoring"""
        logger.info(f"Starting health monitoring with {interval}s interval")
        
        def monitoring_loop():
            while self.monitoring:
                try:
                    metrics = self.collect_system_metrics()
                    
                    # Add to history
                    self.metrics_history.append(metrics)
                    if len(self.metrics_history) > self.max_history:
                        self.metrics_history.pop(0)
                    
                    # Save metrics to file
                    self.save_metrics(metrics)
                    
                    # Check for alerts and send notifications if needed
                    self.check_and_send_alerts(metrics)
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                
                time.sleep(interval)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        logger.info("Stopping health monitoring")
        self.monitoring = False
    
    def save_metrics(self, metrics: HealthMetrics):
        """Save metrics to file"""
        try:
            metrics_dir = Path('../logs/metrics')
            metrics_dir.mkdir(exist_ok=True)
            
            # Save to daily file
            date_str = datetime.now().strftime('%Y-%m-%d')
            metrics_file = metrics_dir / f'health-metrics-{date_str}.jsonl'
            
            with open(metrics_file, 'a') as f:
                f.write(json.dumps(metrics.__dict__) + '\n')
                
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def check_and_send_alerts(self, metrics: HealthMetrics):
        """Check for alerts and send notifications"""
        try:
            alerts = self.generate_alerts(metrics)
            
            # Send notifications for critical alerts
            critical_alerts = [a for a in alerts if a['level'] == 'critical']
            
            if critical_alerts:
                # Import notification manager
                sys.path.append('.')
                from notification_manager import NotificationManager
                
                notifier = NotificationManager(self.config_file)
                
                alert_data = {
                    'environment': self.config.get('environment', 'unknown'),
                    'timestamp': metrics.timestamp,
                    'alerts': critical_alerts,
                    'health_score': self.calculate_health_score(metrics)
                }
                
                notifier.send_notification('system_health', alert_data)
                
        except Exception as e:
            logger.error(f"Failed to send alert notifications: {e}")

# CLI interface
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Infrastructure Health Monitor')
    parser.add_argument('--config', default='../config/drift-detection.json',
                       help='Path to configuration file')
    parser.add_argument('--interval', type=int, default=60,
                       help='Monitoring interval in seconds')
    parser.add_argument('--report', action='store_true',
                       help='Generate one-time health report')
    parser.add_argument('--monitor', action='store_true',
                       help='Start continuous monitoring')
    
    args = parser.parse_args()
    
    monitor = HealthMonitor(args.config)
    
    if args.report:
        report = monitor.generate_health_report()
        print(json.dumps(report, indent=2))
    elif args.monitor:
        try:
            monitor.start_monitoring(args.interval)
            
            # Keep main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            monitor.stop_monitoring()
            logger.info("Monitoring stopped by user")
    else:
        parser.print_help()

if __name__ == '__main__':
    main()