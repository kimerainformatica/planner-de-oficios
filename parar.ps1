# Desliga o Planner de Ofícios (sistema na porta 3112 e o MySQL isolado na 3307).
# Não mexe no outro MySQL da máquina (porta 3306).

$mysql = Join-Path $env:USERPROFILE "planner-oficios-mysql"

$api = Get-NetTCPConnection -LocalPort 3112 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($api) {
    Stop-Process -Id $api.OwningProcess -Force
    Write-Host "Sistema desligado."
} else {
    Write-Host "Sistema ja estava desligado."
}

if (Get-NetTCPConnection -LocalPort 3307 -State Listen -ErrorAction SilentlyContinue) {
    # Desligamento limpo do MySQL (grava tudo em disco antes de sair)
    $senha = ((Get-Content "$mysql\senha-root.txt" -TotalCount 1) -split ": ")[-1].Trim()
    $env:MYSQL_PWD = $senha
    & "$mysql\server\bin\mysqladmin.exe" --defaults-file="$mysql\my.ini" -uroot shutdown
    Remove-Item Env:MYSQL_PWD
    Write-Host "MySQL desligado."
} else {
    Write-Host "MySQL ja estava desligado."
}
