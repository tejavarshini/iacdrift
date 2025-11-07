#!/bin/bash
# 🎬 Live Demo Script for IaC Drift Detection & Remediation
# Run this script step by step during your presentation

set -e  # Exit on any error

echo "🚀 IaC DRIFT DETECTION & REMEDIATION - LIVE DEMO"
echo "================================================="
echo

# Function to pause and wait for user
wait_for_user() {
    echo "➡️  Press Enter to continue to next step..."
    read
}

echo "📋 STEP 1: Show Infrastructure Status"
echo "======================================"
echo "Current containers running:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -10
echo
echo "✅ Infrastructure deployed with:"
echo "   - 2 Web Servers (ports 80, 81)"
echo "   - 1 Database (port 5432)" 
echo "   - 1 Load Balancer (port 8081)"
echo "   - Monitoring Stack (Prometheus, Grafana)"
wait_for_user

echo "🔍 STEP 2: Run Drift Detection (Baseline)"
echo "=========================================="
echo "Checking for drift in current infrastructure..."
cd /Users/sidhartha/devops/scripts/drift-detection
python3 drift-detector.py --config ../../config/drift-detection.json
echo
echo "✅ No drift detected - everything matches Terraform state"
wait_for_user

echo "💥 STEP 3: Simulate Infrastructure Drift"
echo "========================================"
echo "Manually stopping a web container (simulating unauthorized change)..."
docker stop iac-drift-detection-web-1-dev
echo
echo "Current container status after manual change:"
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "(web|NAMES)"
echo
echo "🔴 DRIFT CREATED: One web server is now down!"
wait_for_user

echo "🔍 STEP 4: Detect the Drift"
echo "============================"
echo "Running drift detection again..."
python3 drift-detector.py --config ../../config/drift-detection.json
echo
echo "🚨 DRIFT DETECTED: System found the missing web container"
wait_for_user

echo "🛠️  STEP 5: Automatic Remediation"
echo "=================================="
echo "Applying Terraform to fix the drift..."
cd ../../terraform
terraform apply -auto-approve
echo
echo "✅ Infrastructure automatically restored!"
wait_for_user

echo "✅ STEP 6: Verify Fix"
echo "===================="
echo "Checking containers are all running again:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(web|database|loadbalancer|NAMES)"
echo
echo "🎉 SUCCESS: All containers back online!"
wait_for_user

echo "📊 STEP 7: Show Monitoring Dashboard"
echo "===================================="
echo "Open these URLs in your browser:"
echo "   • Load Balancer: http://localhost:8081"
echo "   • Grafana Dashboard: http://localhost:3000 (admin/admin123)" 
echo "   • Prometheus Metrics: http://localhost:9090"
echo
echo "Generate health report:"
cd ../monitoring
python3 health_monitor.py --report --config ../config/drift-detection.json
wait_for_user

echo "🎯 DEMO COMPLETE!"
echo "================="
echo "Key Points Demonstrated:"
echo "✅ Automatic drift detection"
echo "✅ Self-healing infrastructure" 
echo "✅ Real-time monitoring"
echo "✅ Complete audit trail"
echo "✅ Zero-downtime remediation"
echo