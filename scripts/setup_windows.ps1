param(
    [string]$PythonExe,
    [string]$DataDirectory,
    [int]$Port = 18765,
    [string]$DesktopDirectory = [Environment]::GetFolderPath('Desktop'),
    [string]$StartupDirectory = [Environment]::GetFolderPath('Startup'),
    [string]$ExtensionDirectory,
    [switch]$Plan,
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$entryPoint = Join-Path $PSScriptRoot 'screen_time_start.py'
$outputRoot = Join-Path $projectRoot 'outputs\screen_time'
if ($Port -lt 1024 -or $Port -gt 65535) { throw '端口无效' }
if (!$DataDirectory) { $DataDirectory = Join-Path $outputRoot 'release\ScreenTime\data' }
$DataDirectory = [IO.Path]::GetFullPath($DataDirectory)
$stateFile = Join-Path $DataDirectory 'state.json'
if (!$PythonExe) {
    $localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if(Test-Path -LiteralPath $localPython){ $PythonExe = $localPython }
    else {
        $pythonCommand = Get-Command python.exe -ErrorAction Stop
        $PythonExe = (& $pythonCommand.Source -c 'import sys; print(sys._base_executable)').Trim()
    }
}
$PythonExe = [IO.Path]::GetFullPath($PythonExe)
if (!(Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw '找不到 Python，请安装 Python 3.10 或更新版本' }
$builder = Join-Path $outputRoot 'builder'
& $PythonExe -c 'import sys; sys.path.insert(0,sys.argv[1]); import psutil, tkinter, pystray, PIL; assert sys.version_info >= (3,10)' $builder
$dependenciesReady = $LASTEXITCODE -eq 0
$planObject = [ordered]@{project=$projectRoot;python=$PythonExe;data=$DataDirectory;port=$Port;dependencies_ready=$dependenciesReady;backup_existing_data=$true;preserve_usage_and_bonus=$true;desktop=$DesktopDirectory;startup=$StartupDirectory;extension='原目录更新；在 Chrome 扩展管理页重新加载';reset_data=$false}
if ($Plan) { $planObject | ConvertTo-Json -Depth 4; exit 0 }
if (!$dependenciesReady) {
    Write-Host '安装项目独立 Python 环境与桌面依赖…'
    $environmentRoot = Join-Path $projectRoot '.venv'
    & $PythonExe -m venv $environmentRoot
    if ($LASTEXITCODE -ne 0) { throw '创建虚拟环境失败' }
    $PythonExe = Join-Path $environmentRoot 'Scripts\python.exe'
    & $PythonExe -m pip install ($projectRoot + '[desktop]')
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败；未停止原后台' }
}
$pythonWindowless = Join-Path (Split-Path $PythonExe -Parent) 'pythonw.exe'
if (!(Test-Path -LiteralPath $pythonWindowless)) { throw '缺少 pythonw.exe，未停止原后台' }
if (Test-Path -LiteralPath $stateFile) { $before = Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json }
$backupRoot = Join-Path $outputRoot ('backups\windows-setup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
if (Test-Path -LiteralPath $DataDirectory) {
    $dataBackup = Join-Path $backupRoot 'data'
    New-Item -ItemType Directory -Path $dataBackup -Force | Out-Null
    Get-ChildItem -LiteralPath $DataDirectory -Force | Where-Object { $_.Name -ne '.focuser.lock' -and $_.Name -notlike '*.tmp' } | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $dataBackup -Recurse }
}
$links = @((Join-Path $DesktopDirectory '屏幕使用时间 Local.lnk'), (Join-Path $StartupDirectory '屏幕使用时间 Local.lnk'))
for($index=0;$index -lt $links.Count;$index++) { if(Test-Path -LiteralPath $links[$index]){ Copy-Item -LiteralPath $links[$index] -Destination (Join-Path $backupRoot ('shortcut-' + $index + '.lnk')) } }
$extensionDestination = $(if($ExtensionDirectory){[IO.Path]::GetFullPath($ExtensionDirectory)}else{Join-Path $outputRoot '浏览器扩展'})
if(Test-Path -LiteralPath $extensionDestination){ Copy-Item -LiteralPath $extensionDestination -Destination (Join-Path $backupRoot 'extension') -Recurse }
Write-Host ('已备份至 ' + $backupRoot)
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if($listener) {
    $ownerIds = @($listener | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach($ownerId in $ownerIds) {
        $owner = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $ownerId)
        if(!$owner -or !$owner.CommandLine.Contains($entryPoint)) { throw '端口由其他程序占用，拒绝停止' }
        if($owner.CommandLine -match '--data-dir' -and !$owner.CommandLine.Contains($DataDirectory)) { throw '后台使用另一数据目录，拒绝切换' }
    }
    # Maintenance stop: never call /api/quit or set paused. The same data is
    # immediately reopened; the extension retains offline restrictions.
    foreach($ownerId in $ownerIds) { Stop-Process -Id $ownerId -Force }
    for($attempt=0;$attempt -lt 40;$attempt++) { if(!(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)){break};Start-Sleep -Milliseconds 100 }
}
New-Item -ItemType Directory -Path $extensionDestination -Force | Out-Null
Copy-Item -Path (Join-Path $projectRoot 'resources\screen_time\extension\*') -Destination $extensionDestination -Recurse -Force
$commonArgs = '"' + $entryPoint + '" --data-dir "' + $DataDirectory + '" --port ' + $Port
Start-Process -FilePath $pythonWindowless -ArgumentList ($commonArgs + ' --background') -WorkingDirectory $projectRoot -WindowStyle Hidden
$health = $null
for($attempt=0;$attempt -lt 60;$attempt++) {
    try { $health=Invoke-RestMethod ('http://127.0.0.1:'+$Port+'/api/health') -TimeoutSec 1; if($health.service -eq 'focuser'){break} } catch {}
    Start-Sleep -Milliseconds 200
}
if(!$health -or $health.service -ne 'focuser'){ throw ('后台未启动；原数据备份保留。请查看 ' + (Join-Path $outputRoot 'startup-error.log')) }
$after=Get-Content -LiteralPath $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json
if($before) {
    foreach($field in @('groups','history','bonus','paused')) {
        if(($before.$field | ConvertTo-Json -Depth 30 -Compress) -ne ($after.$field | ConvertTo-Json -Depth 30 -Compress)) { throw ('升级后的 '+$field+' 与备份不一致，请检查备份；未自动重置') }
    }
}
$shortcutShell = New-Object -ComObject WScript.Shell
foreach($folder in @($DesktopDirectory,$StartupDirectory)){New-Item -ItemType Directory -Path $folder -Force | Out-Null}
for($index=0;$index -lt $links.Count;$index++) {
    $link = $shortcutShell.CreateShortcut($links[$index])
    $link.TargetPath = $pythonWindowless
    $link.Arguments = $commonArgs + $(if($index -eq 1){' --background'}else{''})
    $link.WorkingDirectory = $projectRoot
    $link.Description = 'Focuser：网站与桌面 App 共享每日额度'
    $link.Save()
}
$status=Invoke-RestMethod ('http://127.0.0.1:'+$Port+'/api/status') -TimeoutSec 3
$report=[ordered]@{version=$health.version;backup=$backupRoot;python=$PythonExe;data=$DataDirectory;port=$Port;desktop=$links[0];startup=$links[1];state_preserved=$true;paused=$status.paused;bonus_used=$status.bonus_used;app_errors=$status.app_errors;extension_version=(Get-Content (Join-Path $extensionDestination 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $outputRoot 'windows-setup.json') -Encoding UTF8
Write-Host ('后台已更新：' + $health.version + '；桌面与开机入口已配置；原用量和领取记录保留。')
Write-Host ('Chrome 中打开 chrome://extensions；Vivaldi 打开 vivaldi://extensions，找到屏幕使用时间 Local，点击重新加载。扩展目录：' + $extensionDestination)
if(!$NoOpen){ Start-Process -FilePath $pythonWindowless -ArgumentList $commonArgs -WorkingDirectory $projectRoot -WindowStyle Hidden }
