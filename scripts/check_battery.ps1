$battery = Get-WmiObject -Class Win32_Battery
$percent = $battery.EstimatedChargeRemaining
$status = $battery.BatteryStatus

# 1 = discharging, 2 = AC, 3 = fully charged, 4 = low, 5 = critical, 6 = charging, 7 = charging and high, 8 = charging and low
$isCharging = ($status -eq 2 -or $status -eq 6 -or $status -eq 7)

if ($percent -eq 100 -and $isCharging) {
    [void][System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
    $balloon = New-Object System.Windows.Forms.NotifyIcon
    $balloon.Icon = [System.Drawing.SystemIcons]::Information
    $balloon.BalloonTipTitle = "Estado de Batería"
    $balloon.BalloonTipText = "Señor, la batería está cargada al 100%. Recomiendo desconectarla."
    $balloon.Visible = $true
    $balloon.ShowBalloonTip(5000)
} elseif ($percent -le 15 -and -not $isCharging) {
    [void][System.Reflection.Assembly]::LoadWithPartialName("System.Windows.Forms")
    $balloon = New-Object System.Windows.Forms.NotifyIcon
    $balloon.Icon = [System.Drawing.SystemIcons]::Warning
    $balloon.BalloonTipTitle = "Estado de Batería"
    $balloon.BalloonTipText = "Señor, la batería está baja, recomiendo conectarle al fuente de energía."
    $balloon.Visible = $true
    $balloon.ShowBalloonTip(5000)
}
