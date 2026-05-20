#Requires -Version 5.1
<#
    Deploys trading-assistant to AWS Lightsail.
    - Creates instance, attaches static IP, opens only SSH.
    - Uploads server_setup.sh and runs it on the box.
    - No public API; DB is reachable only via SSH tunnel.

    Prerequisites on this laptop:
      - aws CLI configured (aws sts get-caller-identity must work)
      - ssh + scp available on PATH (Windows 10+ has these built-in)
      - server_setup.sh sitting next to this script

    Usage:
      .\deploy_lightsail.ps1
      .\deploy_lightsail.ps1 -Region us-west-2 -Bundle medium_3_0
#>
[CmdletBinding()]
param(
    [string]$InstanceName = "trading-assistant",
    [string]$Region       = "us-east-1",
    [string]$AZ           = "us-east-1a",
    [string]$Blueprint    = "ubuntu_24_04",
    [string]$Bundle       = "small_3_0",
    [string]$RepoUrl      = "https://github.com/chitown2016/tradingAssistant.git",
    [string]$KeyPath      = "$env:USERPROFILE\.ssh\lightsail-trading.pem"
)

$ErrorActionPreference = "Stop"

function Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Info($msg) { Write-Host "    $msg" -ForegroundColor Gray }
function Die($msg)  { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# --- Prereqs ---
Step "Checking prerequisites"
foreach ($cmd in 'aws','ssh','scp') {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Die "$cmd not found on PATH" }
    Info "${cmd}: OK"
}
$identity = aws sts get-caller-identity --output json | ConvertFrom-Json
Info "AWS account: $($identity.Account)  ($($identity.Arn))"

$setupScript = Join-Path $PSScriptRoot "server_setup.sh"
if (-not (Test-Path $setupScript)) { Die "server_setup.sh not found at $setupScript" }

# --- Instance ---
Step "Looking for existing instance '$InstanceName' in $Region"
$instances = (aws lightsail get-instances --region $Region --output json | ConvertFrom-Json).instances
$instance  = $instances | Where-Object { $_.name -eq $InstanceName }

if ($instance) {
    Info "Already exists (state: $($instance.state.name))"
} else {
    Step "Creating Lightsail instance ($Bundle / $Blueprint in $AZ)"
    aws lightsail create-instances `
        --region $Region `
        --instance-names $InstanceName `
        --availability-zone $AZ `
        --blueprint-id $Blueprint `
        --bundle-id $Bundle `
        --tags "key=project,value=tradingAssistant" | Out-Null
}

# --- Wait for running ---
Step "Waiting for instance to enter 'running' state"
do {
    Start-Sleep -Seconds 5
    $inst = (aws lightsail get-instance --region $Region --instance-name $InstanceName --output json `
             | ConvertFrom-Json).instance
    Info "  state: $($inst.state.name)"
} while ($inst.state.name -ne "running")

# --- Static IP ---
$staticIpName = "$InstanceName-ip"
Step "Ensuring static IP '$staticIpName' is allocated and attached"
$ips = (aws lightsail get-static-ips --region $Region --output json | ConvertFrom-Json).staticIps
$ipObj = $ips | Where-Object { $_.name -eq $staticIpName }
if (-not $ipObj) {
    aws lightsail allocate-static-ip --region $Region --static-ip-name $staticIpName | Out-Null
    aws lightsail attach-static-ip   --region $Region --static-ip-name $staticIpName --instance-name $InstanceName | Out-Null
} elseif ($ipObj.attachedTo -ne $InstanceName) {
    aws lightsail attach-static-ip   --region $Region --static-ip-name $staticIpName --instance-name $InstanceName | Out-Null
}
$ip = (aws lightsail get-static-ip --region $Region --static-ip-name $staticIpName --output json `
       | ConvertFrom-Json).staticIp.ipAddress
Info "Static IP: $ip"

# --- Firewall: SSH only ---
Step "Configuring firewall (SSH port 22 only, no public API)"
aws lightsail put-instance-public-ports `
    --region $Region `
    --instance-name $InstanceName `
    --port-infos "fromPort=22,toPort=22,protocol=TCP" | Out-Null

# --- SSH key ---
Step "Fetching default SSH key for region"
$keyDir = Split-Path $KeyPath -Parent
if (-not (Test-Path $keyDir)) { New-Item -ItemType Directory -Path $keyDir | Out-Null }
if (-not (Test-Path $KeyPath)) {
    $keyContent = (aws lightsail download-default-key-pair --region $Region --output json `
                   | ConvertFrom-Json).privateKeyBase64
    Set-Content -Path $KeyPath -Value $keyContent -Encoding ASCII -NoNewline
    icacls $KeyPath /inheritance:r /grant:r "${env:USERNAME}:(R)" | Out-Null
}
Info "Key: $KeyPath"

# --- Wait for SSH ---
Step "Waiting for SSH on $ip"
$ready = $false
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
for ($i = 1; $i -le 36; $i++) {
    & ssh -i $KeyPath -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL `
          -o ConnectTimeout=5 -o BatchMode=yes ubuntu@$ip 'echo ready' 2>$null 1>$null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Info "  attempt $i / 36..."
    Start-Sleep -Seconds 5
}
$ErrorActionPreference = $prevEAP
if (-not $ready) { Die "SSH never became ready on $ip" }

# --- Upload + run setup ---
Step "Uploading server_setup.sh"
scp -i $KeyPath -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL `
    $setupScript "ubuntu@${ip}:~/server_setup.sh"

Step "Running server_setup.sh on box (takes about 5 min)"
ssh -i $KeyPath -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL ubuntu@$ip "chmod +x ~/server_setup.sh"
ssh -i $KeyPath -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL ubuntu@$ip "REPO_URL='$RepoUrl' bash ~/server_setup.sh"

# --- Done ---
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Deployment complete!"                                        -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Instance:  $InstanceName  ($Region)"                          -ForegroundColor Green
Write-Host " IP:        $ip"                                               -ForegroundColor Green
Write-Host " SSH:       ssh -i $KeyPath ubuntu@$ip"                        -ForegroundColor Green
Write-Host ""
Write-Host " First-time catch-up (fills the 4-month gap):"                 -ForegroundColor Yellow
Write-Host "   ssh -i $KeyPath ubuntu@$ip"                                 -ForegroundColor Yellow
Write-Host "   cd ~/tradingAssistant"                                      -ForegroundColor Yellow
Write-Host "   .venv/bin/python run_daily_update_ec2.py --lookback-days 130" -ForegroundColor Yellow
Write-Host "   .venv/bin/python calculate_indicators.py"                   -ForegroundColor Yellow
Write-Host ""
Write-Host " DB tunnel from this laptop (local 5433 -> remote 5432):"     -ForegroundColor Yellow
Write-Host "   ssh -i $KeyPath -L 5433:127.0.0.1:5432 ubuntu@$ip"         -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green
