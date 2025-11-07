#!/usr/bin/env python3
"""
Test Drift Scenarios Generator
Creates different drift scenarios for testing the dashboard
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

def create_test_scenarios():
    """Create various drift scenarios for testing"""
    
    db_path = os.path.join(script_dir, 'data', 'drift_detection.db')
    db = DriftDatabase(db_path)
    
    scenarios = [
        # Scenario 1: High severity network drift
        {
            "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
            "environment": "production",
            "drift_detected": True,
            "summary": {
                "total_issues": 3,
                "high_severity": 2,
                "medium_severity": 1,
                "low_severity": 0
            },
            "drift_details": [
                {
                    "type": "NETWORK_CONFIGURATION_DRIFT",
                    "severity": "high",
                    "resource": "main-network",
                    "issue": "Network bridge configuration mismatch",
                    "expected": "bridge mode with subnet 172.20.0.0/16",
                    "actual": "host mode detected"
                },
                {
                    "type": "SECURITY_POLICY_DRIFT",
                    "severity": "high", 
                    "resource": "web-container-security",
                    "issue": "Container running with elevated privileges",
                    "expected": "non-privileged mode",
                    "actual": "privileged mode enabled"
                },
                {
                    "type": "RESOURCE_LIMITS_DRIFT",
                    "severity": "medium",
                    "resource": "database-container-limits", 
                    "issue": "Memory limit exceeded configuration",
                    "expected": "2GB memory limit",
                    "actual": "4GB memory limit"
                }
            ],
            "infrastructure_state": {
                "expected": {"containers": 4, "networks": 1, "volumes": 2},
                "actual": {"containers": 4, "containers_running": 3, "networks": 1, "volumes": 2}
            }
        },
        
        # Scenario 2: Medium severity configuration drift
        {
            "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
            "environment": "staging",
            "drift_detected": True,
            "summary": {
                "total_issues": 2,
                "high_severity": 0,
                "medium_severity": 2,
                "low_severity": 0
            },
            "drift_details": [
                {
                    "type": "ENVIRONMENT_VARIABLE_DRIFT",
                    "severity": "medium",
                    "resource": "web-app-config",
                    "issue": "Environment variable mismatch",
                    "expected": "DEBUG=false",
                    "actual": "DEBUG=true"
                },
                {
                    "type": "PORT_MAPPING_DRIFT",
                    "severity": "medium",
                    "resource": "api-service-ports",
                    "issue": "Port mapping configuration changed", 
                    "expected": "8080:80",
                    "actual": "8081:80"
                }
            ],
            "infrastructure_state": {
                "expected": {"containers": 3, "networks": 1, "volumes": 1},
                "actual": {"containers": 3, "containers_running": 3, "networks": 1, "volumes": 1}
            }
        },
        
        # Scenario 3: Low severity drift
        {
            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "environment": "dev",
            "drift_detected": True,
            "summary": {
                "total_issues": 1,
                "high_severity": 0,
                "medium_severity": 0,
                "low_severity": 1
            },
            "drift_details": [
                {
                    "type": "LABEL_DRIFT",
                    "severity": "low",
                    "resource": "monitoring-labels",
                    "issue": "Container labels do not match Terraform configuration",
                    "expected": "version=1.0.0",
                    "actual": "version=1.0.1"
                }
            ],
            "infrastructure_state": {
                "expected": {"containers": 4, "networks": 1, "volumes": 2},
                "actual": {"containers": 4, "containers_running": 4, "networks": 1, "volumes": 2}
            }
        },
        
        # Scenario 4: No drift (healthy state)
        {
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
                "expected": {"containers": 4, "networks": 1, "volumes": 2},
                "actual": {"containers": 4, "containers_running": 4, "networks": 1, "volumes": 2}
            }
        }
    ]
    
    print("Creating test drift scenarios...")
    
    for i, scenario in enumerate(scenarios, 1):
        # Save to logs
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"../logs/drift-report-test-{i}-{timestamp}.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(scenario, f, indent=2)
            print(f"✅ Created scenario {i}: {scenario['drift_details'][0]['type'] if scenario['drift_details'] else 'NO_DRIFT'}")
            
            # Save to database
            report_id = db.store_report(scenario)
            print(f"   📊 Stored in database with ID: {report_id}")
            
        except Exception as e:
            print(f"❌ Error creating scenario {i}: {e}")
    
    print("\n🎯 Test scenarios created! Refresh your dashboard to see the changes.")
    
    # Print summary
    stats = db.get_statistics()
    print(f"\n📈 Database Statistics:")
    print(f"   Total reports: {stats['total_reports']}")
    print(f"   Drift reports: {stats['drift_reports']}")
    print(f"   Drift percentage: {stats['drift_percentage']:.1f}%")

if __name__ == "__main__":
    create_test_scenarios()