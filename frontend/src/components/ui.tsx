import { AlertTriangle, ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { useEffect, useId, type ReactNode } from "react";
import type { NivelAlerta, StatusOficio } from "../types";
import { diasUteis, ROTULO_ALERTA, ROTULO_STATUS } from "../utils/formato";

const ROTULO_CURTO: Partial<Record<StatusOficio, string>> = {
  PENDENTE_RESPOSTA: "Pendente",
  PENDENTE_RECEBIMENTO: "Aguard. entrega",
};

export function StatusBadge({ status, curto }: { status: StatusOficio; curto?: boolean }) {
  const rotulo = (curto && ROTULO_CURTO[status]) || ROTULO_STATUS[status];
  return (
    <span className={`badge badge-status-${status}`} title={ROTULO_STATUS[status]}>
      {status.startsWith("PENDENTE") && <span className="ponto-vivo" aria-hidden />}
      {rotulo}
    </span>
  );
}

export function AlertaBadge({ nivel, dias }: { nivel: NivelAlerta | null; dias?: number }) {
  if (!nivel) return <span className="texto-suave">—</span>;
  return (
    <span className={`badge badge-alerta-${nivel}`} title={dias !== undefined ? diasUteis(dias) : undefined}>
      <span className="ponto" aria-hidden />
      {ROTULO_ALERTA[nivel]}
    </span>
  );
}

export function Carregando({ texto = "Carregando…" }: { texto?: string }) {
  return (
    <div className="estado">
      <Loader2 className="girando" size={20} />
      {texto}
    </div>
  );
}

export function ErroBox({ erro }: { erro: unknown }) {
  return (
    <div className="estado estado-erro">
      <AlertTriangle size={20} />
      {erro instanceof Error ? erro.message : "Não foi possível carregar."}
    </div>
  );
}

export function Vazio({ children }: { children: ReactNode }) {
  return <div className="estado">{children}</div>;
}

export function Campo({
  rotulo,
  dica,
  children,
}: {
  rotulo: string;
  dica?: string;
  children: (id: string) => ReactNode;
}) {
  const id = useId();
  return (
    <div className="campo">
      <label htmlFor={id}>{rotulo}</label>
      {children(id)}
      {dica && <small className="texto-suave">{dica}</small>}
    </div>
  );
}

export function Modal({
  titulo,
  aoFechar,
  children,
  rodape,
}: {
  titulo: string;
  aoFechar: () => void;
  children: ReactNode;
  rodape?: ReactNode;
}) {
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [aoFechar]);

  return (
    <div className="modal-fundo" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo}>
        <header className="modal-topo">
          <h2>{titulo}</h2>
          <button className="btn-icone" onClick={aoFechar} aria-label="Fechar">
            <X size={18} />
          </button>
        </header>
        <div className="modal-corpo">{children}</div>
        {rodape && <footer className="modal-rodape">{rodape}</footer>}
      </div>
    </div>
  );
}

export function Paginacao({
  pagina,
  total,
  porPagina,
  aoMudar,
}: {
  pagina: number;
  total: number;
  porPagina: number;
  aoMudar: (p: number) => void;
}) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  if (total === 0) return null;
  const inicio = (pagina - 1) * porPagina + 1;
  const fim = Math.min(total, pagina * porPagina);
  return (
    <div className="paginacao">
      <span className="texto-suave">
        {inicio}–{fim} de {total}
      </span>
      <div className="grupo">
        <button className="btn btn-secundario btn-pequeno" disabled={pagina <= 1} onClick={() => aoMudar(pagina - 1)}>
          <ChevronLeft size={16} /> Anterior
        </button>
        <span className="texto-suave">
          Página {pagina} de {paginas}
        </span>
        <button
          className="btn btn-secundario btn-pequeno"
          disabled={pagina >= paginas}
          onClick={() => aoMudar(pagina + 1)}
        >
          Próxima <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

export function Botao({
  carregando,
  children,
  className = "btn btn-primario",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { carregando?: boolean }) {
  return (
    <button className={className} disabled={carregando || props.disabled} {...props}>
      {carregando && <Loader2 className="girando" size={16} />}
      {children}
    </button>
  );
}
