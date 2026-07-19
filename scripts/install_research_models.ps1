param(
    [string]$OllamaPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
    [ValidateRange(1, 10)]
    [int]$MaxAttempts = 5,
    [string[]]$Models = @(
        "gemma3:4b",
        "qwen3:4b",
        "phi4-mini:3.8b",
        "deepseek-r1:7b"
    )
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $OllamaPath)) {
    throw "Ollama introuvable : $OllamaPath"
}

$installedTags = @(
    & $OllamaPath list |
        Select-Object -Skip 1 |
        ForEach-Object { ($_ -split '\s+')[0] } |
        Where-Object { $_ }
)

foreach ($model in $Models) {
    if ($installedTags -contains $model) {
        Write-Output "MODEL_PRESENT $model $(Get-Date -Format o)"
        continue
    }

    $completed = $false
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Write-Output "PULL_START $model attempt=$attempt/$MaxAttempts $(Get-Date -Format o)"
        & $OllamaPath pull $model
        if ($LASTEXITCODE -eq 0) {
            Write-Output "PULL_DONE $model attempt=$attempt $(Get-Date -Format o)"
            $completed = $true
            $installedTags += $model
            break
        }
        if ($attempt -lt $MaxAttempts) {
            $delaySeconds = [Math]::Min(60, [Math]::Pow(2, $attempt + 1))
            Write-Output "PULL_RETRY $model exit=$LASTEXITCODE wait=${delaySeconds}s"
            Start-Sleep -Seconds $delaySeconds
        }
    }
    if (-not $completed) {
        throw "Ollama pull failed after $MaxAttempts attempts: $model"
    }
}

Write-Output "MODEL_INVENTORY"
& $OllamaPath list
if ($LASTEXITCODE -ne 0) {
    throw "Impossible de produire l'inventaire final Ollama."
}
