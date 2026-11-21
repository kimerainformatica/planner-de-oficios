import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, ListPlus, Pencil, Search, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import {
  anexarComprovante, baixarComprovante, corrigirGasto, excluirGasto, lancarGasto, listarGastos, listarSetores,
  listarTiposTeto,
} from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { SeletorArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal, Paginacao } from "../../components/ui";
import type { GastoTeto } from "../../types";
import { salvarArquivo } from "../../utils/arquivo";
import { data as dataBr, dataHora, hojeIso } from "../../utils/formato";
import { lerValor, primeiroDoMes, valorParaCampo, valorTeto } from "../../utils/tetos";

const POR_PAGINA = 50;

export function Lancamentos() {
  const { ehAdminNo } = useAuth();
  const admin = ehAdminNo("TETOS");
  const [params, setParams] = useSearchParams();
  const setorId = params.get("setor") ? Number(params.get("setor")) : undefined;
  const tipoId = params.get("tipo") ? Number(params.get("tipo")) : undefined;
  const de = params.get("de") ?? primeiroDoMes();
  const ate = params.get("ate") ?? hojeIso();
  const busca = params.get("busca") ?? "";
  const pagina = Number(params.get("pagina") ?? 1);
  const [texto, setTexto] = useState(busca);
  const [editando, setEditando] = useState<GastoTeto | null>(null);
  const [excluindo, setExcluindo] = useState<GastoTeto | null>(null);
  const novo = params.get("novo") === "1";

  const mudar = (novos: Record<string, string | undefined>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(novos)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    if (!("pagina" in novos)) p.delete("pagina");
    setParams(p, { replace: true });
  };

  const setores = useQuery({ queryKey: ["setores-tetos"], queryFn: listarSetores, enabled: admin });
  const tipos = useQuery({ queryKey: ["tipos-teto", "todos"], queryFn: () => listarTiposTeto({ incluir_inativos: true }) });
  const filtros = { setor_id: setorId, tipo_id: tipoId, de, ate, busca: busca || undefined, pagina, por_pagina: POR_PAGINA };
  const lista = useQuery({ queryKey: ["tetos-gastos", filtros], queryFn: () => listarGastos(filtros), placeholderData: keepPreviousData });
  const tiposDoFiltro = (tipos.data ?? []).filter((t) => !setorId || t.setor.id === setorId);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Lançamentos</h1>
          <p className="texto-suave">Os gastos de cada tipo de teto, com o comprovante quando houver.</p>
        </div>
        <button className="btn btn-primario" onClick={() => mudar({ novo: "1" })}><ListPlus size={18} /> Lançar gasto</button>
      </header>

      <form className="grupo filtros-tetos" onSubmit={(e) => { e.preventDefault(); mudar({ busca: texto.trim() || undefined }); }}>
        {admin && (
          <select className="input" aria-label="Setor" value={setorId ?? ""}
            onChange={(e) => mudar({ setor: e.target.value || undefined, tipo: undefined })}>
            <option value="">Todos os setores</option>
            {(setores.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
          </select>
        )}
        <select className="input" aria-label="Tipo de teto" value={tipoId ?? ""} onChange={(e) => mudar({ tipo: e.target.value || undefined })}>
          <option value="">Todos os tipos</option>
          {tiposDoFiltro.map((t) => <option key={t.id} value={t.id}>{admin && !setorId ? `${t.setor.nome} · ` : ""}{t.nome}</option>)}
        </select>
        <label className="campo-inline"><span className="texto-suave">De</span>
          <input type="date" className="input" value={de} max={ate} onChange={(e) => mudar({ de: e.target.value || undefined })} /></label>
        <label className="campo-inline"><span className="texto-suave">até</span>
          <input type="date" className="input" value={ate} min={de} onChange={(e) => mudar({ ate: e.target.value || undefined })} /></label>
        <div className="busca-tetos">
          <Search size={16} aria-hidden />
          <input className="input" placeholder="Descrição ou nº do documento" aria-label="Buscar" value={texto}
            onChange={(e) => setTexto(e.target.value)} />
        </div>
      </form>

      {lista.isPending ? <Carregando /> : lista.isError ? <ErroBox erro={lista.error} /> : (
        <>
          {lista.data.totais.length > 0 && (
            <div className="totais-lancamentos">
              {lista.data.totais.map((t) => (
                <span key={t.tipo.id} className="cartao total-tipo">
                  <small className="texto-suave">{t.tipo.nome} · {t.quantidade} lançamento(s)</small>
                  <strong>{valorTeto(t.total, t.tipo.unidade)}</strong>
                </span>
              ))}
            </div>
          )}
          {lista.data.itens.length === 0 ? (
            <div className="aviso-vazio" role="status">Nenhum lançamento no período escolhido.</div>
          ) : (
            <div className="tabela-box">
              <table className="tabela tabela-tetos">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Tipo</th>
                    <th>Descrição</th>
                    <th className="num">Valor</th>
                    <th>Comprovante</th>
                    <th>Lançado por</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {lista.data.itens.map((g) => (
                    <tr key={g.id}>
                      <td>{dataBr(g.data)}</td>
                      <td>{g.tipo.nome}{admin && <small className="texto-suave"><br />{g.setor.nome}</small>}</td>
                      <td>{g.descricao}{g.documento && <small className="texto-suave"><br />Doc. {g.documento}</small>}</td>
                      <td className="num"><strong>{valorTeto(g.valor, g.tipo.unidade)}</strong></td>
                      <td>{g.arquivo_nome ? <BotaoComprovante g={g} /> : <span className="texto-suave">—</span>}</td>
                      <td>
                        {g.registrado_por?.nome ?? "—"}
                        <small className="texto-suave"><br />{dataHora(g.registrado_em)}
                          {g.atualizado_em && ` · corrigido por ${g.atualizado_por?.nome ?? "—"}`}</small>
                      </td>
                      <td className="num">
                        {g.pode_editar && (
                          <div className="grupo grupo-fim acoes-linha">
                            <button className="btn btn-fantasma btn-pequeno" onClick={() => setEditando(g)} title="Corrigir"
                              aria-label={`Corrigir o lançamento de ${dataBr(g.data)}`}>
                              <Pencil size={15} />
                            </button>
                            <button className="btn btn-fantasma btn-pequeno btn-perigo" onClick={() => setExcluindo(g)} title="Excluir"
                              aria-label={`Excluir o lançamento de ${dataBr(g.data)}`}>
                              <Trash2 size={15} />
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Paginacao pagina={pagina} total={lista.data.total} porPagina={POR_PAGINA} aoMudar={(p) => mudar({ pagina: String(p) })} />
        </>
      )}

      {(novo || editando) && (
        <ModalLancamento gasto={editando} tipoInicial={tipoId} aoFechar={() => { setEditando(null); if (novo) mudar({ novo: undefined }); }} />
      )}
      {excluindo && <ModalExcluir gasto={excluindo} aoFechar={() => setExcluindo(null)} />}
    </>
  );
}

function BotaoComprovante({ g }: { g: GastoTeto }) {
  const baixar = useMutation({ mutationFn: () => baixarComprovante(g), onSuccess: (blob) => salvarArquivo(blob, g.arquivo_nome ?? "comprovante") });
  return (
    <button type="button" className="btn btn-fantasma btn-pequeno" onClick={() => baixar.mutate()} disabled={baixar.isPending}
      title={g.arquivo_nome ?? undefined}>
      <Download size={15} /> {g.arquivo_nome && g.arquivo_nome.length > 18 ? `${g.arquivo_nome.slice(0, 16)}…` : g.arquivo_nome}
    </button>
  );
}

function ModalLancamento({ gasto, tipoInicial, aoFechar }: { gasto: GastoTeto | null; tipoInicial?: number; aoFechar: () => void }) {
  const avisar = useToast();
  const qc = useQueryClient();
  const tipos = useQuery({ queryKey: ["tipos-teto", "ativos"], queryFn: () => listarTiposTeto() });
  const { ehAdminNo } = useAuth();
  const admin = ehAdminNo("TETOS");
  const [tipoId, setTipoId] = useState<number | "">(gasto?.tipo.id ?? tipoInicial ?? "");
  const [dia, setDia] = useState(gasto?.data ?? hojeIso());
  const [valor, setValor] = useState(gasto ? valorParaCampo(gasto.valor) : "");
  const [descricao, setDescricao] = useState(gasto?.descricao ?? "");
  const [documento, setDocumento] = useState(gasto?.documento ?? "");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const escolhido = (tipos.data ?? []).find((t) => t.id === tipoId);
  const unidade = escolhido?.unidade ?? gasto?.tipo.unidade ?? "R$";

  const salvar = useMutation({
    mutationFn: async () => {
      const numero = lerValor(valor);
      if (!numero) throw new Error("Informe um valor maior que zero, com até duas casas decimais (ex.: 1.234,56).");
      if (!gasto) {
        return lancarGasto({ tipo_id: Number(tipoId), data: dia, valor: numero, descricao: descricao.trim(),
          documento: documento.trim() || undefined, arquivo });
      }
      const mudou = {
        ...(tipoId !== gasto.tipo.id ? { tipo_id: Number(tipoId) } : {}),
        ...(dia !== gasto.data ? { data: dia } : {}),
        ...(Number(numero) !== gasto.valor ? { valor: numero } : {}),
        ...(descricao.trim() !== gasto.descricao ? { descricao: descricao.trim() } : {}),
        ...(documento.trim() !== (gasto.documento ?? "") ? { documento: documento.trim() || null } : {}),
      };
      let atualizado = gasto;
      if (Object.keys(mudou).length) atualizado = await corrigirGasto(gasto.id, mudou);
      if (arquivo) atualizado = await anexarComprovante(gasto.id, arquivo);
      if (!Object.keys(mudou).length && !arquivo) throw new Error("Nada foi alterado.");
      return atualizado;
    },
    onSuccess: (g) => {
      qc.invalidateQueries({ queryKey: ["tetos-gastos"] });
      qc.invalidateQueries({ queryKey: ["tetos-painel"] });
      qc.invalidateQueries({ queryKey: ["tetos-indicadores"] });
      avisar(gasto ? "Lançamento corrigido." : `Gasto de ${valorTeto(g.valor, g.tipo.unidade)} lançado em ${g.tipo.nome}.`);
      aoFechar();
    },
    onError: (e: Error) => setErro(e.message),
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    salvar.mutate();
  }

  return (
    <Modal titulo={gasto ? "Corrigir lançamento" : "Lançar gasto"} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={enviar}>
        <Campo rotulo="Tipo de teto *">
          {(id) => (
            <select id={id} className="input" required value={tipoId} autoFocus={!gasto}
              onChange={(e) => setTipoId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Selecione…</option>
              {(tipos.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>{admin ? `${t.setor.nome} · ` : ""}{t.nome} ({t.unidade})</option>
              ))}
              {gasto && !(tipos.data ?? []).some((t) => t.id === gasto.tipo.id) && (
                <option value={gasto.tipo.id}>{gasto.tipo.nome} (desativado)</option>
              )}
            </select>
          )}
        </Campo>
        <div className="grade-2">
          <Campo rotulo="Data do gasto *">
            {(id) => <input id={id} type="date" className="input" required max={hojeIso()} value={dia} onChange={(e) => setDia(e.target.value)} />}
          </Campo>
          <Campo rotulo={`Valor (${unidade}) *`} dica={unidade === "R$" ? "Ex.: 1.234,56" : `Quantidade em ${unidade}`}>
            {(id) => <input id={id} className="input" required inputMode="decimal" value={valor} onChange={(e) => setValor(e.target.value)} />}
          </Campo>
        </div>
        <Campo rotulo="Descrição *" dica="O que foi comprado ou consumido.">
          {(id) => <input id={id} className="input" required minLength={2} maxLength={300} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        <Campo rotulo="Documento" dica="Opcional: nº da nota fiscal, requisição ou pedido.">
          {(id) => <input id={id} className="input" maxLength={60} value={documento} onChange={(e) => setDocumento(e.target.value)} />}
        </Campo>
        <div className="campo">
          <span className="rotulo">Comprovante</span>
          <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo} compacto
            rotulo={gasto?.arquivo_nome ? `Substituir o comprovante (${gasto.arquivo_nome})` : "Anexar comprovante (opcional)"} />
        </div>
        {erro && <div className="alerta-erro">{erro}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>{gasto ? "Salvar correção" : "Lançar"}</Botao>
        </div>
      </form>
    </Modal>
  );
}

function ModalExcluir({ gasto, aoFechar }: { gasto: GastoTeto; aoFechar: () => void }) {
  const avisar = useToast();
  const qc = useQueryClient();
  const excluir = useMutation({
    mutationFn: () => excluirGasto(gasto.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tetos-gastos"] });
      qc.invalidateQueries({ queryKey: ["tetos-painel"] });
      qc.invalidateQueries({ queryKey: ["tetos-indicadores"] });
      avisar("Lançamento excluído.");
      aoFechar();
    },
  });
  return (
    <Modal titulo="Excluir lançamento" aoFechar={aoFechar}>
      <p>
        Excluir o gasto de <strong>{valorTeto(gasto.valor, gasto.tipo.unidade)}</strong> em {dataBr(gasto.data)} ({gasto.descricao})?
        A exclusão fica registrada nas atividades{gasto.arquivo_nome ? " e o comprovante é apagado" : ""}.
      </p>
      {excluir.isError && <div className="alerta-erro">{excluir.error.message}</div>}
      <div className="acoes-form">
        <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
        <Botao className="btn btn-perigo" carregando={excluir.isPending} onClick={() => excluir.mutate()}>Excluir</Botao>
      </div>
    </Modal>
  );
}
