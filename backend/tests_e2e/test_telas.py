"""Fluxos principais pelas telas, como o usuário faz: login, tema, painel, ofício, lixeira, tipos e segurança."""

import re

from playwright.sync_api import Page, expect

from .conftest import SENHAS, entrar

PDF = b"%PDF-1.4\n% teste de tela\n"


def abrir_oficio(page: Page, base: str, numero: str) -> None:
    page.goto(f"{base}/oficios?busca={numero}")
    # na tela larga é a tabela; no celular, a lista de cartões
    page.locator(".tabela .link-forte, .lista-mobile .fila-item strong", has_text=numero).locator("visible=true").click()
    expect(page.get_by_role("heading", name=f"Ofício nº {numero}")).to_be_visible()


def cartao_documento(page: Page, titulo: str):
    return page.locator(".cartao.anexo", has=page.get_by_text(titulo, exact=True))


# ---------- login, tema e painel ----------


def test_login_errado_e_tema_escolhido(servidor, nova_pagina):
    page = nova_pagina(tema="light")
    page.goto(f"{servidor}/login")
    expect(page.get_by_alt_text("Instituto ACQUA")).to_be_visible()
    page.get_by_label("Usuário").fill("admin")
    page.get_by_label("Senha").fill("errada")
    page.get_by_role("button", name="Entrar").click()
    expect(page.locator(".alerta-erro")).to_have_text("Login ou senha incorretos")

    # Tema escuro escolhido no login continua depois de entrar e de recarregar
    page.get_by_role("radio", name="Tema escuro").click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    entrar(page, servidor)
    page.reload()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.get_by_role("radio", name="Claro", exact=True).click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")


def test_painel_visao_geral_e_analise(admin: Page, servidor):
    expect(admin.get_by_role("tab", name="Visão geral")).to_have_attribute("aria-selected", "true")
    expect(admin.locator(".destaque").first).to_contain_text("Pendentes de resposta")
    admin.get_by_role("tab", name="Análise").click()
    expect(admin).to_have_url(re.compile(r"aba=analise"))
    expect(admin.get_by_text("Ofícios por tipo")).to_be_visible()
    # Filtro por tipo vale para a aba; limpar mantém a aba
    admin.get_by_label("Tipo de ofício").select_option(label="EPI's")
    expect(admin).to_have_url(re.compile(r"tipo=EPIS"))
    admin.get_by_role("button", name="Limpar filtros").click()
    expect(admin).to_have_url(re.compile(r"\?aba=analise$"))


# ---------- ofício: cadastro, sugestão de setor, resposta e entrega ----------


def test_cadastro_com_sugestao_de_setor_resposta_e_entrega(admin: Page, servidor):
    admin.goto(f"{servidor}/oficios/novo")
    admin.get_by_label("Número do ofício *").fill("E2E-100")
    admin.get_by_label("Tipo de ofício *").select_option(label="Mobiliários")
    admin.get_by_text("SES", exact=True).click()
    # Sugestões do setor: grafias diferentes do mesmo setor viram uma só
    opcoes = admin.locator("datalist#setores-SES option")
    expect(opcoes).to_have_count(1)
    expect(opcoes.first).to_have_attribute("value", re.compile("lmoxarifado central"))
    admin.get_by_label("Setor da SES").fill("Almoxarifado central")
    admin.get_by_role("button", name="Cadastrar ofício").click()
    expect(admin.get_by_role("heading", name="Ofício nº E2E-100")).to_be_visible()

    admin.get_by_role("button", name="Registrar resposta").click()
    admin.locator(".modal").get_by_role("button", name="Registrar").click()
    expect(admin.locator(".badge-status-PENDENTE_RECEBIMENTO").first).to_be_visible()  # Mobiliários exige entrega

    admin.get_by_role("button", name="Confirmar recebimento").first.click()
    admin.locator(".modal").get_by_role("button", name="Confirmar recebimento").click()
    expect(admin.locator(".badge-status-RECEBIDO").first).to_be_visible()
    expect(admin.locator(".bloco-dados", has_text="Entrega")).to_contain_text("Entregue em")


# ---------- lixeira ----------


