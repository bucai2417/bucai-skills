# Install one or more skills from this repository into an agent skills directory.
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Skill,

    [ValidateSet('claud', 'codex', 'agents', 'cc-switch')]
    [string]$Target = 'claud',

    [string]$Dest,

    [switch]$List,

    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

$available = Get-ChildItem -Path $Root -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') } |
    Select-Object -ExpandProperty Name

if ($List) {
    Write-Host '可用 skill:'
    foreach ($name in $available) {
        $versionLine = Select-String -Path (Join-Path $Root "$name\SKILL.md") -Pattern '^version:' |
            Select-Object -First 1
        $version = if ($versionLine) { $versionLine.Line -replace '^version:\s*"?([^"]*)"?.*$', '$1' } else { '' }
        Write-Host ("  {0,-28} {1}" -f $name, $version)
    }
    return
}

if (-not $Dest) {
    $map = @{
        claud      = Join-Path $HOME '.Claud\skills'
        codex      = Join-Path $HOME '.codex\skills'
        agents     = Join-Path $HOME '.agents\skills'
        'cc-switch' = Join-Path $HOME '.cc-switch\skills'
    }
    $Dest = $map[$Target]
}

if (-not $Skill -or $Skill.Count -eq 0) {
    $Skill = $available
}

foreach ($name in $Skill) {
    $src = Join-Path $Root $name
    if (-not (Test-Path (Join-Path $src 'SKILL.md'))) {
        throw "未知 skill: $name。可用: $($available -join ', ')"
    }

    $out = Join-Path $Dest $name
    if (Test-Path $out) {
        if ($Force) {
            Remove-Item -Path $out -Recurse -Force
        } else {
            throw "已存在: $out（使用 -Force 覆盖）"
        }
    }

    New-Item -ItemType Directory -Path $out -Force | Out-Null
    $exclude = @('.git', 'dist', '__pycache__', '.pytest_cache', '.DS_Store', 'Thumbs.db')
    Get-ChildItem -Path $src -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $out -Recurse -Force
    }
    Write-Host "已安装 $name -> $out"
}

Write-Host '完成。重启 agent 会话后生效。'
