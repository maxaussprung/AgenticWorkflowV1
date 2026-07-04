# Compact the WSL2 virtual disk (ext4.vhdx) to return freed space to Windows.
# WSL never shrinks its vhdx on its own, so after disk_cleanup.sh the space is free INSIDE WSL but the
# Windows file stays huge. This reclaims it. REQUIRES an ELEVATED (Administrator) PowerShell — the
# agent must NOT auto-run this; hand it to the user to run manually.
#
# RUN (in an Admin PowerShell):
#   .\.memory\tools\scripts\wsl_compact_vhdx.ps1
# Close all WSL apps first; this shuts WSL down.

wsl --shutdown
Start-Sleep -Seconds 8

# Find the distro's ext4.vhdx. Store-installed distros live under ...\Packages; a `wsl --install`/
# manual distro (this machine) lives under ...\LocalAppData\wsl\{guid}\ext4.vhdx — search BOTH.
$vhdx = @(
  Get-ChildItem "$env:LOCALAPPDATA\Packages" -Recurse -Filter "ext4.vhdx" -ErrorAction SilentlyContinue
  Get-ChildItem "$env:LOCALAPPDATA\wsl"      -Recurse -Filter "ext4.vhdx" -ErrorAction SilentlyContinue
) | Sort-Object Length -Descending | Select-Object -First 1
if (-not $vhdx) { Write-Error "ext4.vhdx not found under $env:LOCALAPPDATA\Packages or \wsl — locate it and set `$vhdx manually."; exit 1 }
Write-Host "Compacting $($vhdx.FullName)  (current size: $([math]::Round($vhdx.Length/1GB,2)) GB)"

# Preferred: Hyper-V module (Windows Pro/Enterprise).
if (Get-Command Optimize-VHD -ErrorAction SilentlyContinue) {
  Optimize-VHD -Path $vhdx.FullName -Mode Full
} else {
  # Fallback: diskpart (Windows Home). Runs a compact on the vhdx.
  $dp = @("select vdisk file=`"$($vhdx.FullName)`"", "attach vdisk readonly", "compact vdisk", "detach vdisk", "exit")
  $tmp = New-TemporaryFile; $dp | Set-Content $tmp -Encoding ascii
  diskpart /s $tmp; Remove-Item $tmp
}
$after = (Get-Item $vhdx.FullName).Length
Write-Host "Done. New size: $([math]::Round($after/1GB,2)) GB"
