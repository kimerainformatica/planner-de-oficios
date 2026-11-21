from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.deps import SettingsDep
from app.routers import (
    anexos, auditoria, auth, dashboard, documentos, exclusoes, feriados, lixeira, manutencao, modulos, oficios,
    preventivas, tetos, tipos, usuarios,
)

app = FastAPI(
    title="Planner de Ofícios",
    description="Controle de ofícios com prazos em dias corridos (atenção e crítico: DIAS_ATENCAO e DIAS_CRITICO).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_origin_regex=get_settings().cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

for rota in (auth, usuarios, modulos, oficios, anexos, lixeira, exclusoes, auditoria, dashboard, feriados, tipos,
             manutencao, preventivas, tetos, documentos):
    app.include_router(rota.router)
app.include_router(documentos.publico)


@app.get("/api/saude", tags=["Sistema"])
def saude():
    return {"status": "ok"}


@app.get("/api/unidade", tags=["Sistema"], summary="Unidade atendida por este servidor (aparece no login e nas telas)")
def unidade(settings: SettingsDep):
    """Pública: a tela de login mostra o nome da unidade. Vem do .env (UNIDADE_NOME e UNIDADE_DESCRICAO)."""
    return {"nome": settings.unidade_nome.strip() or None, "descricao": settings.unidade_descricao.strip() or None}


# ---------- Front-end (frontend/dist, gerado por `npm run build`) ----------
# Servido pela própria API: um único endereço e uma única porta para todo o sistema.
FRONT = BASE_DIR.parent / "frontend" / "dist"

if FRONT.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONT / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def front(caminho: str):
        if caminho.startswith("api/"):
            raise HTTPException(404, "Rota da API não encontrada")
        arquivo = (FRONT / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(FRONT.resolve()):
            return FileResponse(arquivo)
        # Rotas do React (/oficios/12, /usuarios…) devolvem o index.html
        return FileResponse(FRONT / "index.html", headers={"Cache-Control": "no-cache"})
