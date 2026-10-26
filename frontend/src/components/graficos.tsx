/**
 * Gráficos do painel (SVG/HTML próprios, sem biblioteca).
 * Regras: marcas finas, ponta arredondada de 4px, 2px de espaço entre segmentos, grade em hairline,
 * legenda sempre que há 2+ séries, dica ao passar o mouse/focar e tabela equivalente em todo gráfico.
 */
import { BarChart3, Table2 } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";

export interface Serie {
  nome: string;
  cor: string; // variável CSS, ex.: "var(--serie-1)"
}

/** Escala "redonda" para eixos de contagem: 0, passo, 2·passo… */
export function escala(maximo: number, alvo = 4): { max: number; passo: number } {
  if (maximo <= 0) return { max: alvo, passo: 1 };
  const bruto = maximo / alvo;
  const potencia = 10 ** Math.floor(Math.log10(bruto));
  const passo = Math.max(1, [1, 2, 5, 10].map((m) => m * potencia).find((p) => p >= bruto) ?? bruto);
  return { max: Math.ceil(maximo / passo) * passo, passo };
}

const numero = (v: number) => v.toLocaleString("pt-BR", { maximumFractionDigits: 1 });

// ---------- moldura comum: título, legenda, alternância gráfico/tabela ----------

export function CartaoGrafico({
  titulo,
  subtitulo,
  series,
  tabela,
  children,
  carregando,
  legendaLinha,
}: {
  titulo: string;
  subtitulo?: string;
  series?: Serie[];
  tabela: ReactNode;
  children: ReactNode;
  carregando?: boolean;
  legendaLinha?: boolean; // a chave da legenda imita a marca: traço para linhas, bloco para barras
}) {
  const [verTabela, setVerTabela] = useState(false);
  return (
    <section className={`painel-bloco grafico ${carregando ? "recarregando" : ""}`}>
      <div className="bloco-topo">
        <div>
          <h2>{titulo}</h2>
          {subtitulo && <small className="texto-suave">{subtitulo}</small>}
        </div>
        <button className="btn btn-fantasma btn-pequeno" aria-pressed={verTabela} onClick={() => setVerTabela((v) => !v)}>
          {verTabela ? <BarChart3 size={15} /> : <Table2 size={15} />}
          {verTabela ? "Ver gráfico" : "Ver tabela"}
        </button>
      </div>
      {series && series.length > 1 && !verTabela && <Legenda series={series} linha={legendaLinha} />}
      {verTabela ? <div className="tabela-mini-box">{tabela}</div> : children}
    </section>
  );
}

export function Legenda({ series, linha }: { series: Serie[]; linha?: boolean }) {
  return (
    <ul className="legenda">
      {series.map((s) => (
        <li key={s.nome}>
          <span className={linha ? "chave-linha" : "chave-barra"} style={{ background: s.cor }} aria-hidden />
          {s.nome}
        </li>
      ))}
    </ul>
  );
}

// ---------- dica (tooltip) ----------

interface DicaEstado {
  x: number;
  y: number;
  titulo: string;
  linhas: { serie: Serie; valor: string }[];
}

function Dica({ dica }: { dica: DicaEstado | null }) {
  if (!dica) return null;
  return (
    <div className="dica" style={{ left: dica.x, top: dica.y }} role="tooltip">
      <div className="dica-titulo">{dica.titulo}</div>
      {dica.linhas.map((l) => (
        <div key={l.serie.nome} className="dica-linha">
          <span className="chave-linha" style={{ background: l.serie.cor }} aria-hidden />
          <strong>{l.valor}</strong>
          <span className="texto-suave">{l.serie.nome}</span>
        </div>
      ))}
    </div>
  );
}

/** Posição da dica relativa ao contêiner, mantida dentro dele. */
function posicao(container: HTMLElement | null, clienteX: number, clienteY: number) {
  const r = container?.getBoundingClientRect();
  if (!r) return { x: 0, y: 0 };
  const x = Math.min(Math.max(clienteX - r.left + 14, 0), r.width - 190);
  return { x: Math.max(0, x), y: clienteY - r.top + 14 };
}

