param(
    [string]$Scores = (Join-Path $PSScriptRoot 'examples\rubric\paired_scores.csv'),
    [string]$OutputPath,
    [string]$ModelA = 'model_a',
    [string]$ModelB = 'model_b',
    [string]$Sheet,
    [string]$Manifest
)

$ErrorActionPreference = 'Stop'
$command = Join-Path $PSScriptRoot '.venv\Scripts\deepeval.exe'
if (-not (Test-Path -LiteralPath $command)) {
    throw 'Local environment is missing. Follow README.local.zh-CN.md first.'
}
$settings = @{
    DEEPEVAL_TELEMETRY_OPT_OUT = '1'
    DEEPEVAL_DISABLE_DOTENV = '1'
    DEEPEVAL_UPDATE_WARNING_OPT_IN = '0'
    DEEPEVAL_FILE_SYSTEM = 'READ_ONLY'
    CONFIDENT_OPEN_BROWSER = '0'
    PYTHONUTF8 = '1'
}
$previous = @{}
try {
    foreach ($name in $settings.Keys) {
        $previous[$name] = @{
            Exists = (Test-Path -LiteralPath "Env:$name")
            Value = [Environment]::GetEnvironmentVariable($name, 'Process')
        }
        [Environment]::SetEnvironmentVariable($name, $settings[$name], 'Process')
    }
    $cliArgs = @('rubric', 'compare', $Scores, '--model-a', $ModelA, '--model-b', $ModelB)
    if ($OutputPath) { $cliArgs += @('--output', $OutputPath) }
    if ($Sheet) { $cliArgs += @('--sheet', $Sheet) }
    if ($Manifest) { $cliArgs += @('--manifest', $Manifest) }
    & $command @cliArgs
    $resultCode = $LASTEXITCODE
} finally {
    foreach ($name in $previous.Keys) {
        if ($previous[$name].Exists) {
            [Environment]::SetEnvironmentVariable($name, $previous[$name].Value, 'Process')
        } else {
            Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        }
    }
}
if ($resultCode -ne 0) { throw "Rubric comparison failed (exit $resultCode)." }
