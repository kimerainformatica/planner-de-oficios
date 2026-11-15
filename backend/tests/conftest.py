"""Os testes usam SQLite em memória; em produção o banco é o MySQL do docker-compose."""

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.database import Base, get_db
from app.deps import get_agora, get_hoje
from app.main import app
from app.models import EmpresaManutencao, Modulo, Perfil, Usuario, UsuarioModulo
from app.seguranca import gerar_hash_senha
from app.services import limite_login, manutencao, tipos

HOJE = date(2026, 10, 20)  # terça-feira
AGORA = datetime(2026, 10, 20, 10, 0)  # terça-feira, 10:00


@pytest.fixture
def estado():
    """Permite que um teste altere a data "de hoje" vista pela API."""
    return {"hoje": HOJE, "agora": AGORA}


@pytest.fixture
def api(tmp_path, estado):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conexao, _: conexao.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    limite_login.limpar()
    with Sessao() as db:
        tipos.semear(db)
        manutencao.semear_empresas(db)  # MSI, REALIZA PREDIAL, REALIZA CLIMATIZAÇÃO
        empresa = {e.nome: e for e in db.query(EmpresaManutencao)}

        def acesso(modulo, perfil, empresa=None):
            return UsuarioModulo(modulo=modulo, perfil=perfil, empresa=empresa)

        db.add_all(
            [
                Usuario(nome="Master", login="master", senha_hash=gerar_hash_senha("senha-master"),
                        perfil=Perfil.MASTER),
                # Admin e clientes do Planner de Ofícios (o papel em cada módulo fica em usuario_modulos)
                Usuario(nome="Admin", login="admin", senha_hash=gerar_hash_senha("senha-admin"),
                        modulos=[acesso(Modulo.OFICIOS, Perfil.ADMIN)]),
                Usuario(nome="Ana", login="ana", senha_hash=gerar_hash_senha("senha-ana"),
                        modulos=[acesso(Modulo.OFICIOS, Perfil.CLIENTE)]),
                Usuario(nome="Bruno", login="bruno", senha_hash=gerar_hash_senha("senha-bruno"),
                        modulos=[acesso(Modulo.OFICIOS, Perfil.CLIENTE)]),
                # Operacionais da Manutenção Clínica: pela regra, também são clientes do Planner de Ofícios
                Usuario(nome="Marta", login="marta", senha_hash=gerar_hash_senha("senha-marta"),
                        modulos=[acesso(Modulo.MANUTENCAO, Perfil.ADMIN), acesso(Modulo.OFICIOS, Perfil.CLIENTE)]),
                Usuario(nome="Paulo", login="paulo", senha_hash=gerar_hash_senha("senha-paulo"),
                        modulos=[acesso(Modulo.MANUTENCAO, Perfil.CLIENTE), acesso(Modulo.OFICIOS, Perfil.CLIENTE)]),
                # Técnicos da Manutenção Clínica, cada um de uma empresa
                Usuario(nome="Tiago", login="tiago", senha_hash=gerar_hash_senha("senha-tiago"),
                        modulos=[acesso(Modulo.MANUTENCAO, Perfil.TECNICO, empresa["MSI"])]),
                Usuario(nome="Carla", login="carla", senha_hash=gerar_hash_senha("senha-carla"),
                        modulos=[acesso(Modulo.MANUTENCAO, Perfil.TECNICO, empresa["REALIZA CLIMATIZAÇÃO"])]),
            ]
        )
        db.commit()

    def db_teste():
        with Sessao() as db:
            yield db

    # Limites de alerta fixos nos testes (15/30), independentes do .env; o padrão real é testado à parte
    settings = Settings(
        database_url="sqlite://", jwt_secret="chave-de-teste-" * 4, storage_dir=tmp_path / "storage", upload_max_mb=1,
        dias_atencao=15, dias_critico=30, unidade_nome="", unidade_descricao="",
    )
    app.dependency_overrides[get_db] = db_teste
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_hoje] = lambda: estado["hoje"]
    app.dependency_overrides[get_agora] = lambda: estado["agora"]
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


@pytest.fixture
def marta(api):
    """Administradora só do módulo Manutenção Clínica."""
    return _token(api, "marta")


@pytest.fixture
def paulo(api):
    """Operacional (cliente) só do módulo Manutenção Clínica."""
    return _token(api, "paulo")


@pytest.fixture
def tiago(api):
    """Técnico da MSI."""
    return _token(api, "tiago")


@pytest.fixture
def carla(api):
    """Técnica da REALIZA CLIMATIZAÇÃO."""
    return _token(api, "carla")
