# Liga o Planner de Ofícios: MySQL isolado (porta 3307) + sistema (porta 3112).
# Use o iniciar.bat (duplo clique). Pode rodar de novo sem problema: o que já estiver ligado é mantido.

$ErrorActionPreference = "Stop"
$projeto = $PSScriptRoot
$mysql = Join-Path $env:USERPROFILE "planner-oficios-mysql"
$backend = Join-Path $projeto "backend"
$logs = Join-Path $backend "logs"

function Escutando($porta) { [bool](Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue) }

# Cria o processo pelo WMI: fica totalmente independente desta janela (pode fechá-la que continua rodando).
function IniciarDesanexado($comando, $pasta) {
    $janelaOculta = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = $comando; CurrentDirectory = $pasta; ProcessStartupInformation = $janelaOculta
    }
    if ($r.ReturnValue -ne 0) { throw "Falha ao iniciar processo (codigo $($r.ReturnValue)): $comando" }
}

function Aguardar($porta, $segundos) {
    for ($i = 0; $i -lt $segundos * 2; $i++) {
        if (Escutando $porta) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

# 1. Banco
if (Escutando 3307) {
    Write-Host "MySQL ja estava ligado (porta 3307)."
} else {
    Write-Host "Ligando o MySQL..."
    IniciarDesanexado "`"$mysql\server\bin\mysqld.exe`" --defaults-file=`"$mysql\my.ini`"" $mysql
    if (-not (Aguardar 3307 60)) {
        Write-Host "O MySQL nao subiu. Veja $mysql\mysql-erros.log" -ForegroundColor Red
        exit 1
    }
    Write-Host "MySQL ligado."
}

# 2. Sistema (API + telas)
if (Escutando 3112) {
    Write-Host "Sistema ja estava ligado (porta 3112)."
} else {
    if (-not (Test-Path (Join-Path $projeto "frontend\dist\index.html"))) {
        Write-Host "Aviso: as telas nao foram compiladas (rode 'npm run build' em frontend). So a API vai responder." -ForegroundColor Yellow
    }
    New-Item -ItemType Directory -Force $logs | Out-Null
    Write-Host "Ligando o sistema..."
    IniciarDesanexado "cmd.exe /c `"`"$backend\.venv\Scripts\python.exe`" -m app 1>>`"$logs\api.log`" 2>&1`"" $backend
    if (-not (Aguardar 3112 30)) {
        Write-Host "O sistema nao subiu. Veja $logs\api.log" -ForegroundColor Red
        Get-Content "$logs\api.log" -Tail 15 -ErrorAction SilentlyContinue
        exit 1
    }
    Write-Host "Sistema ligado."
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "Nesta maquina:       http://localhost:3112" -ForegroundColor Green
if ($ip) { Write-Host "Outros computadores: http://${ip}:3112" -ForegroundColor Green }
