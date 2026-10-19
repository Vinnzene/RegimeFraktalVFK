$dest = "..\btcusdt-regime.zip"
if (Test-Path $dest) { Remove-Item $dest -Force }

$items = Get-ChildItem -Path . | Where-Object {
    $_.Name -notin @('.git', '.venv', '.vscode', '.kilo', 'node_modules', '.next')
}

# Temporary staging directory to guarantee no node_modules or .next inside frontend
$staging = "..\btcusdt_staging"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

Copy-Item -Path $items.FullName -Destination $staging -Recurse -Exclude @('.git', '__pycache__', '*.pyc')

# Clean out frontend node_modules and .next from staging if copied
if (Test-Path "$staging\frontend\node_modules") { Remove-Item "$staging\frontend\node_modules" -Recurse -Force }
if (Test-Path "$staging\frontend\.next") { Remove-Item "$staging\frontend\.next" -Recurse -Force }

Compress-Archive -Path "$staging\*" -DestinationPath $dest -Force
Remove-Item $staging -Recurse -Force

$sizeMB = [math]::Round((Get-Item $dest).Length / 1MB, 2)
Write-Host "Created $dest with size: $sizeMB MB"
