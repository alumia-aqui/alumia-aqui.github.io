# Atualiza dados/empresas.json com os arquivos da Receita Federal e envia ao GitHub.
# Roda no computador local, porque a Receita recusa conexões vindas do GitHub.
# Agendamento mensal: ver README, seção "Como rodar".

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz
Start-Transcript -Path (Join-Path $PSScriptRoot "ultima_execucao_empresas.log") -Force | Out-Null

try {
    git pull --quiet
    if ($LASTEXITCODE -ne 0) { throw "git pull falhou" }

    # Lista de candidatos atualizada: apaga o arquivo do TSE da eleição mais recente para baixar de novo.
    Get-ChildItem "pipeline\dados_brutos\consulta_cand_*.zip" -ErrorAction SilentlyContinue |
        Sort-Object Name | Select-Object -Last 1 | Remove-Item

    python pipeline\gerar_empresas.py
    if ($LASTEXITCODE -ne 0) { throw "gerar_empresas.py falhou" }

    git add dados/empresas.json
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        git commit -m "Empresas: atualização mensal com os dados da Receita Federal"
        # Pode ter chegado coisa nova no GitHub durante o download: junta antes de enviar.
        git pull --rebase --quiet
        if ($LASTEXITCODE -ne 0) { throw "git pull --rebase falhou" }
        git push
        if ($LASTEXITCODE -ne 0) { throw "git push falhou" }
        Write-Output "Empresas atualizadas e enviadas."
    } else {
        Write-Output "Nenhuma mudança nas empresas."
    }
} finally {
    Stop-Transcript | Out-Null
}
