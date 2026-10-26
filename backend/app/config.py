from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # 0.0.0.0 = aceita acesso de outros computadores da rede; 127.0.0.1 = só esta máquina
    app_host: str = "0.0.0.0"
    app_porta: int = 3112

    database_url: str ="mysql+pymysql://oficios:oficios_senha@127.0.0.1:3307/oficios?charset=utf8mb4"

    jwt_secret: str = "troque-esta-chave"
    jwt_algoritmo: str = "HS256"
    jwt_expira_minutos: int = 480

    storage_dir: Path = BASE_DIR / "storage"
    upload_max_mb: int = 20
    extensoes_permitidas: set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".odt"}

    # Prazos em DIAS ÚTEIS contados a partir da data do ofício
    dias_atencao: int = 30
    dias_critico: int = 45

    # Login: depois de LOGIN_MAX_TENTATIVAS senhas erradas seguidas, bloqueia por LOGIN_BLOQUEIO_MINUTOS
    login_max_tentativas: int = 5
    login_bloqueio_minutos: int = 5

    # Conferência automática dos arquivos (existência e hash), a cada N horas; 0 desliga
    verificacao_horas: int = 24

    cors_origins: list[str] = ["http://localhost:5173"]
    # Libera o front aberto por qualquer endereço da rede interna (10.x, 172.16–31.x, 192.168.x)
    cors_origin_regex: str | None = (
        r"^https?://(localhost|127\.0\.0\.1|10(\.\d{1,3}){3}|192\.168(\.\d{1,3}){2}"
        r"|172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2})(:\d+)?$"
    )

    @property
    def chave_jwt_insegura(self) -> bool:
        return self.jwt_secret == "troque-esta-chave" or len(self.jwt_secret) < 32


@lru_cache
def get_settings() -> Settings:
    return Settings()
