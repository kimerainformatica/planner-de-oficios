import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Flame, ListPlus } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { listarSetores, painelTetos } from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { Carregando, ErroBox } from "../../components/ui";
import type { IndicadorTipo } from "../../types";
import { data as dataBr, hojeIso } from "../../utils/formato";
import { MESES_LONGOS, ROTULO_PERIODO, valorTeto } from "../../utils/tetos";
import { Medidor, SeloSituacao } from "./comum";

/** Painel do Controle de Tetos: cada tipo do setor com o consumo do dia, do mês e do ano. */
export function PainelTetos() {
  const { usuario, ehAdminNo } = useAuth();
  const admin = ehAdminNo("TETOS");
  const meuSetor = usuario?.modulos.find((a) => a.modulo === "TETOS")?.setor_nome;
  const [params, setParams] = useSearchParams();
  const setorId = params.get("setor") ? Number(params.get("setor")) : undefined;
  const data = params.get("data") ?? undefined;
  const mudar = (chave: string, valor?: string) => {
    const p = new URLSearchParams(params);
    if (valor) p.set(chave, valor);
    else p.delete(chave);
    setParams(p, { replace: true });
  };

  const setores = useQuery({ queryKey: ["setores-tetos"], queryFn: listarSetores, enabled: admin });
  const painel = useQuery({
    queryKey: ["tetos-painel", setorId, data], queryFn: () => painelTetos({ setor_id: setorId, data }),
    placeholderData: keepPreviousData, enabled: admin || !!meuSetor,
  });

  if (!admin && !meuSetor) {
    return (
      <>
        <header className="pagina-topo"><div><h1>Controle de Tetos</h1></div></header>
        <div className="aviso-vazio" role="status">
          Seu usuário ainda não está ligado a um setor. Peça ao administrador do Controle de Tetos para escolher o seu
          setor na tela de usuários.
        </div>
      </>
    );
  }

  const ref = painel.data ? new Date(`${painel.data.referencia}T12:00:00`) : new Date();
  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Controle de Tetos</h1>
          <p className="texto-suave">
            {admin ? "Todos os setores" : `Setor ${meuSetor}`} · consumo até {dataBr(painel.data?.referencia ?? hojeIso())}
          </p>
        </div>
        <Link to="/tetos/lancamentos?novo=1" className="btn btn-primario"><ListPlus size={18} /> Lançar gasto</Link>
      </header>

      <div className="grupo filtros-tetos">
        {admin && (
          <select className="input" aria-label="Setor" value={setorId ?? ""} onChange={(e) => mudar("setor", e.target.value || undefined)}>
            <option value="">Todos os setores</option>
            {(setores.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
          </select>
        )}
        <label className="campo-inline">
          <span className="texto-suave">Consumo até</span>
          <input type="date" className="input" max={hojeIso()} value={data ?? hojeIso()}
            onChange={(e) => mudar("data", e.target.value && e.target.value !== hojeIso() ? e.target.value : undefined)} />
        </label>
      </div>

      {painel.isPending ? <Carregando /> : painel.isError ? <ErroBox erro={painel.error} /> : (
        <>
          {(painel.data.estourados > 0 || painel.data.em_atencao > 0) && (
            <div className="resumo-tetos" role="status">
              {painel.data.estourados > 0 && (
                <span className="selo-teto selo-teto-CRITICO"><Flame size={15} aria-hidden />
                  {painel.data.estourados} tipo(s) acima do teto em {MESES_LONGOS[ref.getMonth()]}</span>
              )}
              {painel.data.em_atencao > 0 && (
                <span className="selo-teto selo-teto-ATENCAO"><AlertTriangle size={15} aria-hidden />
                  {painel.data.em_atencao} perto do teto ou com projeção acima dele</span>
              )}
            </div>
          )}

          {painel.data.setores.length === 0 ? (
            <div className="aviso-vazio" role="status">
              {admin
                ? <>Nenhum tipo de teto ativo ainda. Crie o primeiro em <Link to="/tetos/tipos">Tipos de teto</Link>.</>
                : "O administrador ainda não definiu os tetos do seu setor."}
            </div>
          ) : painel.data.setores.map((s) => (
            <section key={s.setor.id} className="setor-tetos">
              {(admin || painel.data.setores.length > 1) && (
                <div className="setor-tetos-topo">
                  <h2>{s.setor.nome}</h2>
                  <div className="totais-tetos">
                    {s.totais.map((t) => (
                      <span key={t.unidade} className="texto-suave">
                        Mês: <strong>{valorTeto(t.mes.gasto, t.unidade)}</strong> de {valorTeto(t.mes.teto, t.unidade)} ·
                        Ano: <strong>{valorTeto(t.ano.gasto, t.unidade)}</strong> de {valorTeto(t.ano.teto, t.unidade)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="grade-tetos">
                {s.tipos.map((i) => <CartaoTipo key={i.tipo.id} i={i} />)}
              </div>
            </section>
          ))}
        </>
      )}
    </>
  );
}

function CartaoTipo({ i }: { i: IndicadorTipo }) {
  const u = i.tipo.unidade;
  return (
    <article className="cartao cartao-teto">
      <div className="cartao-teto-topo">
        <div>
          <h3>{i.tipo.nome}</h3>
          <small className="texto-suave">
            Teto: {i.tipo.valor !== null && i.tipo.periodo ? `${valorTeto(i.tipo.valor, u)} ${ROTULO_PERIODO[i.tipo.periodo]}` : "não definido"}
          </small>
        </div>
        <SeloSituacao situacao={i.mes.situacao} />
      </div>
      <Medidor titulo="Mês" consumo={i.mes} unidade={u} ritmo={i.mes.teto_ate_hoje}
        rodape={
          <span className={i.mes.projecao_estoura ? "texto-alerta" : "texto-suave"}>
            No ritmo atual: {valorTeto(i.mes.projecao, u)} no mês{i.mes.projecao_estoura ? " (acima do teto)" : ""}
          </span>
        } />
      <div className="medidores-menores">
        <Medidor titulo="Hoje" consumo={i.dia} unidade={u} />
        <Medidor titulo="Ano" consumo={i.ano} unidade={u} />
      </div>
      <Link to={`/tetos/tipo/${i.tipo.id}`} className="link cartao-teto-link">
        Ver indicadores <ArrowRight size={15} aria-hidden />
      </Link>
    </article>
  );
}
