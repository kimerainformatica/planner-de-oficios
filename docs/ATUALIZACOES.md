# Atualizações

O que mudou em cada versão, da mais nova para a mais antiga, e o que fazer no servidor para aplicar.

| Versão | Data | Ramo | Resumo |
|---|---|---|---|
| 2.3 | 20/11/2026 | `feature/2.3-controle-de-tetos` | Módulos Controle de Tetos (tetos por setor, lançamentos e indicadores diários, mensais e anuais) e Documentos (ofícios e memorandos no modelo da unidade, com assinatura eletrônica, verificação e integração ao Planner) |
| 2.2 | 14/11/2026 | `feature/2.2-preventivas-prazos-diagnostico` | Prazos em dias e horas corridas; seção Diagnóstico técnico, com relatório externo e do sistema interligados e editáveis |
| 2.1 | 14/11/2026 | `feature/2.2-preventivas-prazos-diagnostico` | Manutenção preventiva com ateste, avisos internos e nome da unidade |
| 2.0 | 13/11/2026 | `feature/modulos-manutencao-clinica` | Módulos, Manutenção Clínica (helpdesk) e solicitação de peças integrada ao Planner |
| 1.1 | 04/11/2026 | `main` | Documentação dos recursos de servidor e do custo de cada visual |
| 1.0 | 26/10/2026 | `main` | Planner de Ofícios: sistema, testes e documentação |

## 2.3 · Controle de Tetos e Documentos

### Controle de Tetos

- **Setores ligados ao login:** o administrador cadastra os setores (ex.: Gerência Operacional) e, em Usuários, liga
  cada pessoa ao setor dela como *Usuário do setor* no Controle de Tetos.
- **Tipos de teto gerenciáveis:** o administrador cria, para cada setor, o que quer medir, em R$ ou noutra unidade
  (litros, resmas, kWh…), com o % de alerta. O teto é definido num período (diário, mensal ou anual) e os outros
  saem por proporção. Mudar o valor vale a partir de uma data, sem mudar os indicadores do passado.
- **Lançamentos:** o setor lança os gastos (data, valor, descrição, documento e comprovante), corrige e exclui. Tudo
  fica nas atividades.
- **Indicadores:** painel com o consumo do dia, do mês (com o esperado até hoje e a projeção do mês) e do ano de cada
  tipo; e, por tipo, os gráficos dia a dia, mês a mês e ano a ano, com tabela.

### Documentos (ofícios e memorandos)

- **Novo módulo Documentos**, com acesso próprio: *Redator* (redige e assina) ou *Administrador* (vê todos, cancela
  e cuida do timbrado). Quem só redige não precisa usar o Planner.
- **Ofícios e memorandos redigidos no app.** O PDF reproduz os modelos da unidade (*Ofício modelo padrão* e
  *Memorando modelo padrão*):
  - A4, margens de 3 cm nas laterais e 2,5 cm em cima e embaixo, timbrado no topo e marca-d'água em página inteira;
  - número, data por extenso, destinatário (ofício) ou De/Para (memorando), assunto e assinaturas em Arial 12;
  - corpo (vocativo, parágrafos e fecho) em **Times New Roman 12**, justificado, espaçamento 1,5, com recuo na 1ª
    linha de **1,75 cm no ofício** e **1,25 cm no memorando**;
  - páginas numeradas a partir da 2ª.
- **Rascunho → emissão:** o rascunho é salvo sozinho e tem prévia do PDF ao lado. Na emissão o documento recebe o
  próximo número da sequência de quem elaborou (o ofício continua a numeração do Planner, ex.: 012/2026), a data de
  hoje e um **código de verificação** com QR code no rodapé. O texto fica travado.
- **Integração com o Planner de Ofícios:** no ofício, *Registrar no Planner de Ofícios ao emitir* (ligado para quem
  usa o Planner). Com ela, o ofício emitido entra no Planner como pendente de resposta, com o tipo e o destinatário
  escolhidos, e os prazos começam a contar. No Planner, o ofício tem o botão *Documento gerado* (ou *PDF do
  documento*, para quem acompanha o ofício sem ter o módulo), e o menu do Planner ganha o atalho *Redigir ofício*
  para quem tem o módulo.
