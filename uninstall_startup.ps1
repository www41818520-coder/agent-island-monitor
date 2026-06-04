$ErrorActionPreference = "Stop"

$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "Agent Island.lnk"

if (Test-Path -LiteralPath $shortcutPath) {
  Remove-Item -LiteralPath $shortcutPath -Force
  Write-Host "Removed startup shortcut:"
  Write-Host $shortcutPath
} else {
  Write-Host "Startup shortcut was not found:"
  Write-Host $shortcutPath
}
