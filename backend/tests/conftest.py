"""Os testes usam SQLite em memória; em produção o banco é o MySQL do docker-compose."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.deps import get_hoje
from app.main import app
from app.models import Perfil, Usuario
from app.seguranca import gerar_hash_senha
from app.services import limite_login, tipos

HOJE = date(2026, 10, 20)  # terça-feira


@pytest.fixture
def estado():
    """Permite que um teste altere a data "de hoje" vista pela API."""
    return {"hoje": HOJE}


@pytest.fixture
def api(tmp_path, estado):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conexao, _: conexao.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    limite_login.limpar()
    with Sessao() as db:
        tipos.semear(db)
        db.add_all(
            [
                Usuario(nome="Master", login="master", senha_hash=gerar_hash_senha("senha-master"),
                        perfil=Perfil.MASTER),
                Usuario(nome="Admin", login="admin", senha_hash=gerar_hash_senha("senha-admin"), perfil=Perfil.ADMIN),
                Usuario(nome="Ana", login="ana", senha_hash=gerar_hash_senha("senha-ana")),
                Usuario(nome="Bruno", login="bruno", senha_hash=gerar_hash_senha("senha-bruno")),
            ]
        )
        db.commit()

    def db_teste():
        with Sessao() as db:
            yield db

    # Limites de alerta fixos nos testes (15/30), independentes do .env; o padrão real é testado à parte
    settings = Settings(
        database_url="sqlite://", jwt_secret="chave-de-teste-" * 4, storage_dir=tmp_path / "storage", upload_max_mb=1,
        dias_atencao=15, dias_critico=30,
    )
    app.dependency_overrides[get_db] = db_teste
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_hoje] = lambda: estado["hoje"]
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(api, login):
    r = api.post("/api/auth/login", data={"username": login, "password": f"senha-{login}"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def master(api):
    return _token(api, "master")


@pytest.fixture
def admin(api):
    return _token(api, "admin")


@pytest.fixture
def ana(api):
    return _token(api, "ana")


@pytest.fixture
def bruno(api):
    return _token(api, "bruno")