- **Assinaturas:** o PDF sai com o espaço para assinar à mão (quem elaborou e o *De acordo*). Depois da emissão, cada
  um também pode **assinar no app**, confirmando a senha; o carimbo da assinatura eletrônica aparece no PDF no lugar
  da assinatura à mão. O menu mostra quantos documentos esperam a sua assinatura.
- **Verificação pública** (`/verificar/<código>`, sem login): mostra se o documento é autêntico, se foi cancelado e
  se o registro foi alterado depois da emissão (o hash do conteúdo é gravado na emissão).
- **Cancelar e refazer:** o emitido pode ser cancelado com o motivo (continua consultável, marcado como cancelado);
  *Fazer um novo a partir deste* cria um rascunho com o mesmo texto.
- **Timbrado:** o administrador do módulo envia o cabeçalho e a marca-d'água em **Timbrado**. Valem para todos os
  documentos.
- **Usuários:** cadastro com **cargo** e **matrícula/ID**, que já vêm preenchidos no bloco de assinatura.

### Banco de dados

| Migração | O que faz |
|---|---|
| `0017_controle_de_tetos` | Acrescenta o módulo `TETOS`, as tabelas `setores`, `tipos_teto`, `tetos_vigencias` e `gastos_teto` e a coluna `usuario_modulos.setor_id` |
| `0018_documentos` | Cria `documentos` e `documento_assinaturas` e acrescenta `usuarios.cargo` e `usuarios.matricula` |
| `0019_modulo_documentos` | Acrescenta o módulo `DOCUMENTOS` e a coluna `documentos.registrar_no_planner` |

Nada do que existe muda. Ninguém recebe os módulos novos sozinho: o master libera quem vai usar. Voltar a 0016 apaga
os dados dos dois módulos; a volta segura é o backup.

### Como aplicar no servidor

1. Faça o **backup do banco**.
2. Troque para o ramo (`git fetch` e `git checkout feature/2.3-controle-de-tetos`) e rode `alembic upgrade head` em `backend`. Confira com
   `alembic current`: deve mostrar `0019 (head)`.
3. No `backend/.env`, informe `DOCUMENTOS_CIDADE` e `DOCUMENTOS_UF` (ex.: `São Luís` e `MA`) e, se o QR code deve
   levar a um endereço fixo da rede, `DOCUMENTOS_URL_PUBLICA` (ex.: `http://192.168.0.10:3112`).
4. Gere as telas (`npm run build` em `frontend`) e reinicie o sistema.
5. Entre como master:
   - em **Controle de Tetos → Setores**, cadastre os setores; em **Tipos de teto**, os tetos de cada um;
   - em **Usuários**, ligue cada pessoa ao setor dela, libere o módulo **Documentos** (Redator ou Administrador) para
     quem vai redigir e preencha o cargo e a matrícula de quem assina;
   - em **Documentos → Timbrado**, confira o cabeçalho e a marca-d'água.

### Testes

- **API:** 138 testes passando. São 21 novos:
  - **Tetos (10):** as proporções entre os períodos, a mudança de valor no meio do mês, o setor obrigatório no
    cadastro, quem pode o quê, a separação entre setores, os lançamentos com comprovante, o painel (situação e
    projeção) e as séries dos indicadores;
  - **Documentos (11):** o rascunho e a emissão com o cadastro no Planner, a numeração que continua a do Planner (por
    pessoa e por tipo), o *De acordo* e a assinatura com a senha, quem vê o quê, o acesso ao módulo, o ofício sem
    registro no Planner, o redator sem o Planner, o PDF pelo ofício do Planner, a verificação pública (inclusive a
    alteração do registro), o cancelamento, a duplicação e o timbrado.
- **Front-end:** checagem de tipos e `npm run build` sem erros. Telas conferidas no navegador com dados de
  demonstração: no Controle de Tetos, painel, indicadores, tipos, valores, setores, usuários e lançamentos; nos
  Documentos, lista, rascunho com prévia, emissão, assinaturas, verificação no computador e no celular, timbrado,
  usuários e o ofício no Planner.

## 2.2 · Prazos corridos e data do diagnóstico

### Prazos em dias e horas corridas

- **Planner de Ofícios:** o prazo de resposta e o de entrega passam a ser em **dias corridos**, da data do ofício
  (ou da resposta). Sábados, domingos e feriados contam. Os limites continuam em `DIAS_ATENCAO` (30) e
  `DIAS_CRITICO` (45), agora em dias corridos: ajuste no `.env` se quiser outros valores.
