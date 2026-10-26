// Dados do ofício em blocos e a barra do prazo.
import { type ReactNode } from "react";
import type { Prazos } from "../../types";
import { data, diasUteis } from "../../utils/formato";

export function BlocoDados({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="bloco-dados">
      <h3>{titulo}</h3>
      <dl className="dados">{children}</dl>
    </div>
  );
}

export function Dado({ rotulo, valor }: { rotulo: string; valor: ReactNode }) {
  return (
    <div>
      <dt>{rotulo}</dt>
      <dd>{valor}</dd>
    </div>
  );
}

/** "15/09/2026 · 9 dias úteis" */
export function DataComDias({ iso, dias }: { iso: string; dias: number | null }) {
  return (
    <>
      {data(iso)}
      {dias !== null && <span className="dado-extra"> · {diasUteis(dias)}</span>}
    </>
  );
}

export function BarraPrazo({
  dias,
  reaberto,
  etapa,
  prazos: { dias_atencao: atencao, dias_critico: critico },
}: {
  dias: number;
  reaberto: boolean;
  etapa: "resposta" | "recebimento";
  prazos: Prazos;
}) {
  const pct = Math.min(100, (dias / critico) * 100);
  const nivel = dias >= critico ? "CRITICO" : dias >= atencao ? "ATENCAO" : "NORMAL";
  const falta = dias >= critico ? null : dias >= atencao ? critico - dias : atencao - dias;
  return (
    <section className="cartao prazo">
      {etapa === "recebimento" && <span className="prazo-etapa">Etapa de recebimento · resposta já confirmada</span>}
      <div className="prazo-texto">
        <strong>{diasUteis(dias)}</strong>{" "}
        {etapa === "recebimento" ? "aguardando a entrega desde a resposta" : `sem resposta${reaberto ? " desde a reabertura" : ""}`}
        <span className="texto-suave">
          {falta === null
            ? " · prazo crítico atingido"
            : ` · faltam ${diasUteis(falta)} para ${dias >= atencao ? "ficar crítico" : "entrar em atenção"}`}
        </span>
      </div>
      <div className="prazo-trilho" role="progressbar" aria-valuemin={0} aria-valuemax={critico} aria-valuenow={dias}>
        <div className={`prazo-preenchido seg-${nivel}`} style={{ width: `${pct}%` }} />
        <span className="prazo-marca" style={{ left: `${(atencao / critico) * 100}%` }} />
      </div>
      <div className="prazo-escala texto-suave">
        <span>0</span>
        <span className="prazo-escala-meio" style={{ left: `${(atencao / critico) * 100}%` }}>
          {atencao} · atenção
        </span>
        <span>{critico} · crítico</span>
      </div>
    </section>
  );
}
