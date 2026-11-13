# Atualizações

O que mudou em cada versão, da mais nova para a mais antiga, e o que fazer no servidor para aplicar.

| Versão | Data | Ramo | Resumo |
|---|---|---|---|
| 2.0 | 13/11/2026 | `feature/modulos-manutencao-clinica` | Módulos, Manutenção Clínica (helpdesk) e solicitação de peças integrada ao Planner |
| 1.1 | 04/11/2026 | `main` | Documentação dos recursos de servidor e do custo de cada visual |
| 1.0 | 26/10/2026 | `main` | Planner de Ofícios: sistema, testes e documentação |

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
- No Planner, o ofício mostra a **origem** (o chamado da Manutenção), com um link para ele.

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

- **API:** 104 testes passando (eram 62). Os novos cobrem módulos e acessos, horas úteis, prazo, visibilidade do
  técnico, relatório em PDF, tempo de solução, quadro, solicitação de peças e o espelhamento do Planner no chamado.
- **Front-end:** checagem de tipos (`tsc --noEmit`) sem erros e `npm run build` concluído.
- **Telas (Playwright):** os testes foram ajustados para a tela de Módulos, mas **não foram executados** nesta
  versão.
