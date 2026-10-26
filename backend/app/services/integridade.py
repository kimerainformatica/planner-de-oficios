"""Verificação dos arquivos guardados: cada anexo (e cada versão na lixeira) ainda existe e tem o mesmo hash
SHA-256 de quando foi enviado? Roda sozinha (ao ligar e depois a cada VERIFICACAO_HORAS) e sob demanda.
"""

import hashlib
import logging
import threading
import time
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Anexo, AnexoLixeira, Oficio
from app.schemas import ProblemaArquivo, VerificacaoArquivos
from app.services.armazenamento import BLOCO, caminho_absoluto

log = logging.getLogger("planner.integridade")

_ultima: VerificacaoArquivos | None = None
_trava = threading.Lock()


def _hash(caminho) -> str:
    sha = hashlib.sha256()
    with caminho.open("rb") as f:
        while bloco := f.read(BLOCO):
            sha.update(bloco)
    return sha.hexdigest()


def verificar(db: Session, settings: Settings) -> VerificacaoArquivos:
    global _ultima
    with _trava:  # uma verificação por vez (a automática e a do botão podem coincidir)
        problemas: list[ProblemaArquivo] = []
        usados: set = set()
        total = 0
        for origem, modelo in (("anexo", Anexo), ("lixeira", AnexoLixeira)):
            for item, numero in db.execute(select(modelo, Oficio.numero).join(Oficio, modelo.oficio_id == Oficio.id)):
                total += 1
                caminho = caminho_absoluto(item.caminho, settings)
                usados.add(caminho)
                problema = None
                if not caminho.is_file():
                    problema = "AUSENTE"
                elif _hash(caminho) != item.hash_sha256:
                    problema = "ALTERADO"
                if problema:
                    problemas.append(ProblemaArquivo(origem=origem, id=item.id, oficio_id=item.oficio_id,
                                                     oficio_numero=numero, nome_original=item.nome_original,
                                                     problema=problema))
        pasta = settings.storage_dir.resolve()
        sobras = sum(1 for c in pasta.rglob("*") if c.is_file() and c.resolve() not in usados) if pasta.is_dir() else 0
        _ultima = VerificacaoArquivos(verificado_em=datetime.now(), arquivos=total, problemas=problemas,
                                      sem_registro=sobras)
        if problemas:
            log.warning("Verificação dos arquivos: %d problema(s): %s", len(problemas),
                        "; ".join(f"ofício {p.oficio_numero} · {p.nome_original} ({p.problema})" for p in problemas))
        else:
            log.info("Verificação dos arquivos: %d arquivo(s) íntegros", total)
        return _ultima


def ultima() -> VerificacaoArquivos | None:
    return _ultima


def iniciar_agendamento(settings: Settings) -> None:
    """Thread em segundo plano do servidor (python -m app). Os testes não a iniciam."""
    if settings.verificacao_horas <= 0:
        return
    from app.database import SessionLocal  # importado aqui: só o servidor de verdade usa o banco configurado

    def laco():
        time.sleep(60)  # deixa o servidor terminar de subir
        while True:
            try:
                with SessionLocal() as db:
                    verificar(db, settings)
            except Exception:
                log.exception("Falha na verificação automática dos arquivos")
            time.sleep(settings.verificacao_horas * 3600)

    threading.Thread(target=laco, name="verificacao-arquivos", daemon=True).start()
