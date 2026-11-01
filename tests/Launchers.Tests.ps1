# Pester tests: every PowerShell script in the repo must parse, and PSScriptAnalyzer
# must report no Error-severity findings (settings in tests/PSScriptAnalyzerSettings.psd1).
BeforeDiscovery {
    $script:RepoRoot = Split-Path -Parent $PSScriptRoot
    $script:Scripts = Get-ChildItem -Path $script:RepoRoot -Recurse -Filter '*.ps1' |
        Where-Object { $_.FullName -notmatch '[\\/]tests[\\/]' }
}

Describe 'PowerShell scripts' {
    It 'finds at least one script' {
        $found = Get-ChildItem -Path (Split-Path -Parent $PSScriptRoot) -Recurse -Filter '*.ps1' |
            Where-Object { $_.FullName -notmatch '[\\/]tests[\\/]' }
        @($found).Count | Should -BeGreaterThan 0
    }

    It 'parses without errors: <_.Name>' -ForEach $script:Scripts {
        $tokens = $null
        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile($_.FullName, [ref]$tokens, [ref]$errors) | Out-Null
        $msg = ($errors | ForEach-Object { "$($_.Extent.StartLineNumber): $($_.Message)" }) -join "`n"
        $errors.Count | Should -Be 0 -Because $msg
    }

    It 'has no PSScriptAnalyzer errors: <_.Name>' -ForEach $script:Scripts {
        $settings = Join-Path (Split-Path -Parent $PSScriptRoot) 'tests/PSScriptAnalyzerSettings.psd1'
        $findings = Invoke-ScriptAnalyzer -Path $_.FullName -Settings $settings
        $msg = ($findings | ForEach-Object { "$($_.Line): $($_.RuleName) - $($_.Message)" }) -join "`n"
        @($findings).Count | Should -Be 0 -Because $msg
    }
}
