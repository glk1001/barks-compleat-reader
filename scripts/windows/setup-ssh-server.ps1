# cspell:ignore sshd icacls schtasks gregspc HKLM
# Set up the OpenSSH server on this Windows machine, so the overnight laptop can be
# reached from the main machine: the logs read, git pulled, the run started.
#
# What it does (each step is skipped when already done; run it again to change a setting):
#   - installs Windows' own OpenSSH Server and starts it now and at every boot;
#   - opens port 22 to the local network only (the Private profile, the local subnet),
#     and, with -MakeNetworkPrivate, marks the current Wi-Fi as Private (a home
#     network: on a Public one the rule does not apply, so ssh stays closed);
#   - sets the shell ssh logs in to: PowerShell (default) or Git Bash (-Shell bash);
#   - with -PublicKey, adds that key for logging in without a password. An account in
#     the Administrators group reads its keys from
#     C:\ProgramData\ssh\administrators_authorized_keys, not ~\.ssh, and sshd ignores
#     that file unless only Administrators and SYSTEM can open it: this sets that.
#
# Usage, from an elevated PowerShell (Run as administrator), in the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\setup-ssh-server.ps1 -MakeNetworkPrivate
#   ... -PublicKey "ssh-ed25519 AAAA... gregg@gregspc2"   add the other machine's key
#   ... -Shell bash                                       log in to Git Bash instead
# Then from the other machine: ssh gregg@<this machine's IP>
#
# Over ssh there is no desktop: the GUI stages cannot run in an ssh session (their keys
# need the logged-on user's screen). Start a whole run from ssh through the nightly task
# instead, which runs on that screen: schtasks /Run /TN "Barks Reader overnight".

param(
    [string]$PublicKey = "",
    [ValidateSet("powershell", "bash")]
    [string]$Shell = "powershell",
    [switch]$MakeNetworkPrivate
)

$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this from an elevated PowerShell (Run as administrator)."
}

# The server: Windows' optional feature, unless an sshd is already installed. That
# download comes through Windows Update and can stall (it sat at 49% on the laptop);
# then stop this, run `winget install --id Microsoft.OpenSSH.Preview` (the same server,
# from Microsoft's GitHub releases), and run this again for the rest.
if ($null -eq (Get-Service sshd -ErrorAction SilentlyContinue)) {
    $capability = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
    if ($capability.State -ne "Installed") {
        Write-Output "Installing OpenSSH Server through Windows Update (minutes; it shows no progress)..."
        Add-WindowsCapability -Online -Name $capability.Name | Out-Null
    }
} else {
    Write-Output "sshd already installed: $((Get-CimInstance Win32_Service -Filter "Name='sshd'").PathName)"
}
Set-Service -Name sshd -StartupType Automatic
Start-Service sshd
Write-Output "sshd: $((Get-Service sshd).Status), starts at boot"

# The network and the firewall: the local network only.
if ($MakeNetworkPrivate) {
    Get-NetConnectionProfile | Where-Object { $_.NetworkCategory -eq "Public" } | ForEach-Object {
        Set-NetConnectionProfile -InterfaceIndex $_.InterfaceIndex -NetworkCategory Private
        Write-Output "network '$($_.Name)' on $($_.InterfaceAlias): now Private"
    }
}
$rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if ($null -eq $rule) {
    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH SSH Server (sshd)" `
        -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 `
        -Profile Private -RemoteAddress LocalSubnet | Out-Null
} else {
    Set-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -Enabled True -Profile Private `
        -RemoteAddress LocalSubnet
}
Write-Output "firewall: port 22 open to the local subnet, on Private networks only"

# The login shell.
$shellPath = if ($Shell -eq "bash") {
    "C:\Program Files\Git\bin\bash.exe"
} else {
    "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
}
if (-not (Test-Path $shellPath)) { throw "No shell at $shellPath" }
New-Item -Path "HKLM:\SOFTWARE\OpenSSH" -Force | Out-Null
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value $shellPath `
    -PropertyType String -Force | Out-Null
# How sshd hands the shell a command (`ssh host "git pull"`): cmd's /c by default,
# which bash does not take; PowerShell is recognised without it.
if ($Shell -eq "bash") {
    New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShellCommandOption -Value "-c" `
        -PropertyType String -Force | Out-Null
} else {
    Remove-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShellCommandOption `
        -ErrorAction SilentlyContinue
}
Write-Output "login shell: $shellPath"

# The key.
if ($PublicKey) {
    $keys = "$env:ProgramData\ssh\administrators_authorized_keys"
    $have = if (Test-Path $keys) { Get-Content $keys } else { @() }
    if ($have -notcontains $PublicKey.Trim()) {
        Add-Content -Path $keys -Value $PublicKey.Trim() -Encoding ascii
        Write-Output "key added to $keys"
    } else {
        Write-Output "key already in $keys"
    }
    icacls.exe $keys /inheritance:r /grant "*S-1-5-32-544:F" /grant "*S-1-5-18:F" | Out-Null
    Write-Output "permissions: Administrators and SYSTEM only (as sshd requires)"
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254*" }).IPAddress -join ", "
Write-Output ""
Write-Output "Done. From the other machine: ssh $env:USERNAME@$ip"