// ---------- barras horizontais (empilhadas ou simples) ----------

export interface LinhaBarra {
  chave: string;
  rotulo: string;
  valores: number[]; // um por série
  total?: string; // rótulo na ponta (padrão: soma)
}

export function BarrasHorizontais({
  linhas,
  series,
  aoClicar,
  formatar = numero,
  rotuloVazio = "Sem dados para os filtros escolhidos.",
}: {
  linhas: LinhaBarra[];
  series: Serie[];
  aoClicar?: (chave: string) => void;
  formatar?: (v: number) => string;
  rotuloVazio?: string;
}) {
  const caixa = useRef<HTMLDivElement>(null);
  const [dica, setDica] = useState<DicaEstado | null>(null);
  const [ativa, setAtiva] = useState<string | null>(null);
  const somas = linhas.map((l) => l.valores.reduce((a, b) => a + b, 0));
  if (somas.every((s) => s === 0)) return <p className="texto-suave grafico-vazio">{rotuloVazio}</p>;
  const { max, passo } = escala(Math.max(...somas));
  const ticks = Array.from({ length: max / passo + 1 }, (_, i) => i * passo);

  function mostrar(l: LinhaBarra, x: number, y: number) {
    setAtiva(l.chave);
    setDica({
      ...posicao(caixa.current, x, y),
      titulo: l.rotulo,
      linhas: series.map((s, i) => ({ serie: s, valor: formatar(l.valores[i]) })),
    });
  }
  const esconder = () => {
    setAtiva(null);
    setDica(null);
  };

  return (
    <div className="barras" ref={caixa} onMouseLeave={esconder}>
      {linhas.map((l, i) => (
        <div
          key={l.chave}
          className={`barra-linha ${aoClicar ? "clicavel" : ""} ${ativa === l.chave ? "ativa" : ""}`}
          tabIndex={0}
          role={aoClicar ? "button" : undefined}
          aria-label={`${l.rotulo}: ${series.map((s, j) => `${s.nome} ${formatar(l.valores[j])}`).join(", ")}`}
          onMouseMove={(e) => mostrar(l, e.clientX, e.clientY)}
          onFocus={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            mostrar(l, r.left + r.width / 2, r.bottom - 8);
          }}
          onBlur={esconder}
          onClick={() => aoClicar?.(l.chave)}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && aoClicar && (e.preventDefault(), aoClicar(l.chave))}
        >
          <span className="barra-rotulo" title={l.rotulo}>
            {l.rotulo}
          </span>
          <div
            className="barra-trilho"
            style={{ backgroundSize: `${(passo / max) * 100}% 100%` }}
          >
            <div className="barra" style={{ width: `${(somas[i] / max) * 100}%` }}>
              {l.valores.map((v, j) =>
                v > 0 ? <span key={j} className="barra-seg" style={{ flexGrow: v, background: series[j].cor }} /> : null,
              )}
            </div>
            <span className="barra-valor">{l.total ?? formatar(somas[i])}</span>
          </div>
        </div>
      ))}
      <div className="barra-linha barra-eixo" aria-hidden>
        <span />
        <div className="barra-trilho sem-grade">
          {ticks.map((t) => (
            <span key={t} className="tick" style={{ left: `${(t / max) * 100}%` }}>
              {formatar(t)}
            </span>
          ))}
        </div>
      </div>
      <Dica dica={dica} />
    </div>
  );
}

// ---------- linhas (evolução mensal) ----------

