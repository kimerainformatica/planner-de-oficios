import { useEffect, useRef, useState } from "react";
import { escala } from "../../components/graficos";
import type { ConsumoTeto, SituacaoTeto } from "../../types";
import { CLASSE_SITUACAO_TETO, percentualTeto, ROTULO_SITUACAO_TETO, valorTeto } from "../../utils/tetos";

export function SeloSituacao({ situacao }: { situacao: SituacaoTeto }) {
  return <span className={`selo-teto selo-teto-${CLASSE_SITUACAO_TETO[situacao]}`}>{ROTULO_SITUACAO_TETO[situacao]}</span>;
}

/**
 * Barra de consumo: quanto do teto do período já foi gasto. A marca vertical (opcional) mostra onde o gasto
 * "deveria" estar hoje (o teto proporcional até a data), para ver se o ritmo está acima do esperado.
 */
export function Medidor({
  titulo,
  consumo,
  unidade,
  ritmo,
  rodape,
}: {
  titulo: string;
  consumo: ConsumoTeto;
  unidade: string;
  ritmo?: number; // teto até hoje (mesma unidade)
  rodape?: React.ReactNode;
}) {
  const pct = consumo.percentual ?? 0;
  const classe = CLASSE_SITUACAO_TETO[consumo.situacao];
  const marca = ritmo !== undefined && consumo.teto > 0 ? Math.min(100, (ritmo / consumo.teto) * 100) : null;
  return (
    <div className={`medidor medidor-${classe}`}>
      <div className="medidor-topo">
        <span className="medidor-titulo">{titulo}</span>
        <strong className="medidor-pct">{percentualTeto(consumo.percentual)}</strong>
      </div>
      <div className="medidor-trilho" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}
        aria-label={`${titulo}: ${valorTeto(consumo.gasto, unidade)} de ${valorTeto(consumo.teto, unidade)}`}>
        <span className="medidor-barra" style={{ width: `${Math.min(100, pct)}%` }} />
        {marca !== null && <span className="medidor-ritmo" style={{ left: `${marca}%` }} title="Esperado até hoje" />}
      </div>
      <div className="medidor-valores">
        <span><strong>{valorTeto(consumo.gasto, unidade)}</strong> de {valorTeto(consumo.teto, unidade)}</span>
        <span className="texto-suave">
          {consumo.restante >= 0 ? `restam ${valorTeto(consumo.restante, unidade)}` : `${valorTeto(-consumo.restante, unidade)} acima`}
        </span>
      </div>
      {rodape && <div className="medidor-rodape">{rodape}</div>}
    </div>
  );
}

export interface PontoTeto {
  rotulo: string; // eixo
  titulo: string; // dica
  gasto: number;
  teto: number;
}

/** Barras do gasto por período com o teto de cada período (traço). Barra acima do teto fica vermelha. */
export function BarrasTeto({ pontos, unidade, altura = 240 }: { pontos: PontoTeto[]; unidade: string; altura?: number }) {
  const caixa = useRef<HTMLDivElement>(null);
  const [largura, setLargura] = useState(640);
  const [ativo, setAtivo] = useState<number | null>(null);

  useEffect(() => {
    const el = caixa.current;
    if (!el) return;
    const obs = new ResizeObserver(([e]) => setLargura(Math.max(280, e.contentRect.width)));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const n = pontos.length;
  const m = { esq: 56, dir: 12, topo: 12, base: 26 };
  const w = largura - m.esq - m.dir;
  const h = altura - m.topo - m.base;
  const maior = Math.max(0, ...pontos.map((p) => Math.max(p.gasto, p.teto)));
  const { max, passo } = escala(maior);
  const y = (v: number) => m.topo + h - (v / max) * h;
  const faixa = w / Math.max(1, n);
  const barra = Math.max(3, Math.min(34, faixa * 0.62));
  const x = (i: number) => m.esq + faixa * i + (faixa - barra) / 2;
  const ticks = Array.from({ length: Math.round(max / passo) + 1 }, (_, i) => i * passo);
  const cadaRotulo = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(w / 34))));
  const p = ativo !== null ? pontos[ativo] : null;

  return (
    <div className="grafico-caixa" ref={caixa} onMouseLeave={() => setAtivo(null)}>
      <svg width={largura} height={altura} role="img"
        aria-label={`Gasto por período comparado ao teto, em ${unidade}`}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.esq} x2={largura - m.dir} y1={y(t)} y2={y(t)} className="grade" />
            <text x={m.esq - 8} y={y(t) + 4} textAnchor="end" className="eixo">{valorTeto(t, unidade, true)}</text>
          </g>
        ))}
        {pontos.map((pt, i) => {
          const acima = pt.teto > 0 && pt.gasto > pt.teto;
          return (
            <g key={pt.rotulo + i} onMouseEnter={() => setAtivo(i)} onFocus={() => setAtivo(i)} tabIndex={0}
              aria-label={`${pt.titulo}: ${valorTeto(pt.gasto, unidade)} de ${valorTeto(pt.teto, unidade)}`}>
              <rect x={m.esq + faixa * i} y={m.topo} width={faixa} height={h} className="alvo-dica" />
              {pt.gasto > 0 && (
                <rect x={x(i)} y={y(pt.gasto)} width={barra} height={Math.max(1, y(0) - y(pt.gasto))} rx={Math.min(4, barra / 2)}
                  className={acima ? "barra-teto barra-teto-acima" : "barra-teto"} />
              )}
              {pt.teto > 0 && <line x1={x(i) - 3} x2={x(i) + barra + 3} y1={y(pt.teto)} y2={y(pt.teto)} className="traco-teto" />}
              {i % cadaRotulo === 0 && (
                <text x={x(i) + barra / 2} y={altura - 8} textAnchor="middle" className="eixo">{pt.rotulo}</text>
              )}
            </g>
          );
        })}
      </svg>
      {p && ativo !== null && (
        <div className="dica" role="tooltip"
          style={{ left: Math.min(Math.max(0, x(ativo) + barra + 8), largura - 200), top: Math.max(0, y(Math.max(p.gasto, p.teto)) - 10) }}>
          <div className="dica-titulo">{p.titulo}</div>
          <div className="dica-linha"><span className="chave-barra" style={{ background: "var(--serie-1)" }} aria-hidden />
            <strong>{valorTeto(p.gasto, unidade)}</strong><span className="texto-suave">gasto</span></div>
          <div className="dica-linha"><span className="chave-linha" style={{ background: "var(--texto)" }} aria-hidden />
            <strong>{valorTeto(p.teto, unidade)}</strong><span className="texto-suave">teto</span></div>
        </div>
      )}
    </div>
  );
}