- **Manutenção Clínica:** o prazo do diagnóstico passa a ser em **horas corridas** da abertura (24 h = 1 dia), sem
  expediente. O tempo de solução também fica só em horas corridas.
- **Feriados:** não entram mais em nenhum prazo. A tela saiu do menu; o cadastro e a API continuam.
- **Chamados que já existiam:** a migração 0016 refaz o prazo de todos com a regra nova. A situação de cada um (no
  prazo, atrasado, cumprido) é recalculada.

### Seção Diagnóstico técnico

- No chamado, tudo o que é do diagnóstico fica numa seção só, abaixo dos dados: registrar, ver, editar e complementar.
  Saíram o botão *Relatório técnico* do topo e a opção *É uma resposta técnica* da caixa de comentário.
- **Registrar:** *Relatório externo* (o arquivo da empresa, com resumo opcional) ou *Relatório no modelo do sistema*,
  que pode levar o arquivo externo junto, no mesmo registro.
- **Editar depois**, no próprio registro: data e hora, resumo ou campos do relatório, e substituir o relatório externo.
  O arquivo anterior fica guardado na linha do tempo. Toda edição fica registrada como *Correção*.
- **Complementos:** outros relatórios depois do diagnóstico, sem mudar a data dele.

### Data e hora do diagnóstico

- No relatório externo (o laudo da empresa), o técnico informa **quando o diagnóstico foi feito**. É essa data que
  conta para o prazo, e não a hora em que o registro foi feito no sistema.
- No relatório técnico, a data e a hora do atendimento contam como a do diagnóstico.
- **Corrigir depois:** o técnico da empresa ou o administrador clica em **Editar**, no registro da seção *Diagnóstico
  técnico*. O prazo e o tempo de solução são recalculados e a correção fica na linha do tempo, com a data antiga e a
  nova.

### Banco de dados e configuração

| Migração | O que faz |
|---|---|
| `0016_prazos_corridos` | Refaz `chamados.prazo_em` em horas corridas, tira `solucao_horas_uteis`, cria `chamado_interacoes.ocorrido_em` e o tipo de interação `CORRECAO` |

- `MANUTENCAO_EXPEDIENTE_INICIO` e `MANUTENCAO_EXPEDIENTE_FIM` deixam de existir. Se estiverem no `.env`, são
  ignoradas.
- Voltar a 0016 não restaura o prazo antigo em horas úteis. A volta segura é o backup.

### Como aplicar no servidor

1. Faça o **backup do banco**.
2. Troque para o ramo (`git fetch` e `git checkout feature/2.2-preventivas-prazos-diagnostico`) e rode
   `alembic upgrade head` em `backend`. Confira com `alembic current`: deve mostrar `0016 (head)`.
3. Gere as telas (`npm run build` em `frontend`) e reinicie o sistema.

### Testes

- **API:** 117 testes passando. Os de prazo foram refeitos para dias e horas corridas, e há testes novos para a data
  do diagnóstico informada, a correção (permissões, limites, recálculo do prazo e do tempo de solução) e o relatório.

## 2.1 · Preventivas, avisos e unidade

### Manutenção preventiva

- **Planos:** o administrador cadastra cada rotina de preventiva de uma empresa técnica e define a periodicidade
  (a cada N dias, semanas ou meses), a primeira data e a tolerância. O contrato prevê a preventiva sem fixar os
  períodos, então eles ficam registrados aqui.
- **Agenda:** o sistema cria as datas sozinho e mostra a situação de cada uma: programada, para realizar agora,
  atrasada, realizada (no prazo ou com atraso) e não realizada.
- **Realização com evidência:** o técnico da empresa registra a data, quem executou e o que foi feito, e anexa o
  checklist ou a ordem de serviço.
- **Ateste:** o operacional ou o administrador confirma o serviço. O técnico não atesta.
- **Previsto x realizado por empresa:** tabela com o cumprimento de cada empresa no mês, para a fiscalização.

### Avisos internos

- O servidor não envia e-mail, então as pendências ficam no item **Avisos** do menu, com o número ao lado.
- Cada pessoa vê o que é dela: chamados com o diagnóstico atrasado ou vencendo, preventivas atrasadas ou para
  realizar agora e, para quem fiscaliza, preventivas aguardando ateste.

