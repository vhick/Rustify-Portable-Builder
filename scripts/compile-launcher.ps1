Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Visual Studio Developer environment is initialized by a temporary BAT, avoiding nested
# PowerShell/CMD quoting bugs. GitHub's hosted Windows image includes VS C++ workloads.
$root = (Resolve-Path "$PSScriptRoot/..").Path
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) { throw "vswhere.exe not found: $vswhere" }
$install = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
if ($LASTEXITCODE -ne 0 -or -not $install) { throw 'Visual Studio C++ tools not installed on Windows runner' }
$vcvars = Join-Path $install 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path -LiteralPath $vcvars)) { throw "Missing vcvars64.bat: $vcvars" }
$out = Join-Path $root 'work\RustifyPortable.exe'
New-Item -Force -ItemType Directory -Path (Split-Path $out -Parent) | Out-Null
$bat = Join-Path $env:RUNNER_TEMP 'rustify_compile_launcher.cmd'
$src = Join-Path $root 'launcher\RustifyPortable.cpp'
@(
  '@echo off'
  'call "' + $vcvars + '" >nul'
  'if errorlevel 1 exit /b 1'
  'chcp 65001 >nul'
  'cl.exe /nologo /utf-8 /std:c++17 /EHsc /O2 /W4 /DUNICODE /D_UNICODE "' + $src + '" /link /SUBSYSTEM:WINDOWS /MACHINE:X64 /OUT:"' + $out + '" User32.lib Shell32.lib'
  'exit /b %errorlevel%'
) | Set-Content -LiteralPath $bat -Encoding utf8NoBOM
& $env:ComSpec /d /c "`"$bat`""
if ($LASTEXITCODE -ne 0) { throw "C++ launcher compilation failed with exit code $LASTEXITCODE" }
if (-not (Test-Path -LiteralPath $out)) { throw 'Compiled RustifyPortable.exe not generated' }
Write-Host "WINDOWS-COMPILED launcher: $out"
