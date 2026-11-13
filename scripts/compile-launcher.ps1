# Compiles the genuine Win64 Rustify PortableApps launcher on a hosted Windows runner.
# b1r2: NEVER read a potentially unset $LASTEXITCODE under Set-StrictMode.
# vswhere is a short-lived native executable; Start-Process -PassThru gives a dependable ExitCode.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not ${env:ProgramFiles(x86)}) { throw 'ProgramFiles(x86) is unavailable; a Windows x64 runner is required' }
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) { throw "vswhere.exe not found: $vswhere" }
if (-not $env:RUNNER_TEMP -or -not (Test-Path -LiteralPath $env:RUNNER_TEMP -PathType Container)) {
    throw 'RUNNER_TEMP is required; use an official hosted Windows Actions runner'
}

$vsStdout = Join-Path $env:RUNNER_TEMP 'rustify_vswhere.stdout.txt'
$vsStderr = Join-Path $env:RUNNER_TEMP 'rustify_vswhere.stderr.txt'
# vswhere selects the installed C++ workload on either VS 2022 or VS 2026 images.
# Redirect stdout instead of placing the call in a PowerShell pipeline/subexpression.
$vsProc = Start-Process -FilePath $vswhere -ArgumentList @(
    '-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'
) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $vsStdout -RedirectStandardError $vsStderr
if ($vsProc.ExitCode -ne 0) {
    $details = Get-Content -LiteralPath $vsStderr -Raw -ErrorAction SilentlyContinue
    throw "vswhere failed (exit $($vsProc.ExitCode)): $details"
}
$installCandidates = @(Get-Content -LiteralPath $vsStdout -Encoding utf8 | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
if ($installCandidates.Count -ne 1) {
    throw "Expected one Visual Studio installation with x64 C++ tools; got $($installCandidates.Count). Check VS workload installation."
}
$install = $installCandidates[0].Trim()
if (-not (Test-Path -LiteralPath $install -PathType Container)) {
    throw "vswhere returned missing Visual Studio installation: $install"
}
$vcvars = Join-Path $install 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path -LiteralPath $vcvars -PathType Leaf)) { throw "Missing vcvars64.bat: $vcvars" }
Write-Host "Detected Visual Studio: $install"

$out = Join-Path $root 'work\RustifyPortable.exe'
$src = Join-Path $root 'launcher\RustifyPortable.cpp'
if (-not (Test-Path -LiteralPath $src -PathType Leaf)) { throw "Launcher source missing: $src" }
New-Item -Force -ItemType Directory -Path (Split-Path $out -Parent) | Out-Null
$bat = Join-Path $env:RUNNER_TEMP 'rustify_compile_launcher.cmd'
@(
    '@echo off'
    'chcp 65001 >nul'
    'call "' + $vcvars + '" >nul'
    'if errorlevel 1 exit /b 1'
    'cl.exe /nologo /utf-8 /std:c++17 /EHsc /O2 /W4 /DUNICODE /D_UNICODE "' + $src + '" /link /SUBSYSTEM:WINDOWS /MACHINE:X64 /OUT:"' + $out + '" User32.lib Shell32.lib'
    'exit /b %errorlevel%'
) | Set-Content -LiteralPath $bat -Encoding utf8NoBOM

# Invoke through cmd.exe to keep the vcvars environment and compiler in ONE process.
# Capture $? immediately; Get-Variable checks the native exit code safely if it exists.
& $env:ComSpec /d /c "`"$bat`""
$compilerSucceeded = $?
$nativeExitVariable = Get-Variable -Name LASTEXITCODE -ErrorAction SilentlyContinue
$compilerExitCode = if ($null -eq $nativeExitVariable) { 'unavailable' } else { [string]$nativeExitVariable.Value }
if (-not $compilerSucceeded -or ($null -ne $nativeExitVariable -and [int]$nativeExitVariable.Value -ne 0)) {
    throw "C++ launcher compilation failed; cmd exit=$compilerExitCode"
}
if (-not (Test-Path -LiteralPath $out -PathType Leaf)) { throw 'Compiled RustifyPortable.exe not generated' }
if ((Get-Item -LiteralPath $out).Length -lt 1024) { throw 'Compiler output is implausibly small; launcher validation rejected' }
Write-Host "WINDOWS-COMPILED launcher: $out"
