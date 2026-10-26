# Instalação e operação

Como instalar, configurar, ligar, atualizar e fazer backup do Planner de Ofícios.

## Requisitos

| Item | Versão | Observação |
|---|---|---|
| Windows | 10 ou 11 | Os scripts `iniciar.bat` e `parar.bat` são para Windows. A API também roda em Linux |
| Python | 3.12 ou mais novo | Testado no 3.14 |
| Node.js | 20 ou mais novo | Só para compilar as telas (`npm run build`) |
| MySQL | 8.x | Portátil (sem instalação), Docker ou servidor existente |
| Microsoft Edge | qualquer recente | Só para os testes de tela |

## 1. Banco de dados

Escolha uma das três opções.

### a) MySQL portátil, sem administrador (como está hoje)

O MySQL 8.4 oficial da Oracle fica descompactado em `%USERPROFILE%\planner-oficios-mysql\`:

| Item | Onde |
|---|---|
| Programa | `server\` |
| Dados | `dados\` — **faça backup desta pasta** (com o MySQL desligado) ou use `mysqldump` |
| Backups | `backups\` — cópias `mysqldump` feitas antes de cada atualização do banco |
| Configuração | `my.ini` — porta **3307**, aceita conexões só desta máquina (`bind-address=127.0.0.1`), protocolo X desligado |
| Senha do root | `senha-root.txt` (fica só nesta máquina, fora do repositório) |
| Usuário do sistema | `oficios` — acessa só o banco `oficios`. A senha está no `backend\.env` |
| Log | `mysql-erros.log` |

Esse MySQL é independente de qualquer outro instalado na máquina (por exemplo, um na porta 3306).

Para montar do zero:
1. Baixe o ZIP do MySQL 8.4 (Windows, x64), descompacte em `server\` e crie o `my.ini` com `port=3307`,
   `bind-address=127.0.0.1` e `datadir` apontando para `dados\`.
2. Inicialize os dados com `mysqld --initialize`.
3. Crie o banco e o usuário:

```sql
CREATE DATABASE oficios CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'oficios'@'127.0.0.1' IDENTIFIED BY '<senha forte>';
GRANT ALL PRIVILEGES ON oficios.* TO 'oficios'@'127.0.0.1';
```

### b) Docker

```powershell
docker compose up -d
```

Sobe o MySQL 8.4 na porta 3307, aceitando conexões só da própria máquina, com os dados no volume `mysql_dados`.
**Troque as senhas de exemplo do `docker-compose.yml` antes de usar em produção.**

### c) Um MySQL que já existe

Crie o banco `oficios` e um usuário só para ele, como no SQL acima, e aponte o `DATABASE_URL` para lá.

## 2. Back-end

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite o `.env`, no mínimo `DATABASE_URL` e `JWT_SECRET`, e crie as tabelas:

```powershell
alembic upgrade head            # cria/atualiza as tabelas (migrações 0001 … 0010)
python -m scripts.inicializar   # cria o 1º administrador (pede a senha) e os feriados nacionais
```

`scripts.inicializar` aceita `--login`, `--nome`, `--anos 2026 2027` e `--gerar-senha`, que gera e mostra uma senha
aleatória. Para tornar uma conta MASTER ou recuperar o acesso, use
`python -m scripts.definir_perfil --login admin --perfil MASTER`.

### Configuração (`backend/.env`)

| Variável | Padrão | O que faz |
|---|---|---|
| `APP_HOST` | `0.0.0.0` | `0.0.0.0` aceita acesso da rede; `127.0.0.1` só desta máquina |
| `APP_PORTA` | `3112` | Porta do sistema |
| `DATABASE_URL` | `mysql+pymysql://oficios:…@127.0.0.1:3307/oficios?charset=utf8mb4` | Conexão com o banco |
| `JWT_SECRET` | `troque-esta-chave` | Chave que assina as sessões. **Obrigatório trocar**: com a chave padrão o sistema não aceita acesso pela rede. Gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_EXPIRA_MINUTOS` | `480` | Duração da sessão (8 horas) |
| `UPLOAD_MAX_MB` | `20` | Tamanho máximo de cada arquivo |
| `DIAS_ATENCAO` | `30` | Dias úteis para um pendente entrar em atenção |
| `DIAS_CRITICO` | `45` | Dias úteis para um pendente ficar crítico |
| `LOGIN_MAX_TENTATIVAS` | `5` | Senhas erradas seguidas antes do bloqueio |
| `LOGIN_BLOQUEIO_MINUTOS` | `5` | Duração do bloqueio |
| `VERIFICACAO_HORAS` | `24` | Intervalo da verificação dos arquivos (0 desliga a automática) |
| `STORAGE_DIR` | `backend/storage` | Pasta dos documentos |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Origens extras liberadas (o servidor de desenvolvimento do Vite). A rede interna já é liberada |

Depois de mudar o `.env`, reinicie o sistema.

## 3. Front-end

```powershell
cd frontend
npm install
npm run build      # gera frontend/dist, que a API passa a servir
```

Rode `npm run build` de novo sempre que o front-end for alterado. Depois, basta recarregar a página: não precisa
reiniciar a API.

## 4. Ligar e desligar

| Ação | Como |
|---|---|
| Ligar | Duplo clique em **`iniciar.bat`**. Liga o MySQL portátil (se não estiver ligado) e o sistema, e mostra os endereços. Pode fechar a janela depois |
| Desligar | Duplo clique em **`parar.bat`** |
| Ligar manualmente | `cd backend` e `.venv\Scripts\python -m app` |

- Depois de reiniciar o Windows ou fazer logoff, rode o `iniciar.bat` de novo.
- Endereços: `http://localhost:3112` nesta máquina e `http://<IP-da-máquina>:3112` nos outros computadores.
  A documentação interativa da API fica em `/docs`.
