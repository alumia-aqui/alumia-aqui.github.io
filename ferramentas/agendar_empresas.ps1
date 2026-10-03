# Cria (ou recria) a tarefa agendada que roda atualizar_empresas.ps1 toda semana.
# Rodar uma vez, no PowerShell, dentro da pasta do repositório:
#   powershell -ExecutionPolicy Bypass -File ferramentas\agendar_empresas.ps1

$script = Join-Path $PSScriptRoot "atualizar_empresas.ps1"
$acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory (Split-Path $PSScriptRoot -Parent)
$quando = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At "20:00"
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 4)

Register-ScheduledTask -TaskName "Alumia Aqui - empresas" -Action $acao -Trigger $quando `
    -Settings $config -Description "Atualiza as empresas dos candidatos com os dados da Receita Federal." -Force | Out-Null

Write-Output "Tarefa 'Alumia Aqui - empresas' criada: todo domingo às 20h."
Write-Output "Para conferir ou remover: Agendador de Tarefas do Windows."
