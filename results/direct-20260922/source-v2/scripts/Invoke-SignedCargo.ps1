#requires -Version 7.0
[CmdletBinding()]
param(
    [ValidateSet('Test', 'Run', 'Build')][string]$Action = 'Test',
    [switch]$Release,
    [string]$ConfigPath = "$env:LOCALAPPDATA\goproverbs-signing\config.json",
    [switch]$InspectBuild,
    [string[]]$ProgramArguments = @()
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = Split-Path $PSScriptRoot -Parent
$targetRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'target/signed'))

function Read-SigningConfig {
    if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        throw "Signing is not enrolled. Create $ConfigPath using scripts/signing-config.example.json; see docs/WINDOWS-SIGNING.md."
    }
    $config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json -AsHashtable
    if (-not $config.SignTool -or -not (Test-Path -LiteralPath $config.SignTool -PathType Leaf)) {
        throw 'Set SignTool to the installed x64 signtool.exe path.'
    }
    if ($config.Provider -eq 'AzureArtifactSigning') {
        if (-not $config.Dlib -or -not (Test-Path -LiteralPath $config.Dlib -PathType Leaf)) {
            throw 'Set Dlib to the installed x64 Azure.CodeSigning.Dlib.dll path.'
        }
        if (-not $config.Metadata -or -not (Test-Path -LiteralPath $config.Metadata -PathType Leaf)) {
            throw 'Set Metadata to the enrolled Public Trust profile metadata.json path.'
        }
        $metadata = Get-Content -LiteralPath $config.Metadata -Raw | ConvertFrom-Json -AsHashtable
        if ($metadata.Endpoint -notmatch '^https://[a-z0-9]+\.codesigning\.azure\.net/?$' -or
            -not $metadata.CodeSigningAccountName -or -not $metadata.CertificateProfileName -or
            ($metadata.Values -join ' ') -match 'REPLACE_') {
            throw 'Fill metadata with the actual regional endpoint, signing account and Public Trust profile.'
        }
    } elseif ($config.Provider -eq 'CertificateStore') {
        if ($config.Thumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Set a certificate SHA1 thumbprint.' }
        $store = if ($config.MachineStore) { 'LocalMachine' } else { 'CurrentUser' }
        $cert = Get-Item -LiteralPath "Cert:\$store\My\$($config.Thumbprint)"
        if (-not $cert.HasPrivateKey -or $cert.Subject -eq $cert.Issuer -or
            $cert.NotAfter -lt (Get-Date) -or $cert.PublicKey.Oid.Value -ne '1.2.840.113549.1.1.1') {
            throw 'Select a current, non-self-signed RSA code-signing certificate with its private key.'
        }
        if (-not $config.TimestampUrl) { throw 'Set the certificate provider RFC3161 TimestampUrl.' }
    } else { throw 'Provider must be AzureArtifactSigning or CertificateStore.' }
    return $config
}

function Assert-TrustedSignature([string]$File, $Config) {
    & $Config.SignTool verify /pa /all $File | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Authenticode verification failed: $File" }
    $signature = Get-AuthenticodeSignature -LiteralPath $File
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate -or
        $signature.SignerCertificate.Subject -eq $signature.SignerCertificate.Issuer -or
        $signature.SignerCertificate.PublicKey.Oid.Value -ne '1.2.840.113549.1.1.1') {
        throw "A valid non-self-signed RSA signature is required: $File"
    }
}

# InspectBuild compiles and lists artifacts only. It never signs or executes them.
$signing = if ($InspectBuild) { $null } else { Read-SigningConfig }
Push-Location $projectRoot
try {
    $cargoArgs = if ($Action -eq 'Test') { @('test', '--no-run') } else { @('build') }
    $cargoArgs += @('--offline', '--locked', '-j', '1', '--message-format=json', '--target-dir', $targetRoot)
    if ($Release) { $cargoArgs += '--release' }
    $output = @(& cargo @cargoArgs)
    if ($LASTEXITCODE -ne 0) { throw "Cargo build failed with exit $LASTEXITCODE." }
    $artifacts = @($output | ForEach-Object {
        $record = $_ | ConvertFrom-Json
        if ($record.reason -eq 'compiler-artifact' -and $record.executable) { $record }
    })
    if (-not $artifacts.Count) { throw 'Cargo did not report executable artifacts.' }
    $files = @($artifacts.executable | Sort-Object -Unique)
    foreach ($file in $files) {
        $full = [IO.Path]::GetFullPath($file)
        if (-not $full.StartsWith($targetRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
            [IO.Path]::GetExtension($full) -ne '.exe' -or -not (Test-Path -LiteralPath $full -PathType Leaf)) {
            throw "Unexpected Cargo artifact path: $full"
        }
    }
    if ($InspectBuild) {
        $artifacts | Select-Object executable, @{n='IsTest';e={$_.profile.test}} | Format-Table -AutoSize
        return
    }
    # Sign every executable before launching any test, including the app spawned by integration tests.
    foreach ($file in $files) {
        $existing = Get-AuthenticodeSignature -LiteralPath $file
        if ($existing.Status -ne 'Valid') {
            $signArgs = @('sign', '/fd', 'SHA256', '/td', 'SHA256')
            if ($signing.Provider -eq 'AzureArtifactSigning') {
                $signArgs += @('/tr', 'http://timestamp.acs.microsoft.com', '/dlib', $signing.Dlib, '/dmdf', $signing.Metadata)
            } else {
                $signArgs += @('/tr', $signing.TimestampUrl, '/sha1', $signing.Thumbprint, '/s', 'My')
                if ($signing.MachineStore) { $signArgs += '/sm' }
            }
            & $signing.SignTool @signArgs $file | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Signing failed: $file" }
            $signed = Get-AuthenticodeSignature -LiteralPath $file
            if (-not $signed.TimeStamperCertificate) { throw "Timestamp missing: $file" }
        }
        Assert-TrustedSignature $file $signing
    }
    if ($Action -eq 'Build') { Write-Host 'Build signed and verified.'; return }
    $runFiles = if ($Action -eq 'Test') {
        @($artifacts | Where-Object { $_.profile.test } | Select-Object -ExpandProperty executable -Unique)
    } else {
        @($artifacts | Where-Object { -not $_.profile.test -and $_.target.name -eq 'goproverbs' -and 'bin' -in $_.target.kind } |
            Select-Object -ExpandProperty executable -Unique)
    }
    if (-not $runFiles.Count) { throw 'No matching executable to run.' }
    foreach ($file in $runFiles) {
        & $file @ProgramArguments
        if ($LASTEXITCODE -ne 0) { throw "Executable failed with exit ${LASTEXITCODE}: $file" }
    }
} finally { Pop-Location }