def test_documento_substituido_vai_para_a_lixeira_e_volta(admin: Page, servidor):
    abrir_oficio(admin, servidor, "E2E-001")
    cartao = cartao_documento(admin, "Documento do ofício")
    cartao.locator("input[type=file]").set_input_files({"name": "versao1.pdf", "mimeType": "application/pdf",
                                                        "buffer": PDF + b"1"})
    expect(cartao).to_contain_text("versao1.pdf")
    cartao.locator("input[type=file]").set_input_files({"name": "versao2.pdf", "mimeType": "application/pdf",
                                                        "buffer": PDF + b"2"})
    expect(cartao).to_contain_text("versao2.pdf")

    admin.get_by_role("button", name=re.compile(r"Versões anteriores na lixeira \(1\)")).click()
    lixeira = admin.locator(".lixeira-oficio")
    expect(lixeira).to_contain_text("versao1.pdf")
    expect(lixeira).to_contain_text("Substituído")
    lixeira.get_by_role("button", name="Restaurar").click()
    expect(cartao).to_contain_text("versao1.pdf")
    expect(lixeira).to_contain_text("versao2.pdf")  # a que estava no lugar foi para a lixeira

    # A lixeira geral (Arquivos) mostra o mesmo item, com o link para o ofício
    admin.goto(f"{servidor}/arquivos")
    expect(admin.locator(".lixeira")).to_contain_text("versao2.pdf")
    expect(admin.locator(".lixeira")).to_contain_text("Ofício nº E2E-001")


def test_verificacao_dos_arquivos(admin: Page, servidor):
    admin.goto(f"{servidor}/arquivos")
    admin.get_by_role("button", name="Verificar agora").click()
    expect(admin.locator(".verificacao-status")).to_contain_text("íntegros")


# ---------- tipos de ofício ----------


def test_tipo_novo_aparece_no_cadastro_e_pode_ser_desativado(admin: Page, servidor):
    admin.goto(f"{servidor}/tipos")
    admin.get_by_label("Nome *").fill("Medicamentos E2E")
    admin.get_by_label("Exige confirmação da entrega depois da resposta").uncheck()
    admin.get_by_role("button", name="Criar tipo").click()
    linha = admin.locator(".tabela-tipos tr", has_text="Medicamentos E2E")
    expect(linha).to_contain_text("Não")

    admin.goto(f"{servidor}/oficios/novo")
    expect(admin.get_by_label("Tipo de ofício *").locator("option", has_text="Medicamentos E2E")).to_have_count(1)

    admin.goto(f"{servidor}/tipos")
    linha.get_by_role("checkbox").nth(1).click()  # situação: desativar (muda depois da resposta do servidor)
    expect(linha).to_contain_text("Desativado")
    admin.goto(f"{servidor}/oficios/novo")
    expect(admin.get_by_label("Tipo de ofício *").locator("option", has_text="Medicamentos E2E")).to_have_count(0)


# ---------- segurança ----------


def test_login_bloqueado_apos_5_senhas_erradas(servidor, nova_pagina):
    page = nova_pagina()
    page.goto(f"{servidor}/login")
    page.get_by_label("Usuário").fill("ana")
    for _ in range(5):
        page.get_by_label("Senha").fill("errada")
        page.get_by_role("button", name="Entrar").click()
        expect(page.locator(".alerta-erro")).to_be_visible()
    page.get_by_label("Senha").fill(SENHAS["ana"])
    page.get_by_role("button", name="Entrar").click()
    expect(page.locator(".alerta-erro")).to_contain_text("Muitas tentativas")


def test_trocar_a_senha_encerra_a_sessao_aberta(servidor, nova_pagina):
    # O bloqueio do teste anterior é por login e computador: usa outro usuário
    master = nova_pagina()
    entrar(master, servidor)
    master.goto(f"{servidor}/usuarios")
    master.get_by_role("button", name="Novo usuário").click()
    master.get_by_label("Nome *").fill("Bia Teste")
    master.get_by_label("Login *").fill("bia")
    master.get_by_label("Senha *").fill("bia-senha-1")
    master.locator(".modal").get_by_role("button", name=re.compile("Criar|Salvar")).click()
    expect(master.get_by_role("cell", name="Bia Teste")).to_be_visible()

    bia = nova_pagina()
    entrar(bia, servidor, "bia", "bia-senha-1")

    master.locator("tr", has_text="Bia Teste").get_by_role("button", name=re.compile("Editar")).click()
    master.locator(".modal").get_by_label(re.compile("senha", re.I)).first.fill("bia-senha-2")
    master.locator(".modal").get_by_role("button", name="Salvar").click()
    expect(master.locator(".modal")).to_have_count(0)  # salvou

    bia.goto(f"{servidor}/oficios")
    expect(bia.get_by_role("button", name="Entrar")).to_be_visible()
    expect(bia.locator(".alerta-info")).to_contain_text("sessão foi encerrada")
    entrar(bia, servidor, "bia", "bia-senha-2")


# ---------- celular ----------


def test_celular_sem_rolagem_horizontal(servidor, nova_pagina):
    page = nova_pagina(largura=390, altura=844, celular=True)
    entrar(page, servidor)
    for caminho in ("/", "/?aba=analise", "/oficios", "/arquivos", "/tipos"):
        page.goto(f"{servidor}{caminho}")
        page.wait_for_load_state("networkidle")
        assert page.evaluate("document.documentElement.scrollWidth") <= 390, caminho
    abrir_oficio(page, servidor, "E2E-003")
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
