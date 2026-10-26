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
**admin** = `ADMIN` ou `MASTER`.

## Autenticação e usuários

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| POST | `/api/auth/login` | — | Entra e devolve o token |
| GET | `/api/auth/me` | todos | Usuário atual |
| GET | `/api/usuarios` | admin | Lista os usuários |
| POST | `/api/usuarios` | admin | Cria um usuário. Só o master cria administradores e masters |
| PATCH | `/api/usuarios/{id}` | admin | Altera nome, perfil, situação ou senha. Trocar a senha encerra as sessões da pessoa |

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
| GET | `/api/dashboard/prazos` | todos | Limites de atenção e crítico, em dias úteis |
| GET | `/api/dashboard/analise` | todos | Indicadores e agrupamentos dos gráficos (aceita os mesmos filtros da lista) |
| GET | `/api/dashboard/exportar?formato=xlsx\|pdf` | todos | Relatório do painel filtrado em Excel ou PDF |

## Cadastros

| Método | Rota | Quem | O que faz |
|---|---|---|---|
| GET | `/api/tipos` | todos | Tipos de ofício na ordem de exibição (inclui inativos e `em_uso`) |
| POST | `/api/tipos` | admin | Cria um tipo (o código é gerado a partir do nome) |
| PATCH | `/api/tipos/{codigo}` | admin | Altera nome, nome curto, exige entrega, ativo ou ordem. Mudar "exige entrega" ajusta os ofícios do tipo |
| DELETE | `/api/tipos/{codigo}` | admin | Apaga um tipo que nunca foi usado (senão `409`) |
| GET | `/api/feriados?ano=` | todos | Feriados do ano |
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

## Outros

| Método | Rota | O que faz |
|---|---|---|
| GET | `/api/saude` | Verificação de que o sistema está no ar (usada pelos testes) |
| GET | `/docs` | Documentação interativa (Swagger) |
| GET | `/*` | As telas (`frontend/dist`). Rotas desconhecidas devolvem `index.html` |

## Exemplo com PowerShell

```powershell
$base = "http://localhost:3112/api"
$token = (Invoke-RestMethod "$base/auth/login" -Method Post -Body @{ username = "admin"; password = "<senha>" }).access_token
$h = @{ Authorization = "Bearer $token" }
Invoke-RestMethod "$base/oficios?alerta=CRITICO&ordem=antigos" -Headers $h | Select-Object -ExpandProperty itens
```
