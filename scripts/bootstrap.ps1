param(
    [switch]$Check,
    [switch]$DryRun,
    [switch]$SourcesOnly,
    [switch]$WithFsgen,
    [string]$Python = "python"
)
$arguments = @("$PSScriptRoot/bootstrap.py")
if ($Check) { $arguments += "--check" }
if ($DryRun) { $arguments += "--dry-run" }
if ($SourcesOnly) { $arguments += "--sources-only" }
if ($WithFsgen) { $arguments += "--with-fsgen" }
& $Python @arguments
exit $LASTEXITCODE
