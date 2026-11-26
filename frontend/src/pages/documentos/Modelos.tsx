import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, Pencil, Plus, Power, Trash2 } from "lucide-react";
import { useState } from "react";
import { atualizarModelo, criarModelo, excluirModelo, listarModelos, previaModelo } from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type { EstruturaDocumento, FormaAssinatura, ModeloDocumento, ModeloEntrada } from "../../types";
import { abrirEmNovaAba, ROTULO_ESTRUTURA, ROTULO_FORMA } from "./comum";

const ANO = new Date().getFullYear();
const NOVO: ModeloEntrada = {
  nome: "", descricao: "", estrutura: "SIMPLES", digitos: 2, recuo_cm: 1.25, forma_assinatura: "APP",
  mostrar_assunto: true, data_no_fim: false, rotulo_ident: "Matrícula", vocativo: "", fecho: "Atenciosamente,",
  texto_modelo: "", ativo: true,
};

function paraEntrada(m: ModeloDocumento): ModeloEntrada {
  return {
    nome: m.nome, descricao: m.descricao ?? "", estrutura: m.estrutura, digitos: m.digitos, recuo_cm: m.recuo_cm,
    forma_assinatura: m.forma_assinatura, mostrar_assunto: m.mostrar_assunto, data_no_fim: m.data_no_fim,
    rotulo_ident: m.rotulo_ident, vocativo: m.vocativo, fecho: m.fecho, texto_modelo: m.texto_modelo, ativo: m.ativo,
  };
}

const exemploNumero = (digitos: number) => `${"1".padStart(digitos, "0")}/${ANO}`;

