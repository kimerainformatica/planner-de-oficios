# Consumo de recursos e servidor necessário

Quanto o Planner de Ofícios usa de processador, memória, threads, disco e rede, e qual servidor ele precisa para rodar.
Os números foram **medidos** em 04/11/2026 na API real, com **3.000 ofícios simulados** (o volume de vários anos).

## Resumo

| Recurso | Uso normal | Pico medido | Servidor recomendado |
|---|---|---|---|
| Processador | Quase parado | 1 núcleo por ≈ 6 s ao exportar o PDF do painel | **1 a 2 vCPU** |
| RAM (API + MySQL + sistema) | ≈ 0,85 GB | ≈ 1 GB | **2 GB** |
| Threads | API 4 · MySQL 34 | API ≈ 33 sob carga | Qualquer servidor |
| Disco | ≈ 1,5 GB (programas + banco) | **Cresce com os documentos enviados** | **50 a 100 GB SSD** |
| Rede | Poucos KB por tela | Envio e download de documentos (até 20 MB cada) | Qualquer link |

O **servidor é igual nas duas versões do visual**: as branches `main` ("Correnteza") e `visual-classico` só mudam as
telas. A diferença aparece no **computador de quem usa**: a versão clássica usa de 3 a 9 vezes menos processador no
navegador (veja [Versões do visual](#versões-do-visual-custo-no-computador-de-quem-usa)).

## Ambiente medido

| Item | Valor |
|---|---|
| Dados | 3.000 ofícios em 12 meses, 20 clientes, histórico de status e feriados nacionais |
| Software | Python 3.12, FastAPI + uvicorn (1 processo), MySQL 8.4 com a configuração padrão |
| Máquina | Intel Core i5-2400 (4 threads, 2011), 12 GB de RAM, HD mecânico de 5.400 rpm |

Esta máquina é antiga. Num servidor com processador atual, as exportações e o login ficam mais rápidos.

## Processador

### Custo de cada operação

| Operação | Tempo de resposta | Observação |
|---|---|---|
| **Exportar PDF** do painel (3.000 ofícios, 320 KB) | **6,3 a 6,4 s** | A operação mais pesada. Ocupa 1 núcleo inteiro (ReportLab) |
| **Exportar Excel** com gráficos (3.000 ofícios, 203 KB) | **3,0 s** | Ocupa 1 núcleo inteiro (openpyxl) |
| Login | 0,8 s | Proposital: a senha usa PBKDF2-SHA256 com 600 mil iterações, que dificulta adivinhar senhas |
| 10 logins ao mesmo tempo | 2,3 s no total | Começo do expediente |
| Análise do painel (gráficos e tabelas) | 226 a 249 ms | Calculada a cada abertura, sem cache, para o prazo valer sempre |
| Contadores do painel | 25 ms | |
| Lista de ofícios (50 por página) | 27 ms | |
| Verificação diária dos arquivos (SHA-256) | Segundos por GB de documentos | Uma vez por dia, em segundo plano |

O tempo das exportações cresce junto com o número de ofícios do filtro. Com 300 ofícios, ele fica perto de um décimo.

### Acessos simultâneos (painel, contadores e lista)

| Pessoas ao mesmo tempo | Tempo médio (p50) | 95% das respostas em até (p95) | Erros |
|---|---|---|---|
| 10 | 111 a 309 ms | 0,8 a 1,1 s | 0 |
| 25 | 228 a 246 ms | 2,4 a 3,3 s | 0 |

O teste inteiro (as duas exportações, os acessos simultâneos e 11 logins) consumiu **10 a 15 segundos de CPU**, quase
todos nas exportações e nos logins.

O Python executa uma operação de cada vez por processo (GIL). Por isso, durante uma exportação em PDF, as outras telas
ficam mais lentas por alguns segundos:

- **1 vCPU** basta para o uso normal de uma equipe.
- **2 vCPU** evitam que o MySQL e as exportações disputem o mesmo núcleo.

## Memória (RAM)

| Parte | Em repouso | Pico | Quando acontece o pico |
|---|---|---|---|
| API Python (também entrega as telas) | 89 a 90 MB | **153 MB** | Exportações + 25 acessos simultâneos. Fica em ≈ 143 MB depois |
| MySQL 8.4 (buffer do InnoDB de 128 MB, padrão) | ≈ 460 MB | ≈ 500 MB | |
| Sistema operacional Linux + proxy HTTPS | ≈ 300 MB | ≈ 350 MB | |
| **Total** | **≈ 0,85 GB** | **≈ 1 GB** | |

- O Node.js só é usado para compilar as telas (`npm run build`) e não fica rodando.
- Com 1 GB de RAM o servidor fica no limite. Use **2 GB**.
- Para economizar memória, reduza o MySQL com `innodb_buffer_pool_size=64M`, porque o banco é pequeno.

## Threads e conexões

| Processo | Threads | Observação |
|---|---|---|
| API (uvicorn) | 4 em repouso, ≈ 33 sob carga | Um processo. As rotas rodam num pool de threads (AnyIO, até 40) que cresce sob demanda. Uma thread a mais faz a verificação diária dos arquivos |
| MySQL | 34 | Threads internas do InnoDB + uma por conexão aberta |
| Conexões API → MySQL | Até 15 | Padrão do SQLAlchemy: 5 fixas + 10 extras |

## Disco (armazenamento)

| Item | Tamanho |
|---|---|
| MySQL 8.4 (programa + pasta de dados) | ≈ 1,2 GB. Em Linux, pelo pacote da distribuição, ≈ 250 MB + dados |
| Banco do sistema (3.000 ofícios + histórico) | ≈ 2 MB. O banco quase não cresce |
| Ambiente Python (`.venv`) | 214 MB, sendo ≈ 105 MB sem o Playwright, que só é usado nos testes |
| Interface compilada | 0,6 MB |
| **Documentos** (`backend/storage`, com a lixeira) | **O que mais cresce** (veja abaixo) |

### Documentos

Cada ofício pode ter até 4 documentos: o ofício, a referência, a resposta e o comprovante. Cada um tem no máximo 20 MB
(`UPLOAD_MAX_MB`). Com um PDF típico de ≈ 1 MB e ≈ 3 documentos por ofício:

| Ofícios por ano | Documentos por ano | Em 5 anos |
|---|---|---|
| 500 | ≈ 1,5 GB | ≈ 8 GB |
| 1.000 | ≈ 3 GB | ≈ 15 GB |
| 3.000 | ≈ 9 GB | ≈ 45 GB |

Arquivos substituídos ou removidos ficam na lixeira e continuam ocupando espaço. Conte também o espaço do backup da
pasta `storage`, se ele ficar no mesmo disco.

## Rede

| Tráfego | Tamanho |
|---|---|
| Interface (baixada uma vez por computador) | 0,6 MB |
| Cada tela (dados em JSON) | 1 a 25 KB |
| Exportação Excel / PDF | 0,2 a 0,3 MB por 3.000 ofícios |
| Envio ou download de um documento | Até 20 MB |

## Versões do visual: custo no computador de quem usa

| Branch | Visual |
|---|---|
| `main` | "Correnteza": ícones e login animados, contadores que contam do zero e fontes próprias. Tem **16 animações em loop contínuo** |
| `visual-classico` | Sem nenhuma animação nem transição (`animation: none`), com as fontes do sistema |

A API, o banco e as regras são os mesmos, então **o consumo do servidor é idêntico** nas duas. Todo o resto desta
página vale para as duas versões.

### Tamanho das telas compiladas (`frontend/dist`)

| | Correnteza (`main`) | Clássico (`visual-classico`) |
|---|---|---|
| Total | 606 KB em 10 arquivos | **461 KB em 5 arquivos** (−24%) |
| JavaScript | 432 KB (132 KB compactado) | 419 KB (127 KB compactado) |
| CSS | 60 KB | 32 KB |
| Fontes | 5 arquivos, 104 KB | Nenhuma (usa as do sistema) |

### Processador do navegador

Medido no Microsoft Edge (sem placa de vídeo dedicada, como num computador de escritório simples), com os mesmos 3.000
ofícios. "Abrir" é o processador gasto para carregar a tela. "Parada" é o que a tela continua gastando, aberta e sem
ninguém mexer. Os números somam todos os processos do Edge (tela, desenho e navegador) e são a faixa de duas rodadas.

| Tela | Abrir: Correnteza | Abrir: Clássico | Parada: Correnteza | Parada: Clássico |
|---|---|---|---|---|
| Login (inclui abrir o navegador) | 5,0 s | 3,7 a 3,8 s | **34 a 36%** de 1 núcleo | **4 a 5%** |
| Painel | 3,2 a 3,9 s | **1,1 a 1,3 s** | **40 a 50%** | **14 a 15%** |
| Lista de ofícios | 1,4 a 1,5 s | **0,5 s** | 17 a 23% | **2 a 3%** |
| Tela do ofício | 2,1 a 3,3 s | **0,5 s** | 42 a 44% | **6%** |
| Passar o mouse pelo menu (≈ 4 s) | 2,8 s | **0,3 s** | — | — |

| Thread principal da página, com a tela parada | Correnteza | Clássico |
|---|---|---|
| Login | 1,1 s a cada 10 s (11%) | ≈ 0 |
| Painel | 1,7 s a cada 10 s (17%) | ≈ 0 |
| Tela do ofício | 1,0 s a cada 10 s (10%) | ≈ 0 |

| Memória da página | Correnteza | Clássico |
|---|---|---|
| JavaScript (heap) | 2 a 5,4 MB | 2 a 5,4 MB (igual) |
| Elementos na tela do ofício | 3.310 | 3.023 |

### O que isso significa

- **A Correnteza nunca fica parada.** Com a tela aberta e ninguém mexendo, ela continua usando de 17% a 50% de um
  núcleo, por causa das animações em loop. Num computador antigo, isso esquenta a máquina, gasta bateria em notebook e
  deixa os outros programas mais lentos.
- **A Clássica fica praticamente parada** quando ninguém mexe. Para abrir o painel, a lista e o ofício, ela gasta de
  3 a 6 vezes menos processador.
- **A memória é a mesma.** A diferença está no processador e na placa de vídeo, não na RAM.
- **Recomendação:**
  - computadores com processador de 4 núcleos ou mais e placa de vídeo razoável: Correnteza;
  - computadores simples, antigos ou com várias abas e programas abertos ao mesmo tempo: Clássica.
- Com a opção do Windows "Mostrar animações" desligada (`prefers-reduced-motion`), a Correnteza para as animações
  sozinha. É uma alternativa para máquinas específicas sem trocar a versão (não medida aqui).

## Servidor recomendado

| Recurso | Mínimo | Recomendado |
|---|---|---|
| vCPU | 1 | 2 |
| RAM | 2 GB | 2 a 4 GB |
| Disco | 20 GB SSD | 50 a 100 GB SSD/NVMe, conforme o volume de documentos |
| Sistema | Ubuntu 24.04 LTS ou Windows 10/11 | Ubuntu 24.04 LTS |
| Software | Python 3.12+ e MySQL 8.x | Python 3.12+ e MySQL 8.4 |

### No mesmo servidor do Dashboard SISREG

Os dois sistemas podem dividir **um único MySQL**, cada um com seu banco e usuário.

| Recurso | Os dois juntos |
|---|---|
| RAM no pico | ≈ 1,6 GB (Python 153 MB + Node 426 MB + um MySQL ≈ 550 MB + sistema ≈ 350 MB) → use **4 GB** |
| vCPU | **2** |
| Disco | Os documentos daqui + ≈ 20 GB do Dashboard |

## Requisitos para rodar fora da rede interna

1. **HTTPS obrigatório:** um proxy (Caddy ou Nginx) com certificado na frente da porta 3112, porque o token de login e
   os documentos passam por ali.
2. **MySQL fechado:** continua escutando só em `127.0.0.1`.
3. **`JWT_SECRET` própria:** o sistema já se recusa a subir na rede sem ela.
4. **Firewall:** só as portas 22 (SSH, por chave) e 443 abertas.
5. **Backup fora do servidor:** `mysqldump` diário e cópia da pasta `storage`.

## Como medimos

- **Teste:** um script cria um banco temporário com 3.000 ofícios, sobe a API real (`python -m app`), faz o login e
  chama o painel, a lista e as duas exportações. Depois repete com 10 e 25 acessos simultâneos e 10 logins
  simultâneos. Foram três rodadas, e as tabelas mostram a faixa entre elas.
- **Memória, CPU e threads:** contadores do Windows do processo da API (`PeakWorkingSetSize`, tempo de CPU e número
  de threads).
- **MySQL:** memória e threads do MySQL do Planner rodando nesta máquina.
- **Versões do visual:**
  - as duas branches foram compiladas (`npm ci` + `npm run build`) e servidas pela mesma API, com os mesmos dados;
  - um script controla o Edge pelo protocolo DevTools: abre login, painel, lista e ofício, espera a tela carregar e
    a deixa parada por 10 s;
  - o tempo de CPU de todos os processos do Edge vem de `SystemInfo.getProcessInfo`, e o da thread principal de
    `Performance.getMetrics`;
  - foram duas rodadas alternando as versões.
