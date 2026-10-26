"""Testes de tela (Playwright): sobem o sistema de verdade (API + frontend/dist) num banco SQLite temporário.

Rodar (dentro de backend/, com o frontend já compilado por `npm run build`):
    .venv\\Scripts\\python -m pytest tests_e2e
Usa o Microsoft Edge instalado (sem baixar navegadores). Outro navegador: E2E_CANAL=chrome.
Para ver o navegador trabalhando: E2E_VISIVEL=1.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect, sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Destinatario, Feriado, HistoricoStatus, Oficio, Perfil, StatusOficio, Usuario
from app.seguranca import gerar_hash_senha
from app.services.prazos import feriados_nacionais
from app.services.tipos import semear

BACKEND = Path(__file__).resolve().parent.parent
DIST = BACKEND.parent / "frontend" / "dist"
SENHAS = {"admin": "admin-e2e-123", "ana": "ana-e2e-123"}


def _dia_util(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _semear(url: str) -> None:
    hoje = date.today()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        semear(db)
        admin = Usuario(nome="Administrador", login="admin", senha_hash=gerar_hash_senha(SENHAS["admin"]),
                        perfil=Perfil.MASTER)
        ana = Usuario(nome="Ana Souza", login="ana", senha_hash=gerar_hash_senha(SENHAS["ana"]))
        db.add_all([admin, ana])
        db.add_all(Feriado(data=d, descricao=t) for ano in (hoje.year - 1, hoje.year) for d, t in feriados_nacionais(ano))
        db.flush()
        P, PR, C = StatusOficio.PENDENTE_RESPOSTA, StatusOficio.PENDENTE_RECEBIMENTO, StatusOficio.CONFIRMADO
        # (número, tipo, dias atrás, destinatário, setor, status)
        dados = [
            ("E2E-001", "EPIS", 70, Destinatario.SES, "Almoxarifado central", P),
            ("E2E-002", "COMUNICADOS", 30, Destinatario.OUTROS, "Prefeitura", C),
            ("E2E-003", "SERVICOS", 50, Destinatario.ACQUA, "Obras", PR),
            ("E2E-004", "EPIS", 10, Destinatario.SES, "almoxarifado central", P),
        ]
        for numero, tipo, atras, dest, setor, status in dados:
            d = _dia_util(hoje - timedelta(days=atras))
            resposta = _dia_util(d + timedelta(days=7)) if status != P else None
            o = Oficio(dono_id=ana.id, numero=numero, data_oficio=d, ano=d.year, tipo=tipo, destinatario_tipo=dest,
                       destinatario_setor=setor, status=status, inicio_prazo=d, data_resposta=resposta,
                       criado_por_id=ana.id)
            db.add(o)
            db.add(HistoricoStatus(oficio=o, status_anterior=None, status_novo=P, usuario_id=ana.id,
                                   observacao="Cadastro do ofício"))
            if status != P:
                db.add(HistoricoStatus(oficio=o, status_anterior=P, status_novo=status, data_resposta=resposta,
                                       usuario_id=ana.id))
        db.commit()
    engine.dispose()


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor(tmp_path_factory):
    if not (DIST / "index.html").is_file():
        pytest.skip("Compile o frontend antes (npm run build em frontend/)")
    pasta = tmp_path_factory.mktemp("e2e")
    url_banco = f"sqlite:///{(pasta / 'e2e.db').as_posix()}"
    _semear(url_banco)
    porta = _porta_livre()
    env = {**os.environ, "DATABASE_URL": url_banco, "STORAGE_DIR": str(pasta / "storage"), "APP_HOST": "127.0.0.1",
           "APP_PORTA": str(porta), "VERIFICACAO_HORAS": "0", "DIAS_ATENCAO": "30", "DIAS_CRITICO": "45"}
    log = open(pasta / "servidor.log", "w", encoding="utf-8")
    processo = subprocess.Popen([sys.executable, "-m", "app"], cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{porta}"
    for _ in range(60):
        try:
            urllib.request.urlopen(f"{base}/api/saude", timeout=1)
            break
        except OSError:
            if processo.poll() is not None:
                raise RuntimeError(f"O servidor não subiu; veja {pasta / 'servidor.log'}")
            time.sleep(0.5)
    else:
        processo.kill()
        raise RuntimeError("O servidor não respondeu em 30 s")
    yield base
    processo.terminate()
    processo.wait(10)
    log.close()


@pytest.fixture(scope="session")
def navegador():
    with sync_playwright() as p:
        nav = p.chromium.launch(channel=os.environ.get("E2E_CANAL", "msedge"),
                                headless=not os.environ.get("E2E_VISIVEL"))
        yield nav
        nav.close()


@pytest.fixture
def erros_console():
    return []


@pytest.fixture
def nova_pagina(navegador, erros_console):
    """Fábrica de páginas em contextos limpos (sem login, sem tema guardado). Falha o teste se houver erro de JS."""
    contextos = []

    def criar(largura=1440, altura=900, tema="light", celular=False) -> Page:
        ctx = navegador.new_context(viewport={"width": largura, "height": altura}, color_scheme=tema,
                                    is_mobile=celular, has_touch=celular)
        contextos.append(ctx)
        page = ctx.new_page()
        page.on("pageerror", lambda e: erros_console.append(str(e)))
        return page

    yield criar
    for ctx in contextos:
        ctx.close()
    assert not erros_console, f"Erros de JavaScript na página: {erros_console}"


def entrar(page: Page, base: str, login: str = "admin", senha: str | None = None) -> None:
    page.goto(f"{base}/login")
    page.get_by_label("Usuário").fill(login)
    page.get_by_label("Senha").fill(senha or SENHAS[login])
    page.get_by_role("button", name="Entrar").click()
    expect(page.get_by_role("heading", name="Painel")).to_be_visible()


@pytest.fixture
def admin(servidor, nova_pagina) -> Page:
    page = nova_pagina()
    entrar(page, servidor)
    return page