/** Modelos de documento da instituição (só o administrador do módulo Documentos). */
export function Modelos() {
  const qc = useQueryClient();
  const avisar = useToast();
  const consulta = useQuery({ queryKey: ["modelos-documento"], queryFn: listarModelos });
  const [editando, setEditando] = useState<ModeloDocumento | "novo" | null>(null);
  const depois = () => {
    qc.invalidateQueries({ queryKey: ["modelos-documento"] });
    qc.invalidateQueries({ queryKey: ["documento"] });
  };
  const alternar = useMutation({
    mutationFn: (m: ModeloDocumento) => atualizarModelo(m.codigo, { ativo: !m.ativo }),
    onSuccess: (m) => { depois(); avisar(`${m.nome} ${m.ativo ? "reativado" : "desativado"}.`); },
    onError: (e) => avisar(e.message, "erro"),
  });
  const apagar = useMutation({
    mutationFn: (m: ModeloDocumento) => excluirModelo(m.codigo),
    onSuccess: () => { depois(); avisar("Modelo apagado."); },
    onError: (e) => avisar(e.message, "erro"),
  });

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Modelos de documento</h1>
          <p className="texto-suave">
            Os modelos que a instituição já usa: declaração, relatório, ata, termo, circular… Todos saem no timbrado da
            unidade, com as mesmas fontes e margens. O modelo define o cabeçalho, a numeração, o recuo, os textos com que
            o rascunho começa e a assinatura sugerida. Mudar um modelo não muda os documentos já emitidos.
          </p>
        </div>
        <Botao onClick={() => setEditando("novo")}><Plus size={18} /> Novo modelo</Botao>
      </header>

      {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : (
        <div className="tabela-box">
          <table className="tabela tabela-modelos">
            <thead>
              <tr>
                <th>Modelo</th>
                <th>Cabeçalho</th>
                <th>Numeração</th>
                <th>Assinatura sugerida</th>
                <th className="num">Documentos</th>
                <th>Situação</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {consulta.data.map((m) => (
                <tr key={m.codigo} className={m.ativo ? "" : "linha-inativa"}>
                  <td>
                    <strong>{m.nome}</strong>
                    {m.sistema && <span className="selo-doc selo-doc-NEUTRO selo-sistema">Vem com o sistema</span>}
                    {m.descricao && <small className="celula-sub">{m.descricao}</small>}
                  </td>
                  <td>{ROTULO_ESTRUTURA[m.estrutura].nome}</td>
                  <td className="sem-quebra">{exemploNumero(m.digitos)}</td>
                  <td>{ROTULO_FORMA[m.forma_assinatura]}</td>
                  <td className="num">{m.em_uso}</td>
                  <td>{m.ativo ? "Ativo" : "Desativado"}</td>
                  <td>
                    <span className="grupo grupo-justo">
                      <button className="btn-icone" aria-label={`Editar ${m.nome}`} title="Editar" onClick={() => setEditando(m)}>
                        <Pencil size={15} />
                      </button>
                      {!m.sistema && (
                        <button className="btn-icone" aria-label={`${m.ativo ? "Desativar" : "Reativar"} ${m.nome}`}
                          title={m.ativo ? "Desativar" : "Reativar"} disabled={alternar.isPending} onClick={() => alternar.mutate(m)}>
                          <Power size={15} />
                        </button>
                      )}
                      {!m.sistema && m.em_uso === 0 && (
                        <button className="btn-icone btn-perigo" aria-label={`Apagar ${m.nome}`} title="Apagar" disabled={apagar.isPending}
                          onClick={() => { if (confirm(`Apagar o modelo ${m.nome}? Ele nunca foi usado.`)) apagar.mutate(m); }}>
                          <Trash2 size={15} />
                        </button>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <ModalModelo modelo={editando === "novo" ? null : editando} aoFechar={() => setEditando(null)}
          aoSalvar={(m) => { depois(); avisar(`Modelo ${m.nome} salvo.`); setEditando(null); }} />
      )}
    </>
  );
}

function ModalModelo({ modelo, aoFechar, aoSalvar }: {
  modelo: ModeloDocumento | null; aoFechar: () => void; aoSalvar: (m: ModeloDocumento) => void;
}) {
  const avisar = useToast();
  const [f, setF] = useState<ModeloEntrada>(() => (modelo ? paraEntrada(modelo) : NOVO));
  const [vendo, setVendo] = useState(false);
  const muda = <K extends keyof ModeloEntrada>(campo: K) => (valor: ModeloEntrada[K]) => setF((a) => ({ ...a, [campo]: valor }));
  const sistema = modelo?.sistema ?? false;
  const limpo = (): ModeloEntrada => ({ ...f, nome: f.nome.trim(), descricao: f.descricao?.trim() || null });
  const salvar = useMutation({
    mutationFn: () => (modelo ? atualizarModelo(modelo.codigo, limpo()) : criarModelo(limpo())),
    onSuccess: aoSalvar,
  });

  async function verExemplo() {
    setVendo(true);
    try {
      await abrirEmNovaAba(() => previaModelo(limpo()));
    } catch (e) {
      avisar((e as Error).message, "erro");
    } finally {
      setVendo(false);
    }
  }

  return (
    <Modal titulo={modelo ? `Modelo: ${modelo.nome}` : "Novo modelo de documento"} aoFechar={aoFechar}>
      <form className="formulario form-modelo" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <div className="grade-2">
          <Campo rotulo="Nome *">
            {(i) => <input id={i} className="input" required minLength={2} maxLength={80} value={f.nome}
              placeholder="Ex.: Declaração" onChange={(e) => muda("nome")(e.target.value)} />}
          </Campo>
          <Campo rotulo="Descrição" dica="Aparece na escolha do modelo, ao começar um documento.">
            {(i) => <input id={i} className="input" maxLength={300} value={f.descricao ?? ""}
              onChange={(e) => muda("descricao")(e.target.value)} />}
          </Campo>
        </div>

        <fieldset className="opcoes-forma" disabled={sistema}>
          <legend>Cabeçalho{sistema && <small className="texto-suave"> (fixo no ofício e no memorando)</small>}</legend>
          {(Object.keys(ROTULO_ESTRUTURA) as EstruturaDocumento[]).map((e) => (
            <label key={e} className={`opcao-forma ${f.estrutura === e ? "ativa" : ""}`}>
              <input type="radio" name="estrutura" checked={f.estrutura === e} onChange={() => muda("estrutura")(e)} />
              <span>
                <strong>{ROTULO_ESTRUTURA[e].nome}</strong>
                <small className="texto-suave">{ROTULO_ESTRUTURA[e].texto}</small>
              </span>
            </label>
          ))}
        </fieldset>

        <div className="grade-3">
          <Campo rotulo="Numeração" dica={sistema ? "A do ofício segue o Planner de Ofícios." : "Sequência por pessoa, modelo e ano."}>
            {(i) => (
              <select id={i} className="input" value={f.digitos} disabled={sistema}
                onChange={(e) => muda("digitos")(Number(e.target.value))}>
                {[2, 3, 4].map((n) => <option key={n} value={n}>{exemploNumero(n)}</option>)}
              </select>
            )}
          </Campo>
          <Campo rotulo="Recuo do parágrafo (cm)">
            {(i) => <input id={i} className="input" type="number" min={0} max={5} step={0.05} value={f.recuo_cm}
              onChange={(e) => muda("recuo_cm")(Number(e.target.value))} />}
          </Campo>
          <Campo rotulo="Assinatura sugerida" dica="Quem redige pode trocar em cada documento.">
            {(i) => (
              <select id={i} className="input" value={f.forma_assinatura}
                onChange={(e) => muda("forma_assinatura")(e.target.value as FormaAssinatura)}>
                {(Object.keys(ROTULO_FORMA) as FormaAssinatura[]).map((forma) => <option key={forma} value={forma}>{ROTULO_FORMA[forma]}</option>)}
              </select>
            )}
          </Campo>
        </div>

        <div className="grupo opcoes-modelo">
          <label className="checkbox">
            <input type="checkbox" checked={f.mostrar_assunto} onChange={(e) => muda("mostrar_assunto")(e.target.checked)} />
            Imprimir a linha “Assunto:”
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={f.data_no_fim} onChange={(e) => muda("data_no_fim")(e.target.checked)} />
            Local e data no fim, antes da assinatura
          </label>
          {!sistema && (
            <label className="checkbox">
              <input type="checkbox" checked={f.ativo} onChange={(e) => muda("ativo")(e.target.checked)} />
              Ativo (aparece para quem redige)
            </label>
          )}
        </div>

        <div className="grade-3">
          <Campo rotulo="Vocativo" dica="Ex.: Prezado(a) Senhor(a),">
            {(i) => <input id={i} className="input" maxLength={160} value={f.vocativo} onChange={(e) => muda("vocativo")(e.target.value)} />}
          </Campo>
          <Campo rotulo="Fecho" dica="Ex.: Atenciosamente,">
            {(i) => <input id={i} className="input" maxLength={120} value={f.fecho} onChange={(e) => muda("fecho")(e.target.value)} />}
          </Campo>
          <Campo rotulo="Rótulo da matrícula" dica="Sai antes do número, na assinatura.">
            {(i) => <input id={i} className="input" maxLength={30} value={f.rotulo_ident} onChange={(e) => muda("rotulo_ident")(e.target.value)} />}
          </Campo>
        </div>

        <Campo rotulo="Texto do modelo"
          dica="O texto com que o rascunho começa. Deixe marcas como [NOME] para quem redige completar. Uma linha que começa com “# ” vira título de seção, e com “- ”, item de lista.">
          {(i) => <textarea id={i} className="input texto-documento" rows={10} maxLength={30000} value={f.texto_modelo}
            onChange={(e) => muda("texto_modelo")(e.target.value)} />}
        </Campo>

        {salvar.isError && <div className="alerta-erro" role="alert">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
          <Botao type="button" className="btn btn-secundario" carregando={vendo} disabled={f.nome.trim().length < 2}
            onClick={verExemplo}>
            <Eye size={16} /> Ver exemplo em PDF
          </Botao>
          <Botao type="submit" carregando={salvar.isPending}>Salvar</Botao>
        </div>
      </form>
    </Modal>
  );
}
