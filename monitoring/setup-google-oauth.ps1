# Grafana Google OAuth Setup Script
# Run this script to configure Google OAuth for Grafana

Write-Host "=== Grafana Google OAuth Setup ===" -ForegroundColor Green

Write-Host "`nStep 1: Set up Google OAuth Application" -ForegroundColor Yellow
Write-Host "1. Go to https://console.cloud.google.com/" -ForegroundColor White
Write-Host "2. Create or select a project" -ForegroundColor White
Write-Host "3. Enable Google+ API (if not already enabled)" -ForegroundColor White
Write-Host "4. Go to 'Credentials' -> 'Create Credentials' -> 'OAuth 2.0 Client IDs'" -ForegroundColor White
Write-Host "5. Application type: 'Web application'" -ForegroundColor White
Write-Host "6. Authorized redirect URIs:" -ForegroundColor White
Write-Host "   - http://localhost:3000/login/google" -ForegroundColor Cyan
Write-Host "   - https://your-domain.com/login/google (if you have a domain)" -ForegroundColor Cyan

Write-Host "`nStep 2: Enter your Google OAuth credentials" -ForegroundColor Yellow

# Get Google Client ID
$clientId = Read-Host "Enter your Google Client ID"
while ([string]::IsNullOrWhiteSpace($clientId)) {
    Write-Host "Client ID cannot be empty!" -ForegroundColor Red
    $clientId = Read-Host "Enter your Google Client ID"
}

# Get Google Client Secret
$clientSecret = Read-Host "Enter your Google Client Secret" -MaskInput
while ([string]::IsNullOrWhiteSpace($clientSecret)) {
    Write-Host "Client Secret cannot be empty!" -ForegroundColor Red
    $clientSecret = Read-Host "Enter your Google Client Secret" -MaskInput
}

# Optional: Hosted Domain
Write-Host "`nOptional: Restrict login to specific Google Workspace domain" -ForegroundColor Yellow
$hostedDomain = Read-Host "Enter hosted domain (e.g., yourcompany.com) or press Enter to skip"

# Update .env file
$envContent = @"
# Google OAuth Configuration for Grafana
GOOGLE_CLIENT_ID=$clientId
GOOGLE_CLIENT_SECRET=$clientSecret
GOOGLE_HOSTED_DOMAIN=$hostedDomain
"@

$envPath = ".env"
$envContent | Out-File -FilePath $envPath -Encoding UTF8
Write-Host "`n✅ Environment file updated: $envPath" -ForegroundColor Green

# Update grafana.ini with the hosted domain if provided
if (![string]::IsNullOrWhiteSpace($hostedDomain)) {
    $grafanaIniPath = "grafana.ini"
    $content = Get-Content $grafanaIniPath -Raw
    $content = $content -replace "hosted_domain = ", "hosted_domain = $hostedDomain"
    $content | Out-File -FilePath $grafanaIniPath -Encoding UTF8
    Write-Host "✅ Grafana configuration updated with hosted domain" -ForegroundColor Green
}

Write-Host "`nStep 3: Restart Grafana" -ForegroundColor Yellow
Write-Host "Run these commands to restart Grafana with new settings:" -ForegroundColor White
Write-Host "docker-compose -f docker-compose.monitoring.yml restart grafana" -ForegroundColor Cyan

Write-Host "`nStep 4: Test Google Login" -ForegroundColor Yellow
Write-Host "1. Go to http://localhost:3000" -ForegroundColor White
Write-Host "2. Click 'Sign in with Google' button" -ForegroundColor White
Write-Host "3. Authenticate with your Google account" -ForegroundColor White

Write-Host "`n🎉 Setup complete!" -ForegroundColor Green
Write-Host "Note: Users signing in with Google will have 'Viewer' role by default." -ForegroundColor Yellow