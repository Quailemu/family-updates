Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$patterns = @(
    "â€“",  # en dash mojibake
    "â€”",  # em dash mojibake
    "â€¢",  # bullet mojibake
    "â†",   # arrow mojibake prefix
    "Ã."    # common UTF-8/Latin-1 mismatch pattern
)

$targets = @("app.py", "docs", "supabase", "pages", "config.py", "README.md")
$existingTargets = $targets | Where-Object { Test-Path $_ }

if (-not $existingTargets) {
    Write-Host "No target paths found. Skipping encoding check."
    exit 0
}

$regex = [string]::Join("|", $patterns)
$matches = rg -n -S --glob "!*.png" --glob "!*.jpg" --glob "!*.jpeg" --glob "!*.gif" --glob "!*.mp4" $regex $existingTargets

if ($LASTEXITCODE -eq 0 -and $matches) {
    Write-Host "Encoding check failed. Possible mojibake found:" -ForegroundColor Red
    Write-Host $matches
    exit 1
}

if ($LASTEXITCODE -gt 1) {
    Write-Host "Encoding check could not run correctly (rg error)." -ForegroundColor Yellow
    exit $LASTEXITCODE
}

Write-Host "Encoding check passed."
exit 0

