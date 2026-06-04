$ErrorActionPreference = "Stop"

$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Agent Island.lnk"
$target = Join-Path $appDir "start_agent_island.bat"

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $appDir
$shortcut.WindowStyle = 7
$shortcut.Description = "Windows Codex and Cursor island monitor"
$shortcut.Save()

Write-Host "Installed startup shortcut:"
Write-Host $shortcutPath
