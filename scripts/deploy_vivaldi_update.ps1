$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$dataDirectory = Join-Path $projectRoot 'outputs\screen_time\release\ScreenTime\data'
$stateFile = Join-Path $dataDirectory 'state.json'
$extensionDirectory = Join-Path $projectRoot 'outputs\screen_time\浏览器扩展'
$entryPoint = Join-Path $PSScriptRoot 'screen_time_start.py'
$pythonWindowless = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$status = Invoke-RestMethod 'http://127.0.0.1:18765/api/status'
if ($status.api_version -ne 1 -or !$status.instance_id) { throw '后台不兼容' }
$listener = @(Get-NetTCPConnection -LocalPort 18765 -State Listen | Select-Object -ExpandProperty OwningProcess -Unique)
if ($listener.Count -ne 1) { throw '监听进程不唯一' }
$owner = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $listener[0])
if (!$owner.CommandLine.Contains($entryPoint) -or !$owner.CommandLine.Contains($dataDirectory)) { throw '后台入口或数据目录不匹配' }
$backupRoot = Join-Path $projectRoot ('outputs\screen_time\backups\vivaldi-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path (Join-Path $backupRoot 'data') -Force | Out-Null
Get-ChildItem -LiteralPath $dataDirectory -Force | Where-Object { $_.Name -ne '.focuser.lock' -and $_.Name -notlike '*.tmp' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $backupRoot 'data') -Recurse }
if (Test-Path -LiteralPath $extensionDirectory) { Copy-Item -LiteralPath $extensionDirectory -Destination (Join-Path $backupRoot 'extension') -Recurse }
# Maintenance restart only: never pause, reset state or call the unlock APIs.
Stop-Process -Id $listener[0] -Force
for ($attempt=0; $attempt -lt 40; $attempt++) {
    if (!(Get-NetTCPConnection -LocalPort 18765 -State Listen -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 100
}
$before = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
Copy-Item -LiteralPath $stateFile -Destination (Join-Path $backupRoot 'state-at-restart.json')
try {
    New-Item -ItemType Directory -Path $extensionDirectory -Force | Out-Null
    Copy-Item -Path (Join-Path $projectRoot 'resources\screen_time\extension\*') -Destination $extensionDirectory -Recurse -Force
} finally {
    Start-Process -FilePath $pythonWindowless -ArgumentList ('"' + $entryPoint + '" --data-dir "' + $dataDirectory + '" --port 18765 --background') -WorkingDirectory $projectRoot -WindowStyle Hidden
}
$afterStatus = $null
for ($attempt=0; $attempt -lt 60; $attempt++) {
    try { $afterStatus = Invoke-RestMethod 'http://127.0.0.1:18765/api/status' -TimeoutSec 1; if ($afterStatus.instance_id -eq $status.instance_id) { break } } catch {}
    Start-Sleep -Milliseconds 200
}
if (!$afterStatus -or $afterStatus.instance_id -ne $status.instance_id) { throw '后台恢复失败；备份已保留' }
$after = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($field in @('groups','bonus','paused')) {
    if (($before.$field | ConvertTo-Json -Depth 30 -Compress) -ne ($after.$field | ConvertTo-Json -Depth 30 -Compress)) { throw ('维护改变了 ' + $field) }
}
foreach ($day in $before.history.PSObject.Properties) {
    foreach ($group in $day.Value.PSObject.Properties) {
        if ([double]$after.history.($day.Name).($group.Name) -lt [double]$group.Value) { throw '维护减少了已用时长' }
    }
}
$report = [ordered]@{backup=$backupRoot;extension=$extensionDirectory;instance_id=$afterStatus.instance_id;rules_preserved=$true;usage_not_reduced=$true;bonus_preserved=$true;paused=$afterStatus.paused;activation='在 Vivaldi 加载扩展；已安装的其他浏览器重新加载扩展'}
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'outputs\screen_time\vivaldi-update.json') -Encoding UTF8
$report | ConvertTo-Json
