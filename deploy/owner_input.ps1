param([ValidateSet('Bootstrap','InstallKey')][string]$Mode = 'Bootstrap')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$statusPath = 'C:\Projects\trading-inteligence-platform\coding-agent-files\owner-input-status.txt'
$form = New-Object System.Windows.Forms.Form
$form.Text = if ($Mode -eq 'Bootstrap') { 'Personal AI Brain - credentialless broker bootstrap' } else { 'Personal AI Brain - install OpenAI key' }
$form.Size = New-Object System.Drawing.Size(720,320)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$label = New-Object System.Windows.Forms.Label
$label.Text = if ($Mode -eq 'Bootstrap') { "Homelab sudo password for az1mutt (NOT an OpenAI key).`nDeploy the reviewed broker identity/service and run credentialless acceptance.`nThe administrative job detaches from SSH. No paid API request; no Media changes.`nPassword is sent only over SSH stdin and is never saved." } else { "Homelab sudo password, then the future OpenAI service-account key.`nKey is sent only after the privileged installer signals readiness.`nNeither value is saved locally or placed in command arguments." }
$label.Location = New-Object System.Drawing.Point(15,15)
$label.Size = New-Object System.Drawing.Size(680,90)
$form.Controls.Add($label)
$passwordBox = New-Object System.Windows.Forms.TextBox
$passwordBox.UseSystemPasswordChar = $true
$passwordBox.Location = New-Object System.Drawing.Point(15,115)
$passwordBox.Size = New-Object System.Drawing.Size(675,25)
$form.Controls.Add($passwordBox)
$keyBox = New-Object System.Windows.Forms.TextBox
$keyBox.UseSystemPasswordChar = $true
$keyBox.Location = New-Object System.Drawing.Point(15,160)
$keyBox.Size = New-Object System.Drawing.Size(675,25)
$keyBox.Visible = $Mode -eq 'InstallKey'
$form.Controls.Add($keyBox)
$button = New-Object System.Windows.Forms.Button
$button.Text = if ($Mode -eq 'Bootstrap') {'Deploy credentialless broker and verify'} else {'Install key into broker-only file'}
$button.Location = New-Object System.Drawing.Point(345,220)
$button.Size = New-Object System.Drawing.Size(345,30)
$button.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($button); $form.AcceptButton = $button
$form.Add_Shown({$form.Activate(); $passwordBox.Focus()})
'WAITING_FOR_MASKED_INPUT' | Set-Content -LiteralPath $statusPath
if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
  'CANCELLED' | Set-Content -LiteralPath $statusPath
  $form.Dispose(); exit
}
try {
  $password = $passwordBox.Text
  $key = $keyBox.Text
  $passwordBox.Clear(); $keyBox.Clear(); $form.Dispose()
  if (-not $password -or $password -match "[\r\n]") { throw 'INVALID_INPUT' }
  if ($Mode -eq 'InstallKey' -and (-not $key -or $key -match '[\s]')) { throw 'INVALID_INPUT' }
  $info = New-Object System.Diagnostics.ProcessStartInfo
  $info.FileName = 'C:\Windows\System32\OpenSSH\ssh.exe'
  $remote = if ($Mode -eq 'Bootstrap') { '/usr/bin/systemd-run --unit=pab-credentialless-bootstrap --collect /usr/bin/python3 -B /tmp/pab-coding-agent-preflight/deploy/install_credentialless_broker.py' } else { '/usr/bin/python3 -B /opt/personal-ai-brain/builder/src/personal_ai_brain/inference_install_key.py' }
  $info.Arguments = '-o BatchMode=yes -o ConnectTimeout=10 homelab sudo -k -S -p SUDO_INPUT ' + $remote
  $info.UseShellExecute = $false; $info.CreateNoWindow = $true
  $info.RedirectStandardInput = $true; $info.RedirectStandardOutput = $true; $info.RedirectStandardError = $true
  $proc = [System.Diagnostics.Process]::Start($info)
  $stderrTask = $proc.StandardError.ReadToEndAsync()
  $proc.StandardInput.WriteLine($password); $proc.StandardInput.Flush(); $password = $null
  if ($Mode -eq 'InstallKey') {
    $ready = $proc.StandardOutput.ReadLineAsync()
    if (-not $ready.Wait(15000) -or $ready.Result -ne 'INFERENCE_KEY_READY') { $proc.Kill(); throw 'INSTALLER_NOT_READY' }
    $proc.StandardInput.WriteLine('PAB-INFERENCE-KEY-V1')
    $proc.StandardInput.WriteLine($key); $key = $null
  }
  $proc.StandardInput.Close()
  $outputTask = $proc.StandardOutput.ReadToEndAsync()
  if (-not $proc.WaitForExit(30000)) { $proc.Kill(); throw 'ADMIN_TIMEOUT' }
  $null = $stderrTask.Result
  if ($proc.ExitCode -ne 0) { throw 'ADMIN_FAILED' }
  if ($Mode -eq 'InstallKey' -and $outputTask.Result.Trim() -ne 'INFERENCE_KEY_INSTALLED') { throw 'INSTALL_NOT_VERIFIED' }
  $(if ($Mode -eq 'Bootstrap') {'BOOTSTRAP_DETACHED'} else {'KEY_INSTALLED'}) | Set-Content -LiteralPath $statusPath
} catch {
  $allowedErrors = @('INVALID_INPUT','INSTALLER_NOT_READY','ADMIN_TIMEOUT','ADMIN_FAILED','INSTALL_NOT_VERIFIED')
  $safeError = if ($allowedErrors -contains $_.Exception.Message) { $_.Exception.Message } else { $_.Exception.GetType().Name }
  if ($safeError -eq 'ADMIN_FAILED' -and $stderrTask -and $stderrTask.IsCompleted) {
    if ($stderrTask.Result -match 'incorrect password|Sorry, try again|no password was provided') { $safeError = 'SUDO_AUTH_FAILED' }
    elseif ($stderrTask.Result -match 'Could not resolve|Connection timed out|Connection refused|Permission denied \(publickey') { $safeError = 'SSH_CONNECTION_FAILED' }
  }
  ('OWNER_FLOW_STOPPED_' + $safeError) | Set-Content -LiteralPath $statusPath
} finally {
  $password = $null; $key = $null
}