### Nome da unidade

- Cada unidade tem o próprio servidor. O nome configurado aparece no login, no menu e no PDF do relatório técnico.

### Banco de dados e configuração

| Migração | O que faz |
|---|---|
| `0015_preventivas` | Tabelas `planos_preventiva` e `preventivas` |

| Variável | Padrão | O que faz |
|---|---|---|
| `UNIDADE_NOME` | vazio | Nome da unidade deste servidor (ex.: `SORRIR PRAIA GRANDE`) |
| `UNIDADE_DESCRICAO` | vazio | Descrição que aparece abaixo do nome, no login |

### Como aplicar no servidor

1. Faça o **backup do banco**.
2. Troque para o ramo `feature/2.2-preventivas-prazos-diagnostico` e rode `alembic upgrade head`. Ele já leva até a
   2.2: `alembic current` mostra `0016 (head)`.
3. Acrescente `UNIDADE_NOME` (e, se quiser, `UNIDADE_DESCRICAO`) ao `backend/.env`.
4. Gere as telas (`npm install` e `npm run build` em `frontend`) e reinicie o sistema.
5. Cadastre os planos de preventiva em **Manutenção Clínica → Preventivas → Novo plano**.

Voltar a 0015 (`alembic downgrade -1`) apaga os planos e os registros das preventivas. A volta segura é o backup.

### Testes

- **API:** 117 testes passando (eram 106). Os novos cobrem as datas dos planos, a mudança de periodicidade, a
  visibilidade do técnico, a realização com evidência, o ateste, o previsto x realizado e os avisos por papel.

## 2.0 · Módulos e Manutenção Clínica

### Módulos e acesso

- O sistema passa a ter **módulos**: *Planner de Ofícios* e *Manutenção Clínica*. Depois do login, a tela
  **Módulos** mostra os que a pessoa pode abrir. Com um só, ela entra direto.
- O papel é definido **por módulo**, no cadastro do usuário:

  | Módulo | Papéis |
  |---|---|
  | Planner de Ofícios | Administrador, Cliente |
  | Manutenção Clínica | Administrador, Operacional, Técnico (com a empresa) |

- O **master** tem acesso total e edita o acesso aos dois módulos. Só ele cria administradores e outros masters.
- O **administrador** de um módulo cadastra e edita pessoas **só no próprio módulo**.
- **Regra do operacional:** todo operacional (operacional ou administrador da Manutenção) também tem o Planner. Ao
  habilitar alguém na Manutenção, o Planner vem como cliente. A tela não deixa tirar, e a API recusa (`400`).
- O **técnico** usa só a Manutenção e vê só os chamados da própria empresa.
- Ninguém altera o próprio acesso, e o sistema mantém pelo menos um master ativo.

### Manutenção Clínica (helpdesk)

- **Abertura do chamado** pelo operacional:
  - empresa técnica, título e descrição do problema;
  - local, equipamento e data/hora em que ocorreu.
- **Empresas técnicas** cadastráveis pelo administrador. Já vêm MSI, REALIZA PREDIAL e REALIZA CLIMATIZAÇÃO, cada uma
  com o próprio prazo (padrão de 24 horas).
- **Prazo de diagnóstico em horas úteis:** expediente das 08:00 às 18:00, de segunda a sexta, sem os feriados do
  Planner. A situação é calculada na hora: no prazo, vencendo (4 h úteis ou menos), atrasado, cumprido, cumprido com
  atraso.
- **Login do técnico:**
  - vê só os chamados da própria empresa e tem o próprio painel (**Meu painel**);
  - assume o chamado e responde com um comentário, um arquivo externo ou um **relatório técnico** no modelo do
    sistema, com PDF;
  - a resposta técnica ou o relatório contam como diagnóstico.
- **Andamento:** concluir (exige diagnóstico), reabrir e cancelar com motivo, com toda a linha do tempo registrada.
- **Tempo de solução:** ao concluir, o chamado grava quanto demorou do diagnóstico à solução, em horas úteis e
  corridas. O painel mostra a média por empresa. Reabrir apaga esse tempo, e ele é gravado de novo na próxima
  conclusão.
