import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowLeft, CalendarDays, CalendarRange, History, ListPlus, ReceiptText } from "lucide-react";
import { type CSSProperties } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { indicadoresTeto, obterTipoTeto } from "../../api/endpoints";
import { CartaoGrafico, LinhasTempo, TabelaMini } from "../../components/graficos";
import { Carregando, ErroBox } from "../../components/ui";
import { data as dataBr, dataHora } from "../../utils/formato";
import { MESES, MESES_LONGOS, NOME_PERIODO, ROTULO_PERIODO, percentualTeto, valorTeto } from "../../utils/tetos";
import { BarrasTeto, Medidor, SeloSituacao } from "./comum";

type Aba = "diario" | "mensal" | "anual";
const ABAS: Record<Aba, string> = { diario: "Dia a dia", mensal: "Mês a mês", anual: "Ano a ano" };

export function TipoTetoDetalhe() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const hoje = new Date();
  const ano = Number(params.get("ano") ?? hoje.getFullYear());
  const mes = Number(params.get("mes") ?? (ano === hoje.getFullYear() ? hoje.getMonth() + 1 : 12));
  const aba = (params.get("aba") as Aba | null) ?? "diario";
  const mudar = (novos: Record<string, string | undefined>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(novos)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p, { replace: true });
  };

  const tipo = useQuery({ queryKey: ["tipo-teto", id], queryFn: () => obterTipoTeto(id) });
  const ind = useQuery({
    queryKey: ["tetos-indicadores", id, ano, mes], queryFn: () => indicadoresTeto(id, { ano, mes }),
    placeholderData: keepPreviousData,
  });

  if (tipo.isPending || ind.isPending) return <Carregando />;
  if (tipo.isError) return <ErroBox erro={tipo.error} />;
  if (ind.isError) return <ErroBox erro={ind.error} />;

  const t = tipo.data;
  const r = ind.data.resumo;
  const u = t.unidade;
  const anos = Array.from({ length: hoje.getFullYear() - 2019 }, (_, i) => hoje.getFullYear() - i);
  const nomeMes = `${MESES_LONGOS[mes - 1]} de ${ano}`;

  return (
    <>
      <header className="pagina-topo">
        <div>
          <Link to="/tetos" className="link voltar"><ArrowLeft size={16} /> Painel</Link>
          <h1>{t.nome}</h1>
          <p className="texto-suave">
            {t.setor.nome} · teto {t.valor !== null && t.periodo ? `${valorTeto(t.valor, u)} ${ROTULO_PERIODO[t.periodo]}` : "não definido"}
            {t.equivalentes && ` (≈ ${valorTeto(t.equivalentes.diario, u)}/dia · ${valorTeto(t.equivalentes.mensal, u)}/mês · ${valorTeto(t.equivalentes.anual, u)}/ano)`}
            {!t.ativo && " · desativado"}
          </p>
        </div>
        <div className="grupo">
          <Link to={`/tetos/lancamentos?tipo=${t.id}`} className="btn btn-secundario"><ReceiptText size={17} /> Lançamentos</Link>
          {t.ativo && <Link to={`/tetos/lancamentos?novo=1&tipo=${t.id}`} className="btn btn-primario"><ListPlus size={17} /> Lançar gasto</Link>}
        </div>
      </header>

      <div className="grupo filtros-tetos">
        <select className="input" aria-label="Ano" value={ano} onChange={(e) => mudar({ ano: e.target.value, mes: undefined })}>
          {anos.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <select className="input" aria-label="Mês" value={mes} onChange={(e) => mudar({ mes: e.target.value })}>
          {MESES_LONGOS.map((m, i) => (
            <option key={m} value={i + 1} disabled={ano === hoje.getFullYear() && i > hoje.getMonth()}>{m}</option>
          ))}
        </select>
        <span className="texto-suave">Cartões até {dataBr(ind.data.referencia)}</span>
      </div>

      <section className="medidores-detalhe">
        <div className="cartao">
          <div className="cartao-teto-topo"><h3>Dia {dataBr(ind.data.referencia)}</h3><SeloSituacao situacao={r.dia.situacao} /></div>
          <Medidor titulo="Gasto do dia" consumo={r.dia} unidade={u} />
        </div>
        <div className="cartao">
          <div className="cartao-teto-topo"><h3>{nomeMes}</h3><SeloSituacao situacao={r.mes.situacao} /></div>
          <Medidor titulo="Gasto do mês" consumo={r.mes} unidade={u} ritmo={r.mes.teto_ate_hoje}
            rodape={<span className={r.mes.projecao_estoura ? "texto-alerta" : "texto-suave"}>
              Esperado até {dataBr(ind.data.referencia)}: {valorTeto(r.mes.teto_ate_hoje, u)} · no ritmo atual:{" "}
              {valorTeto(r.mes.projecao, u)}</span>} />
        </div>
        <div className="cartao">
          <div className="cartao-teto-topo"><h3>Ano de {ano}</h3><SeloSituacao situacao={r.ano.situacao} /></div>
          <Medidor titulo="Gasto do ano" consumo={r.ano} unidade={u} />
        </div>
      </section>

      <div className="abas abas-3" role="tablist" aria-label="Indicadores"
        style={{ "--i": (Object.keys(ABAS) as Aba[]).indexOf(aba) } as CSSProperties}>
        {(Object.keys(ABAS) as Aba[]).map((chave) => (
          <button key={chave} type="button" role="tab" aria-selected={aba === chave} className={`aba ${aba === chave ? "ativa" : ""}`}
            onClick={() => mudar({ aba: chave === "diario" ? undefined : chave })}>
            {chave === "anual" ? <CalendarRange size={16} /> : <CalendarDays size={16} />} {ABAS[chave]}
          </button>
        ))}
      </div>

      {aba === "diario" && (
        <>
          <CartaoGrafico titulo={`Gasto por dia · ${nomeMes}`} subtitulo="O traço é o teto de cada dia; a barra vermelha passou dele."
            tabela={<TabelaMini cabecalho={["Dia", "Gasto", "Teto", "Acumulado", "Teto acumulado"]}
              linhas={ind.data.diario.map((p) => [dataBr(p.data), valorTeto(p.gasto, u), valorTeto(p.teto, u),
                valorTeto(p.acumulado, u), valorTeto(p.teto_acumulado, u)])} />}>
            <BarrasTeto unidade={u} pontos={ind.data.diario.map((p) => ({
              rotulo: String(Number(p.data.slice(8))), titulo: dataBr(p.data), gasto: p.gasto, teto: p.teto }))} />
          </CartaoGrafico>
          <CartaoGrafico titulo="Acumulado no mês" subtitulo="Quanto já foi gasto, dia a dia, contra o teto acumulado até o mesmo dia."
            series={[{ nome: "Gasto acumulado", cor: "var(--serie-1)" }, { nome: "Teto acumulado", cor: "var(--serie-2)" }]} legendaLinha
            tabela={<TabelaMini cabecalho={["Dia", "Gasto acumulado", "Teto acumulado"]}
              linhas={ind.data.diario.map((p) => [dataBr(p.data), valorTeto(p.acumulado, u), valorTeto(p.teto_acumulado, u)])} />}>
            <LinhasTempo rotulos={ind.data.diario.map((p) => String(Number(p.data.slice(8))))}
              dados={[ind.data.diario.map((p) => p.acumulado), ind.data.diario.map((p) => p.teto_acumulado)]}
              series={[{ nome: "Gasto acumulado", cor: "var(--serie-1)" }, { nome: "Teto acumulado", cor: "var(--serie-2)" }]} />
          </CartaoGrafico>
        </>
      )}
      {aba === "mensal" && (
        <CartaoGrafico titulo={`Gasto por mês · ${ano}`} subtitulo="Cada barra é um mês; o traço é o teto do mês."
          tabela={<TabelaMini cabecalho={["Mês", "Gasto", "Teto", "% do teto"]}
            linhas={ind.data.mensal.map((p) => [MESES_LONGOS[p.mes - 1], valorTeto(p.gasto, u), valorTeto(p.teto, u),
              percentualTeto(p.teto > 0 ? Math.round((p.gasto / p.teto) * 1000) / 10 : null)])} />}>
          <BarrasTeto unidade={u} pontos={ind.data.mensal.map((p) => ({
            rotulo: MESES[p.mes - 1], titulo: `${MESES_LONGOS[p.mes - 1]} de ${ano}`, gasto: p.gasto, teto: p.teto }))} />
        </CartaoGrafico>
      )}
      {aba === "anual" && (
        <CartaoGrafico titulo="Gasto por ano" subtitulo="Cada barra é um ano; o traço é o teto do ano."
          tabela={<TabelaMini cabecalho={["Ano", "Gasto", "Teto", "% do teto"]}
            linhas={ind.data.anual.map((p) => [String(p.ano), valorTeto(p.gasto, u), valorTeto(p.teto, u),
              percentualTeto(p.teto > 0 ? Math.round((p.gasto / p.teto) * 1000) / 10 : null)])} />}>
          <BarrasTeto unidade={u} pontos={ind.data.anual.map((p) => ({
            rotulo: String(p.ano), titulo: String(p.ano), gasto: p.gasto, teto: p.teto }))} />
        </CartaoGrafico>
      )}

      <section className="painel-bloco">
        <div className="bloco-topo">
          <div>
            <h2><History size={18} aria-hidden /> Valores do teto</h2>
            <small className="texto-suave">Cada valor vale a partir da data dele; o primeiro vale também para trás.</small>
          </div>
        </div>
        <ul className="vigencias">
          {t.vigencias.map((v) => (
            <li key={v.id}>
              <strong>{valorTeto(v.valor, u)} {ROTULO_PERIODO[v.periodo]}</strong>
              <span className="texto-suave"> · {NOME_PERIODO[v.periodo]} · a partir de {dataBr(v.inicio)}</span>
              <small className="texto-suave">
                Definido por {v.criado_por?.nome ?? "—"} em {dataHora(v.criado_em)}{v.motivo ? ` · ${v.motivo}` : ""}
              </small>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
