# Desenvolvimento

Como preparar o ambiente, rodar os testes e mexer no código sem quebrar o que existe.

## Ambiente

Siga a [instalação](INSTALACAO.md) até o `npm install`. Para desenvolver, use dois terminais:

```powershell
# terminal 1: API, reiniciando ao salvar
cd backend
.venv\Scripts\python -m app --reload

# terminal 2: telas com recarga instantânea em http://localhost:5173
cd frontend
npm run dev
```

O Vite repassa as chamadas `/api` para a porta 3112. Para conferir o resultado final, gere o build (`npm run build`)
e abra `http://localhost:3112`.

## Testes

```powershell
cd backend
.venv\Scripts\python -m pytest              # API
.venv\Scripts\python -m pytest tests_e2e    # telas (compile o front antes: npm run build)
cd ..\frontend
npm run typecheck                           # TypeScript
```

| Suíte | Onde | O que cobre | Banco |
|---|---|---|---|
| API (62 testes) | `backend/tests/` | Prazos e feriados, transições de status, entrega, correções, perfis, exclusões, auditoria, anexos e lixeira, verificação, tipos, bloqueio de login, sessões, painel e exportação | SQLite em memória |
| Telas (9 fluxos) | `backend/tests_e2e/` | Login e tema; abas do painel; cadastro com sugestão de setor, resposta e entrega; lixeira; verificação; tipos; bloqueio de login; troca de senha encerrando a sessão; celular sem rolagem lateral | SQLite temporário, com o sistema real rodando numa porta livre |

- Os testes de tela usam o **Microsoft Edge** instalado (`channel="msedge"`), sem baixar navegadores. Use
  `E2E_CANAL=chrome` para usar o Chrome e `E2E_VISIVEL=1` para ver o navegador trabalhando.
- Qualquer erro de JavaScript na página faz o teste de tela falhar.
- Nenhum teste toca o banco MySQL real.

## Mudar o banco (migrações)

1. Altere `backend/app/models.py`.
2. Crie a migração seguindo a numeração (`0011_…`):
   `.venv\Scripts\alembic revision -m "descrição" --rev-id 0011`. Escreva `upgrade()` e `downgrade()` à mão,
   olhando as anteriores.
3. Teste numa cópia do banco: `upgrade` → `downgrade` → `upgrade`.
4. No banco real: **backup com `mysqldump` antes**, depois `alembic upgrade head` e reinicie o sistema.

Cuidados no MySQL:
- Converter `ENUM` para `VARCHAR` exige ajustar os dados antes ou depois.
- Remover uma chave estrangeira pode exigir remover também o índice com o mesmo nome (veja a 0009).

## Convenções

- **Idioma:** código, mensagens, comentários e documentação em português do Brasil, com nomes descritivos
  (`dias_uteis_decorridos`, `exige_recebimento`).
- **Onde fica cada coisa:**
  - regras de negócio em `services/`;
  - `routers/` só valida a entrada, chama o serviço e registra a auditoria;
  - o front-end nunca decide permissão: ele só esconde botões, e o back-end confere tudo de novo.
- **Auditoria:** toda alteração passa por `services/auditoria.registrar`, com o antes e o depois. Ação nova = item no
  enum `Acao` e nome dos campos em `NOME_CAMPO` (back-end), mais o rótulo em `ROTULO_ACAO`, em `utils/formato.ts`
  (front-end).
- **Datas:** dias úteis sempre por `services/prazos.py`. Nunca conte dias corridos para o prazo.
- **Painel:** tela, Excel e PDF usam a mesma rotina (`services/analise.py`). Indicador novo entra lá, uma vez só.
- **Visual:**
  - use as variáveis de `styles/base.css` (`--primaria`, `--superficie`, `--texto-suave`…) e não cores soltas, para
    o tema escuro funcionar;
  - CSS fica no arquivo do assunto;
  - ícones vêm do lucide-react;
  - neste ramo (`visual-classico`) não há animações: a regra no `base.css` desliga qualquer animação ou transição.
- **Acessibilidade:**
  - botões de verdade (`<button>`) e `aria-label` em botões só com ícone;
  - status sempre com texto, além da cor;
  - contraste mínimo de 4,5:1 no texto.

## Estrutura de pastas

```
backend/
  app/
    __main__.py  main.py  config.py  database.py  deps.py  seguranca.py
    models.py  schemas.py
    routers/     auth usuarios oficios anexos lixeira tipos dashboard feriados exclusoes auditoria
    services/    prazos oficios tipos armazenamento integridade limite_login analise exportacao exclusoes auditoria
  alembic/versions/   0001 … 0010
  scripts/            inicializar.py  definir_perfil.py
  tests/  tests_e2e/
frontend/
  index.html          aplica o tema antes de desenhar
  public/favicon.svg
  src/
    main.tsx  App.tsx  types.ts
    api/  auth/  components/  pages/  pages/oficio/  styles/  utils/  assets/
docs/                 esta documentação e as capturas (docs/imagens)
```

## Publicar uma alteração

1. Testes da API, testes de tela e `npm run typecheck` passando.
2. `npm run build`.
3. Se houver migração: backup e `alembic upgrade head`.
4. Reinicie (`parar.bat` e `iniciar.bat`) se o back-end mudou. Mudança só no front-end não precisa.
5. Commit com mensagem clara, em português.
