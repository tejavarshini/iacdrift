#!/usr/bin/env python3
"""
Create Working Perfectly Scenarios
Generate scenarios showing different states: working perfectly, minor issues, major problems
"""

import os
import sys
import json
from datetime import datetime, timedelta
import random

# Add the database directory to path
script_dir = os.path.dirname(os.path.dirname(__file__))
database_dir = os.path.join(script_dir, 'database')
sys.path.append(database_dir)
from drift_database import DriftDatabase

def create_perfect_scenarios():
    """Create scenarios showing 'working perfectly' and other positive states"""
    
    db_path = os.path.join(script_dir, 'data', 'drift_detection.db')
    db = DriftDatabase(db_path)
    
    scenarios = [
        # Scenario 1: Everything Working Perfectly
        {
            "timestamp": datetime.now().isoformat(),
            "environment": "production",
            "drift_detected": False,
            "summary": {
                "total_issues": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0
            },
            "drift_details": [],
            "infrastructure_state": {
                "expected": {
                    "containers": 5,
                    "networks": 2,
                    "volumes": 3,
                    "images": 4
                },
                "actual": {
                    "containers": 5,
                    "containers_running": 5,
                    "containers_healthy": 5,
                    "networks": 2,
                    "volumes": 3,
                    "load_balancer_status": "healthy",
                    "database_status": "online",
                    "api_status": "responsive"
                }
            },
            "health_metrics": {
                "cpu_usage": "12%",
                "memory_usage": "45%",
                "disk_usage": "23%",
                "response_time": "85ms",
                "uptime": "99.9%"
            },
            "raw_data": {
                "terraform_state_available": True,
                "docker_state_available": True,
                "last_check": datetime.now().isoformat(),
                "system_status": "optimal"
            }
        },
        
        # Scenario 2: Minor Optimization Suggestions
        {
            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "environment": "production",
            "drift_detected": True,
            "summary": {
                "total_issues": 2,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 2
            },
            "drift_details": [
                {
                    "type": "PERFORMANCE_OPTIMIZATION",
                    "severity": "low",
                    "resource": "web-server-optimization",
                    "issue": "Container could use resource optimization",
                    "expected": "Standard resource allocation",
                    "actual": "Could benefit from CPU limit adjustment for better performance",
                    "recommendation": "Consider updating CPU limits for optimal performance"
                },
                {
                    "type": "IMAGE_UPDATE_AVAILABLE",
                    "severity": "low",
                    "resource": "database-image",
                    "issue": "Newer image version available",
                    "expected": "postgres:13",
                    "actual": "postgres:13.1 (newer version 13.2 available)",
                    "recommendation": "Update to latest patch version for security improvements"
                }
            ],
            "infrastructure_state": {
                "expected": {"containers": 4, "networks": 1, "volumes": 2},
                "actual": {"containers": 4, "containers_running": 4, "networks": 1, "volumes": 2}
            }
        },
        
        # Scenario 3: Auto-Resolved Issues
        {
            "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat(),
            "environment": "staging",
            "drift_detected": False,
            "summary": {
                "total_issues": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0,
                "resolved_issues": 1
            },
            "drift_details": [],
            "infrastructure_state": {
                "expected": {"containers": 3, "networks": 1, "volumes": 1},
                "actual": {"containers": 3, "containers_running": 3, "networks": 1, "volumes": 1}
            },
            "resolved_issues": [
                {
                    "type": "CONTAINER_RESTART_RESOLVED",
                    "severity": "medium",
                    "resource": "api-service",
                    "issue": "Container was restarted due to health check failure",
                    "resolution": "Auto-recovery successful - container now healthy",
                    "resolved_at": (datetime.now() - timedelta(minutes=2)).isoformat()
                }
            ]
        },
        
        # Scenario 4: Excellent Performance State
        {
            "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
            "environment": "production",
            "drift_detected": False,
            "summary": {
                "total_issues": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0
            },
            "drift_details": [],
            "infrastructure_state": {
                "expected": {"containers": 6, "networks": 2, "volumes": 4},
                "actual": {
                    "containers": 6, 
                    "containers_running": 6,
                    "containers_healthy": 6,
                    "networks": 2, 
                    "volumes": 4,
                    "performance_score": 98.5
                }
            },
            "performance_metrics": {
                "response_time_avg": "45ms",
                "throughput": "1200 req/sec",
                "error_rate": "0.01%",
                "availability": "100%"
            }
        },
        
        # Scenario 5: Successfully Remediated Critical Issue
        {
            "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "environment": "production", 
            "drift_detected": False,
            "summary": {
                "total_issues": 0,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 0,
                "remediated_issues": 1
            },
            "drift_details": [],
            "infrastructure_state": {
                "expected": {"containers": 4, "networks": 1, "volumes": 2},
                "actual": {"containers": 4, "containers_running": 4, "networks": 1, "volumes": 2}
            },
            "remediation_log": {
                "action": "AUTO_REMEDIATION_SUCCESSFUL",
                "issue_resolved": "Critical security vulnerability patched",
                "remediation_time": "3 minutes",
                "success_rate": "100%",
                "rollback_available": True
            }
        }
    ]
    
    print("🎯 Creating 'Working Perfectly' scenarios...")
    
    for i, scenario in enumerate(scenarios, 1):
        # Save to logs with descriptive names
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if scenario['drift_detected']:
            status = "minor_issues"
        elif 'resolved_issues' in scenario['summary']:
            status = "auto_resolved"
        elif 'remediation_log' in scenario:
            status = "remediated"
        else:
            status = "perfect"
            
        log_file = f"../logs/drift-report-{status}-{i}-{timestamp}.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(scenario, f, indent=2)
            
            # Determine status description
            if status == "perfect":
                desc = "✅ WORKING PERFECTLY"
            elif status == "minor_issues":
                desc = "🔧 MINOR OPTIMIZATIONS"
            elif status == "auto_resolved":
                desc = "🔄 AUTO-RESOLVED"
            elif status == "remediated":
                desc = "🛠️ SUCCESSFULLY REMEDIATED"
            else:
                desc = "👍 HEALTHY STATE"
                
            print(f"   {desc} - Environment: {scenario['environment']}")
            
            # Save to database
            report_id = db.store_report(scenario)
            print(f"   📊 Stored in database with ID: {report_id}")
            
        except Exception as e:
            print(f"❌ Error creating scenario {i}: {e}")
    
    print(f"\n🎉 Created 5 diverse scenarios showing different positive states!")
    print(f"🔄 Refresh your dashboard to see:")
    print(f"   ✅ Perfect operations")
    print(f"   🔧 Minor optimizations")  
    print(f"   🔄 Auto-resolved issues")
    print(f"   🛠️ Successful remediations")
    
    # Get latest statistics
    try:
        stats = db.get_drift_statistics()
        print(f"\n📈 Updated Database Statistics:")
        print(f"   Total reports: {stats['total_reports']}")
        print(f"   Drift reports: {stats['drift_reports']}")
        print(f"   Drift percentage: {stats['drift_percentage']:.1f}%")
    except:
        print(f"\n📊 Database updated successfully!")

if __name__ == "__main__":
    create_perfect_scenarios()