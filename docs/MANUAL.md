# Manual do usuário

Como usar o sistema no dia a dia: o Planner de Ofícios e, no fim, a [Manutenção Clínica](#manutenção-clínica). As
regras por trás de cada tela estão em [REGRAS.md](REGRAS.md).

## Entrar

![Tela de login](imagens/login.png)

1. Abra o endereço do sistema no navegador. Nesta rede, ele é mostrado ao ligar o sistema, por exemplo
   `http://192.168.70.198:3112`.
2. Digite **Usuário** e **Senha** e clique em **Entrar**.

- **Tema:** no alto da tela você escolhe **Claro**, **Escuro** ou **Auto** (segue o tema do computador). A escolha
  fica guardada naquele navegador.
- **Senha errada:** depois de 5 senhas erradas seguidas, o login fica bloqueado por 5 minutos naquele computador.
- **Sessão encerrada:** se aparecer "Sua sessão foi encerrada", a senha foi trocada ou o tempo de acesso (8 horas)
  acabou. Basta entrar de novo.

## O menu

O menu fica à esquerda. No celular, ele abre pelo botão ☰ no alto.

| Item | Quem vê | Para quê |
|---|---|---|
| Painel | Todos | Situação geral, prazos, gráficos e exportação |
| Ofícios | Todos | Lista com busca e filtros |
| Novo ofício | Todos | Cadastrar um ofício |
| Pedidos de exclusão | Todos | Cliente: os pedidos que fez. Administrador: os pedidos a decidir (com contador) |
| Atividades | Todos | Tudo o que foi alterado, por quem e quando |
| Usuários | Administrador e master | Criar e alterar contas |
| Feriados | Administrador e master | Dias que não contam no prazo |
| Tipos de ofício | Administrador e master | Os tipos e se exigem entrega |
| Arquivos | Administrador e master | Verificação dos documentos e lixeira (com contador de problemas) |

No pé do menu ficam o seletor de tema, o seu nome, o seu perfil e o botão **Sair**.

## Painel

![Painel, visão geral](imagens/painel.png)

### Visão geral

- **Pendentes de resposta** e **Pendentes de recebimento:** quantos ofícios estão em cada etapa e quantos estão
  críticos, em atenção ou no prazo. Clique no número ou num dos níveis para abrir a lista já filtrada.
- **Indicadores:** ofícios no filtro, concluídos, não confirmados, taxa de confirmação e tempos médios de resposta e
  de entrega, em dias úteis.
- **Críticos** e **Em atenção:** os mais antigos primeiro. Clique para abrir o ofício.

### Análise

Gráficos de ofícios por tipo e por destinatário, evolução mensal, tempos médios por tipo, principais setores e
destinos, e uma tabela por cliente. Cada gráfico tem o botão **Ver tabela**. Clicar numa barra abre os ofícios
correspondentes.

![Painel, análise](imagens/painel-analise.png)

### Filtros e exportação

- **Filtros:** busca (número, protocolo, setor ou observação), período, tipo, destinatário, status, prazo e cliente
  (só administrador). Valem para as duas abas. **Limpar filtros** volta ao início.
- **Exportar Excel** e **Exportar PDF** geram o relatório com os mesmos filtros: indicadores, gráficos e a lista de
  ofícios.
- O endereço da página guarda os filtros, então dá para salvar nos favoritos ou mandar o link para alguém.

## Lista de ofícios

![Lista de ofícios](imagens/oficios.png)

- **Busca e filtros:** status, prazo, tipo, destinatário, data do ofício (de / até) e ordem (mais recentes ou mais
  antigos primeiro).
- **Colunas:** número, data, tipo e destinatário, status, prazo, observação, anexos e cliente (para administradores).
- **Abrir:** clique na linha. No celular, a tabela vira uma lista de cartões.

## Cadastrar um ofício

Em **Novo ofício**:

1. **Número do ofício** e **Data do ofício** (obrigatórios).
2. **Tipo de ofício** (obrigatório). O tipo define se haverá a etapa de entrega.
3. **Destinatário** (opcional): SES, ACQUA ou Outros, e o setor ou destino. Ao digitar, aparecem os setores já
   usados.
4. **Protocolo** e **Observação** (opcionais).
5. **Anexar o ofício** e **Anexar referência** (opcionais): clique ou arraste o arquivo (PDF, imagem ou Word, até
   20 MB).
6. Administradores escolhem também o **Cliente** dono do ofício.
7. Clique em **Cadastrar ofício**. O ofício entra como **Pendente de resposta**.

## Tela do ofício

![Tela do ofício](imagens/oficio.png)

- **Cabeçalho:** número, status, nível de prazo e tipo. Os botões mudam conforme a etapa:

  | Situação | Botão principal |
  |---|---|
  | Pendente de resposta | **Registrar resposta** |
  | Pendente de recebimento | **Confirmar recebimento** |
  | Não confirmado | **Reabrir** |

  Também ficam no cabeçalho **Editar** e **Excluir**. Para clientes, o segundo é **Solicitar exclusão**.
- **Barra do prazo** (só pendentes): quantos dias úteis se passaram e quanto falta para entrar em atenção ou ficar
  crítico. A marca no meio é o limite de atenção, e o fim da barra é o crítico.
- **Caminho:** Identificação → Resposta → Entrega. Etapa concluída aparece com ✓, a etapa atual pulsa e a futura é
  tracejada. Cada bloco mostra os dados daquela etapa.
- **Documentos:** documento do ofício, documento de referência e, quando houver, evidência da resposta e da
  entrega. Cada um pode ser **visualizado**, **baixado** e **substituído**. Administradores também podem **remover**.
- **Versões anteriores na lixeira** (administradores): os documentos substituídos ou removidos deste ofício.
- **Histórico:** cada passo do ofício, com data, autor, observação e evidência. **Mostrar eventos desfeitos** exibe
  as correções.
- **Registro de alterações:** a auditoria completa do ofício (quem mudou o quê). Abre ao clicar.

### Registrar a resposta

1. Clique em **Registrar resposta**.
2. Escolha **Confirmado** ou **Não confirmado**. A janela avisa se o tipo exige entrega.
3. Informe a **data da resposta** e, se quiser, anexe o documento de resposta e escreva uma observação.
4. Clique em **Registrar**.

O resultado depende da escolha e do tipo:
- Confirmado, num tipo que exige entrega: vai para **Pendente de recebimento**.
- Confirmado, num tipo sem entrega: vai para **Confirmado**.
- Não confirmado: vai para **Não confirmado**.

### Confirmar o recebimento

1. Clique em **Confirmar recebimento**.
2. Informe a data da entrega e, se quiser, anexe o comprovante (canhoto, termo de recebimento, relatório do
   serviço…).

O ofício passa a **Recebido**.

### Reabrir

Num ofício **Não confirmado**, **Reabrir** o devolve a **Pendente de resposta** e o prazo recomeça a contar.

### Correções (administradores)

No histórico, os administradores têm:
- **Corrigir resposta**: resultado, data e observação;
- **Corrigir recebimento**: data e observação;
- **Desfazer**: informando o motivo.

O que foi desfeito continua no histórico, riscado.

### Excluir

- **Administrador:** **Excluir** pede confirmação e apaga o ofício e os documentos.
- **Cliente:** **Solicitar exclusão** pede um motivo. O ofício mostra um aviso até um administrador decidir, e o
  cliente pode cancelar o pedido.

## Pedidos de exclusão

- **Administrador:** vê os pedidos pendentes e o histórico de decisões. Pode **Aprovar e excluir** ou **Recusar**,
  informando um motivo.
- **Cliente:** acompanha os próprios pedidos.

## Atividades

Lista de tudo o que foi feito, filtrável por tipo de atividade e período. Clique numa linha para ver os detalhes
(valor antigo → novo). Clientes veem o que fizeram e o que aconteceu nos próprios ofícios.

## Administração

### Usuários

- **Novo usuário:** nome, login, senha (mínimo de 8 caracteres) e o **acesso aos módulos**:
  - Planner de Ofícios: *Sem acesso*, *Cliente* ou *Administrador*;
  - Manutenção Clínica: *Sem acesso*, *Operacional*, *Técnico* (escolha também a empresa) ou *Administrador*.

  Só o master cria administradores e masters. Um administrador só habilita pessoas nos módulos que ele administra.
- **Operacional sempre tem o Planner:** ao escolher *Operacional* ou *Administrador* na Manutenção, o Planner vem
  como *Cliente* (ou mantém o papel que a pessoa já tinha) e a opção *Sem acesso* some. O técnico fica só na
  Manutenção.
- **Editar:** altera nome, login, situação (ativo ou inativo), senha e o acesso aos módulos. Deixe a senha em branco
  para manter a atual. Trocar a senha encerra as sessões abertas daquela pessoa. O administrador de um módulo só
  altera o nome, o login, a senha e a situação de quem usa apenas módulos que ele administra.
- **Depois do login:** quem tem acesso a mais de um módulo (o master, por exemplo) escolhe o módulo na tela
  **Módulos**. Quem tem só um módulo entra direto nele.

### Feriados

- Navegue pelos anos com as setas.
- **Cadastrar nacionais de {ano}** adiciona os feriados nacionais.
- **Adicionar feriado** cadastra feriados locais ou pontos facultativos (data e descrição).
- Lembre de cadastrar os feriados de cada ano novo.

### Tipos de ofício

![Tipos de ofício](imagens/tipos.png)

- **Ordem:** as setas definem a ordem nas listas e nos gráficos.
- **Exige entrega:** ao marcar ou desmarcar, o sistema avisa e ajusta os ofícios já respondidos daquele tipo.
- **Situação:** um tipo desativado some do cadastro de ofícios novos.
- **Editar:** muda o nome e o nome curto.
- **Apagar:** só aparece em tipos que nunca foram usados.
- **Novo tipo:** nome, nome curto (opcional) e se exige entrega.

### Arquivos

- **Verificação dos arquivos:** mostra quantos documentos foram conferidos e se algum **sumiu** ou foi **alterado**,
  com o link para o ofício. **Verificar agora** refaz a verificação. Ela também roda sozinha uma vez por dia.
- **Lixeira:** as versões anteriores de todos os ofícios, com **Visualizar**, **Baixar**, **Restaurar** e
  **Apagar de vez**.

Se um arquivo sumir ou for alterado, recupere-o do backup da pasta `backend/storage` ou envie de novo no ofício.

## Manutenção Clínica

Helpdesk para pedir suporte técnico às empresas (MSI, Realiza Predial, Realiza Climatização…). Abra pelo cartão
**Manutenção Clínica** na tela **Módulos**.

| Item do menu | Quem vê | Para quê |
|---|---|---|
| Painel / Meu painel | Todos (o técnico vê "Meu painel") | Situação dos chamados e desempenho por empresa |
| Quadro de acompanhamento | Operacional e administrador | Os chamados por etapa |
| Chamados | Todos | Lista com busca e filtros (o técnico só vê os da empresa dele) |
| Abrir chamado | Operacional e administrador | Pedir um atendimento |
| Empresas técnicas | Administrador e master | Empresas e o prazo de cada uma |

### Abrir um chamado

1. Em **Abrir chamado**, escolha a empresa, escreva o título e a **descrição do problema**.
2. Informe o local, o equipamento e a data e hora em que o problema aconteceu.
3. Clique em **Abrir chamado**. O prazo do diagnóstico (24 horas úteis, das 08:00 às 18:00, de segunda a sexta)
   começa a contar.

### Tela do chamado

- **Dados:** prazo do diagnóstico, situação do prazo (no prazo, vencendo, atrasado, cumprido), tempo em execução e,
  depois de concluído, o **tempo de solução após o diagnóstico**.
- **Linha do tempo:** tudo o que aconteceu, com autor, data, arquivos e relatórios.
- **Botões** (aparecem conforme o papel e a etapa): **Assumir**, **Relatório técnico**, **Concluir**, **Reabrir** e
  **Cancelar chamado**. Reabrir e cancelar pedem o motivo.
- **Responder:** escreva um comentário e, se quiser, anexe um arquivo. O técnico marca **É uma resposta técnica**
  para registrar o diagnóstico. A primeira resposta técnica encerra o prazo.

### Para o técnico

1. Em **Meu painel**, acompanhe os chamados da sua empresa por etapa.
2. Abra o chamado e clique em **Assumir** para ficar como responsável.
3. Responda com o diagnóstico: uma **resposta técnica** (texto e o relatório externo da empresa, se tiver) ou o
   **Relatório técnico** do sistema (data do atendimento, situação do equipamento, diagnóstico, causa, serviço,
   peças e recomendações), que gera um PDF.
4. Quando resolver, clique em **Concluir** e escreva o resumo da solução.

### Peças e equipamentos

1. No chamado, o operacional clica em **Solicitar peças ou equipamentos** e preenche os dados do ofício.
2. Clique em **Registrar no Planner**. O ofício é criado no Planner de Ofícios, ligado ao chamado, e o chamado passa
   para **Aguardando peças** no quadro.
3. Anexe o documento do ofício **no Planner**: use o atalho **Anexar o documento no Planner de Ofícios**.
4. A resposta e a entrega são registradas no Planner, como em qualquer ofício. Tudo aparece na linha do tempo do
   chamado como "Planner de Ofícios · …", e os documentos podem ser baixados pela seção **Peças e equipamentos**.
5. Com a entrega registrada, o chamado volta sozinho à etapa em que estava.

**Ofício que já existe no Planner.** Se o ofício já foi cadastrado no Planner, não cadastre de novo:

1. No chamado, clique em **Vincular ofício existente**.
2. Busque pelo número, protocolo, setor ou um trecho da observação. A lista mostra os ofícios que você vê no Planner
   e que ainda não estão em nenhum chamado: os seus, ou todos, se você for administrador do Planner.
3. Clique em **Vincular**. O ofício aparece na seção **Peças e equipamentos** com os documentos e o andamento que já
   tinha, e daí em diante tudo o que for feito nele no Planner aparece no chamado.

Cada ofício fica ligado a um chamado só. Para desfazer, use **Desvincular do chamado** no cartão do ofício: ele sai do
chamado e continua no Planner. Quem desvincula é o dono do ofício ou um administrador, com o chamado em aberto.

### Quadro de acompanhamento

Os chamados em quatro colunas: **aguardando diagnóstico**, **em execução**, **aguardando peças** e **concluídos**.
Filtre por "quais chamados", empresa e período dos concluídos. O cartão mostra o prazo e o status de cada ofício de
peças. O quadro se atualiza sozinho a cada 30 segundos.

### Empresas técnicas (administrador)

Cadastre, altere ou desative as empresas e defina o prazo do diagnóstico de cada uma, em horas úteis. Uma empresa
só pode ser excluída se não tiver chamados nem técnicos.

## Celular

O sistema funciona no navegador do celular: o menu abre pelo botão ☰ e as tabelas viram listas.

| Painel | Menu |
|---|---|
| ![Painel no celular](imagens/celular-painel.png) | ![Menu no celular](imagens/celular-menu.png) |