export function LinhasTempo({
  rotulos,
  dados,
  series,
  altura = 230,
}: {
  rotulos: string[];
  dados: number[][]; // [série][ponto]
  series: Serie[];
  altura?: number;
}) {
  const caixa = useRef<HTMLDivElement>(null);
  const [largura, setLargura] = useState(600);
  const [indice, setIndice] = useState<number | null>(null);

  useEffect(() => {
    const el = caixa.current;
    if (!el) return;
    const obs = new ResizeObserver(([e]) => setLargura(Math.max(260, e.contentRect.width)));
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const n = rotulos.length;
  if (n === 0 || dados.every((s) => s.every((v) => v === 0))) {
    return <p className="texto-suave grafico-vazio">Sem dados para os filtros escolhidos.</p>;
  }
  const m = { esq: 36, dir: 16, topo: 12, base: 28 };
  const w = largura - m.esq - m.dir;
  const h = altura - m.topo - m.base;
  const { max, passo } = escala(Math.max(...dados.flat()));
  const x = (i: number) => m.esq + (n === 1 ? w / 2 : (i / (n - 1)) * w);
  const y = (v: number) => m.topo + h - (v / max) * h;
  const ticks = Array.from({ length: max / passo + 1 }, (_, i) => i * passo);
  const cadaRotulo = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(w / 52))));

  function apontar(clienteX: number) {
    const r = caixa.current?.getBoundingClientRect();
    if (!r) return;
    const rel = clienteX - r.left - m.esq;
    setIndice(Math.min(n - 1, Math.max(0, Math.round(n === 1 ? 0 : (rel / w) * (n - 1)))));
  }

  const dica: DicaEstado | null =
    indice === null
      ? null
      : {
          x: Math.min(x(indice) + 12, largura - 190),
          y: m.topo,
          titulo: rotulos[indice],
          linhas: series.map((s, j) => ({ serie: s, valor: numero(dados[j][indice]) })),
        };

  return (
    <div
      className="linhas"
      ref={caixa}
      tabIndex={0}
      role="img"
      aria-label={`Evolução mensal: ${series.map((s) => s.nome).join(" e ")}. Use as setas para percorrer os meses.`}
      onMouseMove={(e) => apontar(e.clientX)}
      onMouseLeave={() => setIndice(null)}
      onBlur={() => setIndice(null)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") setIndice((i) => Math.min(n - 1, (i ?? -1) + 1));
        if (e.key === "ArrowLeft") setIndice((i) => Math.max(0, (i ?? n) - 1));
      }}
    >
      <svg width={largura} height={altura} aria-hidden>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.esq} x2={m.esq + w} y1={y(t)} y2={y(t)} className="grade" />
            <text x={m.esq - 8} y={y(t)} className="eixo-texto" textAnchor="end" dominantBaseline="middle">
              {numero(t)}
            </text>
          </g>
        ))}
        {rotulos.map((r, i) =>
          i % cadaRotulo === 0 || i === n - 1 ? (
            <text key={r} x={x(i)} y={altura - 8} className="eixo-texto" textAnchor="middle">
              {r}
            </text>
          ) : null,
        )}
        {indice !== null && <line x1={x(indice)} x2={x(indice)} y1={m.topo} y2={m.topo + h} className="mira" />}
        {dados.map((serie, j) => (
          <g key={series[j].nome}>
            <polyline
              points={serie.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
              fill="none"
              stroke={series[j].cor}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {[indice ?? n - 1].map((i) => (
              <circle key={i} cx={x(i)} cy={y(serie[i])} r={4} fill={series[j].cor} className="ponto" />
            ))}
          </g>
        ))}
      </svg>
      <Dica dica={dica} />
    </div>
  );
}

// ---------- tabela equivalente ----------

export function TabelaMini({ cabecalho, linhas }: { cabecalho: string[]; linhas: (string | number)[][] }) {
  return (
    <table className="tabela tabela-mini">
      <thead>
        <tr>
          {cabecalho.map((c, i) => (
            <th key={c} className={i > 0 ? "num" : undefined}>
              {c}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {linhas.map((l, i) => (
          <tr key={i}>
            {l.map((v, j) => (
              <td key={j} className={j > 0 ? "num" : undefined}>
                {v}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