- Logs: `backend\logs\api.log` (sistema) e `%USERPROFILE%\planner-oficios-mysql\mysql-erros.log` (MySQL).

## 5. Acesso pela rede

O sistema escuta em `0.0.0.0:3112` e, ao ligar, mostra o endereço para os outros computadores. É preciso liberar a
porta no firewall do Windows **uma vez**, num PowerShell aberto como administrador:

```powershell
New-NetFirewallRule -DisplayName "Planner de Oficios (API 3112)" -Direction Inbound -Protocol TCP -LocalPort 3112 -Action Allow -Profile Domain,Private
```

Para aceitar só esta máquina, use `APP_HOST=127.0.0.1`.

## 6. Backup

O que precisa de backup:

| O quê | Onde | Como |
|---|---|---|
| Banco | MySQL `oficios` | `mysqldump` (abaixo) ou cópia da pasta `dados\` com o MySQL desligado |
| Documentos | `backend\storage\` | Cópia da pasta inteira (inclui a lixeira) |
| Configuração | `backend\.env` | Cópia guardada em lugar seguro: tem a senha do banco e a chave das sessões |

```powershell
$mysql = "$env:USERPROFILE\planner-oficios-mysql"
& "$mysql\server\bin\mysqldump.exe" -h 127.0.0.1 -P 3307 -u root -p --single-transaction --routines oficios > "$mysql\backups\oficios-$(Get-Date -Format yyyyMMdd-HHmm).sql"
```

Para restaurar: `mysql -h 127.0.0.1 -P 3307 -u root -p oficios < arquivo.sql`. Depois, copie a pasta `storage` de
volta.

A pasta `backend\storage` tem as permissões do Windows restritas ao dono da máquina, ao SISTEMA e aos
Administradores. Se outra conta precisar fazer backup dela, ajuste as permissões com `icacls`.

## 7. Atualizar o sistema

1. **Backup do banco** (`mysqldump`, acima). Faça isso sempre, antes de qualquer migração.
2. Atualize o código (`git pull`).
3. `cd backend`, `.venv\Scripts\pip install -r requirements.txt` e `.venv\Scripts\alembic upgrade head`.
4. `cd ..\frontend`, `npm install` e `npm run build`.
5. Reinicie: `parar.bat` e depois `iniciar.bat`.
6. Peça aos usuários para recarregar a página com **Ctrl+F5**.

Para conferir a versão do banco: `alembic current`. Para voltar uma migração: `alembic downgrade -1`. As migrações
foram testadas nos dois sentidos, mas a volta segura é restaurar o backup.

## 8. Rotina anual

- **Feriados:** em **Feriados**, clique em *Cadastrar nacionais de {ano}* para o ano novo e adicione os feriados
  locais. Sem isso, o prazo conta esses dias como úteis.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `iniciar.bat` diz que o MySQL não subiu | Veja `mysql-erros.log`. Confira se a porta 3307 está livre e se o disco tem espaço |
| `iniciar.bat` diz que o sistema não subiu | Veja as últimas linhas de `backend\logs\api.log` (o script mostra 15 linhas) |
| "JWT_SECRET padrão ou curta" ao ligar | Gere uma `JWT_SECRET` própria no `.env` (o comando aparece na própria mensagem) |
| Outros computadores não abrem o sistema | Libere a porta 3112 no firewall (seção 5) e confira o IP mostrado ao ligar |
| Telas antigas depois de atualizar | Ctrl+F5 no navegador e confira se o `npm run build` rodou |
| Contador vermelho em **Arquivos** | Um documento sumiu ou foi alterado fora do sistema: recupere do backup da pasta `storage` ou envie de novo |
| Ninguém consegue entrar como master | `python -m scripts.definir_perfil --login <login> --perfil MASTER` |
