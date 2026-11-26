# API

A API é REST/JSON, em `http://<máquina>:3112/api`. A documentação interativa (Swagger), com todos os campos e o
botão **Authorize**, fica em **`/docs`**. Esta página é o mapa geral.

## Autenticação

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=<login>&password=<senha>
```

A resposta traz `{"access_token": "...", "token_type": "bearer"}`. Nas demais chamadas, envie o cabeçalho
`Authorization: Bearer <token>`.

| Código | Quando |
|---|---|
| `401` | Token ausente, expirado ou de uma sessão encerrada (a senha foi trocada) |
| `403` | O perfil não permite a ação |
| `404` | O registro não existe ou o cliente não tem acesso a ele |
| `409` | Conflito: número ou protocolo repetido, tipo em uso, transição de status inválida |
| `422` | Dados inválidos, com a mensagem em português em `detail` |
| `429` | Login bloqueado por excesso de tentativas |

**Perfis** na coluna "Quem": **todos** = qualquer usuário logado (o cliente só enxerga os próprios ofícios);
**admin** = `ADMIN` do módulo ou `MASTER`. Nas rotas `/api/oficios`, `/api/anexos`, `/api/dashboard`, `/api/feriados`,
`/api/tipos`, `/api/exclusoes`, `/api/auditoria` e da lixeira, "admin" é o administrador do **Planner de Ofícios**
e é preciso ter acesso a esse módulo (senão, `403`). As rotas `/api/manutencao/*` exigem acesso ao módulo
**Manutenções Integradas**. O `MASTER` tem acesso e poder de administrador em todos os módulos.

## Autenticação, módulos e usuários

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| POST | `/api/auth/login` | — | Entra e devolve o token |
| GET | `/api/auth/me` | todos | Usuário atual, com o papel dele em cada módulo (`modulos`) |
| GET | `/api/modulos` | todos | Módulos que o usuário pode abrir, com o papel dele em cada um |
| GET | `/api/manutencao/resumo` | acesso à Manutenção | Papel do usuário no módulo (e a empresa, se for técnico) |
| GET | `/api/usuarios` | gestor | Lista os usuários (o master vê todos; o admin vê quem usa os módulos que ele administra). `?modulo=OFICIOS` filtra por quem tem acesso ao módulo |
| POST | `/api/usuarios` | gestor | Cria um usuário já habilitado nos módulos (`modulos`: lista de `{modulo, perfil}`). Só o master cria administradores e masters (`master: true`) |
| PATCH | `/api/usuarios/{id}` | gestor | Altera nome, login, situação, senha, `master` ou o acesso (`modulos`). Trocar a senha encerra as sessões da pessoa |

**gestor** = `MASTER` ou administrador de algum módulo. O administrador de um módulo só altera o acesso a **esse**
módulo, e só altera nome, login, senha e situação de quem usa apenas módulos que ele administra (veja `REGRAS.md`).

## Ofícios

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/api/oficios` | todos | Lista paginada com filtros: `busca`, `status`, `alerta`, `tipo`, `destinatario_tipo`, `data_inicio`, `data_fim`, `dono_id`, `ordem`, `pagina`, `por_pagina` |
| GET | `/api/oficios/setores?destinatario_tipo=SES` | todos | Setores já usados, para a sugestão (sem grafias duplicadas) |
| POST | `/api/oficios` | todos | Cadastra (entra como `PENDENTE_RESPOSTA`) |
| GET | `/api/oficios/{id}` | todos | Detalhe com histórico, anexos e evidências |
| PATCH | `/api/oficios/{id}` | todos | Edita os dados (dono ou admin) |
| PATCH | `/api/oficios/{id}/status` | todos | Registra a resposta (confirmado ou não), confirma o recebimento ou reabre |
| PATCH | `/api/oficios/{id}/resposta` | admin | Corrige a resposta atual (resultado, data, observação) |
| PATCH | `/api/oficios/{id}/recebimento` | admin | Corrige o recebimento (data, observação) |
| POST | `/api/oficios/{id}/desfazer` | admin | Desfaz a resposta ou o recebimento, com motivo |
| DELETE | `/api/oficios/{id}` | admin | Exclui o ofício, os documentos e a lixeira dele |
| POST | `/api/oficios/{id}/exclusao` | todos | Cliente: pede a exclusão, com motivo |
| DELETE | `/api/oficios/{id}/exclusao` | todos | Cliente: cancela o próprio pedido pendente |

## Documentos

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| POST | `/api/oficios/{id}/anexos/{tipo}` | todos | Envia ou substitui um documento (`multipart/form-data`, campo `arquivo`). A versão substituída vai para a lixeira |
| GET | `/api/anexos/{id}/download?inline=true` | todos | Baixa o arquivo (`inline=true` abre no navegador) |
| DELETE | `/api/anexos/{id}` | todos | Remove o documento (vai para a lixeira) |
| GET | `/api/lixeira?oficio_id=` | admin | Versões na lixeira (de um ofício ou de todos) |
| GET | `/api/lixeira/{id}/download` | admin | Baixa uma versão guardada |
| POST | `/api/lixeira/{id}/restaurar` | admin | Restaura (troca de lugar com o documento atual) |
| DELETE | `/api/lixeira/{id}` | admin | Apaga de vez (remove o arquivo do disco) |
| GET | `/api/arquivos/verificacao` | admin | Resultado da última verificação dos arquivos |
| POST | `/api/arquivos/verificacao` | admin | Verifica agora |

## Painel

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/api/dashboard/resumo` | todos | Contadores rápidos |
| GET | `/api/dashboard/prazos` | todos | Limites de atenção e crítico, em dias corridos |
| GET | `/api/dashboard/analise` | todos | Indicadores e agrupamentos dos gráficos (aceita os mesmos filtros da lista) |
| GET | `/api/dashboard/exportar?formato=xlsx\|pdf` | todos | Relatório do painel filtrado em Excel ou PDF |

## Cadastros

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/api/tipos` | todos | Tipos de ofício na ordem de exibição (inclui inativos e `em_uso`) |
| POST | `/api/tipos` | admin | Cria um tipo (o código é gerado a partir do nome) |
| PATCH | `/api/tipos/{codigo}` | admin | Altera nome, nome curto, exige entrega, ativo ou ordem. Mudar "exige entrega" ajusta os ofícios do tipo |
| DELETE | `/api/tipos/{codigo}` | admin | Apaga um tipo que nunca foi usado (senão `409`) |
| GET | `/api/feriados?ano=` | todos | Feriados do ano (só cadastro: não entram nos prazos desde a 2.2) |
| POST | `/api/feriados` | admin | Cadastra um feriado (data e descrição) |
| POST | `/api/feriados/nacionais/{ano}` | admin | Cadastra os feriados nacionais do ano |
| DELETE | `/api/feriados/{id}` | admin | Remove um feriado |

## Pedidos de exclusão e atividades

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/api/exclusoes` | todos | Admin: todos os pedidos. Cliente: os próprios |
| GET | `/api/exclusoes/pendentes` | admin | Quantidade aguardando decisão (contador do menu) |
| POST | `/api/exclusoes/{id}/aprovar` | admin | Aprova e exclui o ofício |
| POST | `/api/exclusoes/{id}/recusar` | admin | Recusa (o ofício continua) |
| GET | `/api/auditoria` | todos | Registro de atividades, com filtros `acao`, `usuario_id`, `oficio_id`, `data_inicio`, `data_fim` e paginação. O cliente vê o que fez e o que aconteceu nos próprios ofícios |

## Manutenções Integradas (helpdesk)

Todas exigem acesso ao módulo. **operacional** = `CLIENTE` do módulo; **técnico** = `TECNICO` (vê só os chamados
da própria empresa); **admin** = `ADMIN` do módulo ou `MASTER`. Regras em `REGRAS.md`.

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/api/manutencao/painel` | todos | Contagens (aguardando diagnóstico, vencendo, atrasados…), desempenho por empresa e os chamados mais perto do prazo |
| GET | `/api/manutencao/empresas` | todos | Empresas técnicas (`?ativas=true` só as ativas), com o nº de técnicos e de chamados |
| POST · PATCH · DELETE | `/api/manutencao/empresas[/{id}]` | admin | Cadastra, altera (nome, descrição, `prazo_horas`, ativo) ou exclui (só sem chamados e técnicos) |
| GET | `/api/manutencao/chamados` | todos | Lista, com filtros `status` (repetível), `empresa_id`, `situacao` (do prazo), `busca`, `meus` e paginação |
| POST | `/api/manutencao/chamados` | operacional, admin | Abre um chamado: `empresa_id`, `titulo`, `descricao`, `local`, `equipamento`, `ocorrido_em` |
| GET | `/api/manutencao/chamados/{id}` | todos | Detalhe com a linha do tempo e o que quem consulta pode fazer (`pode_*`) |
| POST | `/api/manutencao/chamados/{id}/assumir` | técnico | Vira o técnico responsável (não conta como diagnóstico) |
| POST | `/api/manutencao/chamados/{id}/interacoes` | todos | `multipart/form-data`: `texto`, `arquivo` e `diagnostico=true` (só técnico/admin) para a resposta técnica |
| POST | `/api/manutencao/chamados/{id}/relatorios` | técnico, admin | Relatório técnico no modelo do sistema (conta como diagnóstico) |
| GET | `/api/manutencao/relatorios/{id}` · `/pdf` | todos | O relatório, ou o PDF dele |
| GET | `/api/manutencao/interacoes/{id}/arquivo` | todos | Baixa o arquivo de uma interação (`inline`, `bruto`) |
| POST | `/api/manutencao/chamados/{id}/concluir` | técnico, admin | Conclui (exige diagnóstico), com `texto` opcional. Grava o tempo de solução em horas corridas (`solucao_horas_corridas`) |
| PATCH | `/api/manutencao/interacoes/{id}` | técnico, admin | Edita uma resposta técnica (diagnóstico ou complemento): `ocorrido_em`, `texto`, `motivo`. Registra uma `CORRECAO` |
| PATCH | `/api/manutencao/relatorios/{id}` | técnico, admin | Edita o relatório técnico (só os campos enviados, `atendido_em` e `motivo`). Registra uma `CORRECAO` |
| PUT | `/api/manutencao/interacoes/{id}/arquivo` | técnico, admin | Anexa ou substitui o relatório externo de uma resposta técnica ou relatório (formulário: `arquivo`, `motivo`). O arquivo anterior fica na `CORRECAO` |
| PATCH | `/api/manutencao/chamados/{id}/diagnostico` | técnico, admin | Corrige a data e a hora do diagnóstico (`diagnosticado_em`, `motivo` opcional). Refaz o prazo e o tempo de solução e registra uma `CORRECAO` na linha do tempo |
| GET | `/api/manutencao/quadro` | todos | Quadro por etapa (aguardando diagnóstico, em execução, aguardando peças, concluídos) e indicadores; `meus`, `empresa_id`, `dias` |
| GET | `/api/manutencao/avisos` | todos | Pendências de quem consulta (`total` e `itens` com `nivel`, `quantidade`, `titulo`, `link`) |
| GET | `/api/manutencao/planos-preventiva` | todos | Planos de preventiva (o técnico vê os da empresa dele), com a próxima data e os totais |
| POST | `/api/manutencao/planos-preventiva` | admin | Cria o plano (`empresa_id`, `titulo`, `descricao`, `local`, `equipamento`, `intervalo`, `unidade` DIAS/SEMANAS/MESES, `inicio`, `tolerancia_dias`) e gera as datas |
| PATCH · DELETE | `/api/manutencao/planos-preventiva/{id}` | admin | Altera (refaz só as datas futuras) ou exclui um plano sem nada vencido ou registrado |
| GET | `/api/manutencao/preventivas` | todos | Agenda e previsto x realizado por empresa (`de`, `ate`, `empresa_id`, `plano_id`, `situacao`, `aguardando_ateste`) |
| POST | `/api/manutencao/preventivas/{id}/realizar` | todos | Registra a realização (formulário: `realizada_em`, `executor`, `observacao`, `arquivo`) |
| POST | `/api/manutencao/preventivas/{id}/atestar` | operacional, admin | Ateste de quem fiscaliza (`observacao` opcional) |
| POST | `/api/manutencao/preventivas/{id}/nao-realizada` | operacional, admin | Marca como não realizada, com `motivo` |
| POST | `/api/manutencao/preventivas/{id}/reabrir` | admin | Desfaz o registro ainda sem ateste (apaga a evidência) |
| GET | `/api/manutencao/preventivas/{id}/arquivo` | todos | Baixa a evidência |
| GET | `/api/manutencao/tipos-solicitacao` | todos | Tipos de ofício aceitos na solicitação de peças/equipamentos |
| GET | `/api/manutencao/chamados/{id}/oficios/anexos/{anexo_id}` | todos | Baixa um documento do ofício de peças (anexado no Planner) pelo chamado |
| GET | `/api/manutencao/oficios-disponiveis` | operacional, admin | Ofícios do Planner ainda sem chamado, na visibilidade de quem consulta (`busca`, `limite` até 50) |
| PUT | `/api/manutencao/chamados/{id}/oficios/{oficio_id}` | operacional, admin | Vincula ao chamado um ofício que já existe no Planner (`404` se não for visível, `409` se já tiver chamado) |
| DELETE | `/api/manutencao/chamados/{id}/oficios/{oficio_id}` | dono do ofício, admin | Desfaz o vínculo; o ofício continua no Planner |
| POST | `/api/manutencao/chamados/{id}/oficios` | operacional, admin | Solicita peças/equipamentos: cadastra um ofício no Planner ligado ao chamado (`tipo`, `numero`, `data_oficio`, `protocolo`, `destinatario_tipo`, `destinatario_setor`, `itens`) |
| POST | `/api/manutencao/chamados/{id}/reabrir` · `/cancelar` | operacional, admin | Reabre um concluído ou cancela um em aberto, com `motivo` |

## Documentos

Módulo Documentos: ofícios e memorandos redigidos no app. Todas as rotas exigem acesso ao módulo; cada um vê o que
elaborou ou em que dá o De acordo (o administrador do módulo vê todos). O campo `registrar_no_planner` liga o ofício
ao Planner na emissão (só para quem usa o Planner).

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/api/documentos` | todos | Lista (`escopo` = `todos`, `meus` ou `assinar`; `tipo` = código do modelo, `status`, `etapa`, `pasta_id` (0: sem pasta), `prazo` = `com_prazo`, `alerta` ou `atrasados`, `busca`, `ordem` = `recentes` ou `prazo`, `pagina`) |
| GET | `/api/documentos/quadro` | todos | As cinco etapas (rascunho, aguardando assinatura, assinado, concluído, cancelado) com o total e os primeiros de cada uma; os mesmos filtros da lista |
| GET | `/api/documentos/resumo` | todos | Contadores do menu: aguardando a assinatura de quem consulta e prazos vencidos ou vencendo |
| GET | `/api/documentos/assinantes` | todos | Usuários que podem dar o De acordo (com cargo e matrícula) |
| POST | `/api/documentos` | todos | Começa um rascunho do modelo (`tipo` = código do modelo ativo; `pasta_id` e `prazo` opcionais), com os textos do modelo |
| GET · PATCH · DELETE | `/api/documentos/{id}` | quem vê · quem elaborou | Detalhe; salva o rascunho; descarta o rascunho |
| GET | `/api/documentos/{id}/pdf` | quem vê | PDF no modelo da unidade; no ofício emitido, o arquivo guardado, com as assinaturas GOV.BR (`bruto=true`: octet-stream; `assinado=true`: o assinado, mesmo cancelado) |
| POST | `/api/documentos/{id}/emitir` | quem elaborou | Número, data, código e hash; o ofício é cadastrado no Planner (`422` com o que falta) |
| POST | `/api/documentos/{id}/assinar` | quem elaborou · De acordo | Assinatura no app (`senha`), nos documentos com essa forma; `400` senha incorreta, `409` nada a assinar |
| POST | `/api/documentos/{id}/assinado` | quem elaborou · De acordo · admin | Documento com assinatura GOV.BR: PDF assinado (campo `arquivo`). Confere o documento, o certificado e a pessoa; `422` com o motivo da recusa |
| POST | `/api/documentos/{id}/cancelar` | quem elaborou · admin | Cancela o emitido (`motivo`) |
| POST | `/api/documentos/{id}/duplicar` | quem vê | Novo rascunho com o mesmo texto, a mesma forma de assinatura e a mesma pasta |
| PATCH | `/api/documentos/{id}/organizacao` | quem elaborou · admin | Pasta (`pasta_id`) e prazo (`prazo`), em qualquer etapa; null tira |
| POST | `/api/documentos/{id}/concluir` · `/reabrir` | quem elaborou · admin | Conclui o emitido (o prazo para e ele sai de *Para assinar*) ou desfaz |
| GET · POST | `/api/documentos/modelos` | todos · admin | Modelos (os ativos; o admin vê todos, com `em_uso`); cadastra (`nome`, `estrutura` = `EXTERNO`, `INTERNO` ou `SIMPLES`, `digitos`, `recuo_cm`, `forma_assinatura`, `mostrar_assunto`, `data_no_fim`, `rotulo_ident`, `vocativo`, `fecho`, `texto_modelo`) |
| POST | `/api/documentos/modelos/previa` | admin | PDF de exemplo do modelo, sem salvar |
| PATCH · DELETE | `/api/documentos/modelos/{codigo}` | admin | Altera (no ofício e no memorando, estrutura e numeração fixas; `422`); apaga só o nunca usado (`409`) |
| GET · POST | `/api/documentos/pastas` | todos · admin | Pastas (com quantos documentos cada uma tem, dos que quem consulta vê); cria (`nome`, `descricao`) |
| PATCH · DELETE | `/api/documentos/pastas/{id}` | admin | Renomeia, descreve, desativa (`ativo`); apaga (os documentos ficam sem pasta) |
| GET | `/api/documentos/timbrado` | todos | Se há cabeçalho e marca-d'água, e a cidade/UF da data |
| GET · PUT · DELETE | `/api/documentos/timbrado/{cabecalho\|fundo}` | todos · admin · admin | Imagem; envia (PNG/JPG, até 5 MB, campo `arquivo`); remove |
| GET | `/api/oficios/{id}/documento/pdf` | quem vê o ofício no Planner | PDF do documento que gerou o ofício (não exige o módulo Documentos) |
| GET | `/api/publico/verificar/{codigo}` | **sem login** | Verificação: situação, dados de identificação, assinaturas e se o conteúdo é o da emissão (`integro`) |

## Outros

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/saude` | Verificação de que o sistema está no ar (usada pelos testes) |
| GET | `/api/unidade` | Nome e descrição da unidade deste servidor (pública: a tela de login usa) |
| GET | `/docs` | Documentação interativa (Swagger) |
| GET | `/*` | As telas (`frontend/dist`). Rotas desconhecidas devolvem `index.html` |

## Exemplo com PowerShell

```powershell
$base = "http://localhost:3112/api"
$token = (Invoke-RestMethod "$base/auth/login" -Method Post -Body @{ username = "admin"; password = "<senha>" }).access_token
$h = @{ Authorization = "Bearer $token" }
Invoke-RestMethod "$base/oficios?alerta=CRITICO&ordem=antigos" -Headers $h | Select-Object -ExpandProperty itens
```
