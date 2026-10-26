"""Gravação dos anexos em disco. O banco guarda apenas o caminho relativo e os metadados."""

import hashlib
import mimetypes
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.models import Anexo, AnexoLixeira, Usuario

BLOCO = 1024 * 1024


@dataclass(frozen=True)
class ArquivoSalvo:
    caminho: str
    nome_original: str
    mime_type: str
    tamanho_bytes: int
    hash_sha256: str


def salvar_upload(arquivo: UploadFile, settings: Settings) -> ArquivoSalvo:
    nome = Path(arquivo.filename or "").name
    extensao = Path(nome).suffix.lower()
    if extensao not in settings.extensoes_permitidas:
        permitidas = ", ".join(sorted(settings.extensoes_permitidas))
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Tipo de arquivo não aceito. Use: {permitidas}")

    hoje = date.today()
    relativo = PurePosixPath(f"{hoje:%Y}", f"{hoje:%m}", f"{uuid4().hex}{extensao}")
    destino = settings.storage_dir / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)

    limite = settings.upload_max_mb * 1024 * 1024
    sha, tamanho = hashlib.sha256(), 0
    try:
        with destino.open("wb") as saida:
            while bloco := arquivo.file.read(BLOCO):
                tamanho += len(bloco)
                if tamanho > limite:
                    raise HTTPException(
                        status.HTTP_413_CONTENT_TOO_LARGE, f"Arquivo maior que {settings.upload_max_mb} MB"
                    )
                sha.update(bloco)
                saida.write(bloco)
        if tamanho == 0:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Arquivo vazio")
    except BaseException:
        destino.unlink(missing_ok=True)
        raise

    mime = mimetypes.guess_type(nome)[0] or arquivo.content_type or "application/octet-stream"
    return ArquivoSalvo(str(relativo), nome, mime, tamanho, sha.hexdigest())


def caminho_absoluto(relativo: str, settings: Settings) -> Path:
    base = settings.storage_dir.resolve()
    caminho = (base / relativo).resolve()
    if not caminho.is_relative_to(base):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Caminho de arquivo inválido")
    return caminho


def remover_arquivo(relativo: str, settings: Settings) -> None:
    caminho_absoluto(relativo, settings).unlink(missing_ok=True)


def para_lixeira(anexo: Anexo, motivo: str, usuario: Usuario) -> AnexoLixeira:
    """Cópia do anexo atual para a lixeira (o arquivo fica onde está). O chamador adiciona à sessão."""
    return AnexoLixeira(
        oficio_id=anexo.oficio_id, tipo=anexo.tipo, ciclo=anexo.ciclo, historico_id=anexo.historico_id,
        nome_original=anexo.nome_original, caminho=anexo.caminho, mime_type=anexo.mime_type,
        tamanho_bytes=anexo.tamanho_bytes, hash_sha256=anexo.hash_sha256, enviado_por_id=anexo.enviado_por_id,
        enviado_em=anexo.enviado_em, motivo=motivo, descartado_por_id=usuario.id,
    )