- **Painel** com contagens, desempenho por empresa e os chamados mais perto do prazo.
- **Quadro de acompanhamento** em quatro etapas: aguardando diagnóstico, em execução, aguardando peças, concluídos.
  Tem filtros e indicadores e se atualiza a cada 30 segundos.

### Peças e equipamentos, integrados ao Planner

- No chamado, o operacional abre uma **solicitação de peças ou equipamentos**. Ela é cadastrada como **ofício no
  Planner** (tipos *Peças para Manutenção/Engenharia Clínica* e *Equipamentos*), ligada ao chamado.
- O **documento é anexado no Planner**, no próprio ofício. O chamado lista os documentos para download, inclusive
  para o técnico, e tem o atalho "Anexar o documento no Planner de Ofícios".
- **Espelhamento:** cada ação no ofício entra na linha do tempo do chamado como "Planner de Ofícios · …", com o autor:
  - anexos enviados ou removidos;
  - resposta, entrega e correções;
  - desfazer e exclusão.
- O chamado fica em **Aguardando peças** enquanto algum ofício estiver pendente de resposta ou de entrega. Com a
  entrega registrada no Planner, volta sozinho à etapa em que estava.
- No Planner, o ofício mostra o **chamado** da Manutenção a que está ligado, com um link para ele.
- **Ofícios que já existem no Planner** (14/11/2026): o botão **Vincular ofício existente** liga ao chamado um
  ofício já cadastrado, sem cadastrar de novo.
  - A busca mostra os ofícios que a pessoa vê no Planner e que ainda não têm chamado.
  - Cada ofício fica em um chamado só. **Desvincular do chamado** desfaz, e o ofício continua no Planner.
  - Não muda o banco: usa a ligação `oficios.chamado_id` da migração 0013.

### Banco de dados

| Migração | O que faz |
|---|---|
| `0011_modulos` | Cria `usuario_modulos` e passa o perfil de cada usuário (não master) para o módulo Planner |
| `0012_helpdesk_manutencao` | Cria empresas técnicas (com as 3 iniciais), chamados, relatórios técnicos e a linha do tempo. Inclui o papel Técnico |
| `0013_solucao_e_pecas` | Tempo de solução no chamado e ligação ofício → chamado (`oficios.chamado_id`) |
| `0014_operacional_no_planner` | Dá o Planner, como cliente, a todo operacional que ainda não o tinha |

A 0014 só acrescenta acessos e não os retira ao voltar (`downgrade`). Para desfazer a atualização, restaure o backup.

### Configuração nova (opcional)

| Variável | Padrão | O que faz |
|---|---|---|
| `MANUTENCAO_EXPEDIENTE_INICIO` | `08:00` | Início do expediente usado no prazo dos chamados |
| `MANUTENCAO_EXPEDIENTE_FIM` | `18:00` | Fim do expediente (`00:00` = meia-noite) |
| `MANUTENCAO_ALERTA_HORAS` | `4` | Horas úteis restantes para o chamado aparecer como "vencendo" |

### Como aplicar no servidor

1. Faça o **backup do banco** com `mysqldump` (veja [INSTALACAO.md](INSTALACAO.md#6-backup)).
2. Troque para o ramo: `git fetch` e `git checkout feature/modulos-manutencao-clinica`. Depois da aprovação, ele entra no
   `main`.
3. `cd backend`, `.venv\Scripts\pip install -r requirements.txt` e `.venv\Scripts\alembic upgrade head`. Confira com
   `alembic current`: deve mostrar `0014 (head)`.
4. `cd ..\frontend`, `npm install` e `npm run build`.
5. Reinicie com `parar.bat` e `iniciar.bat`, e peça aos usuários um **Ctrl+F5**.
6. Na tela **Usuários**, habilite cada pessoa na Manutenção: operacionais, técnicos (com a empresa) e administradores.

O ramo parte do `main` (visual "Correnteza"). O `visual-classico` ainda não tem esta versão.

### Testes

- **API:** 106 testes passando (eram 62). Os novos cobrem módulos e acessos, horas úteis, prazo, visibilidade do
  técnico, relatório em PDF, tempo de solução, quadro, solicitação de peças e o espelhamento do Planner no chamado.
- **Front-end:** checagem de tipos (`tsc --noEmit`) sem erros e `npm run build` concluído.
- **Telas (Playwright):** os testes foram ajustados para a tela de Módulos, mas **não foram executados** nesta
  versão.
