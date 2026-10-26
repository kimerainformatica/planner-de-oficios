from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, get_settings
from app.routers import anexos, auditoria, auth, dashboard, exclusoes, feriados, lixeira, oficios, tipos, usuarios

app = FastAPI(
    title="Planner de Ofícios",
    description="Controle de ofícios com prazos em dias úteis (atenção e crítico: DIAS_ATENCAO e DIAS_CRITICO).",
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

for modulo in (auth, usuarios, oficios, anexos, lixeira, exclusoes, auditoria, dashboard, feriados, tipos):
    app.include_router(modulo.router)


@app.get("/api/saude", tags=["Sistema"])
def saude():
    return {"status": "ok"}


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
