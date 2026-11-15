import { useMutation } from "@tanstack/react-query";
import {
  CalendarClock, ChevronDown, ChevronUp, ClipboardList, Download, FileUp, PencilLine, Plus, Stethoscope, X,
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import {
  anexarRelatorioExterno, baixarArquivoInteracao, baixarRelatorioPdf, criarRelatorio, editarRelatorio, editarResposta,
  responderChamado, type RelatorioForm,
} from "../../api/endpoints";
import { SeletorArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Campo } from "../../components/ui";
import type { ChamadoDetalhe as Detalhe, Interacao, RelatorioTecnico, SituacaoEquipamento } from "../../types";
import { salvarArquivo } from "../../utils/arquivo";
import { dataHora, tamanho } from "../../utils/formato";
import { agoraLocal, horas, paraInputLocal, ROTULO_EQUIPAMENTO, ROTULO_PAPEL_MANUTENCAO } from "../../utils/manutencao";
import { Dado } from "../oficio/Dados";

type Modo = "externo" | "sistema";
type CamposRelatorio = Omit<RelatorioForm, "atendido_em">;

const RELATORIO_VAZIO: CamposRelatorio = {
  equipamento: null, identificacao: null, diagnostico: "", causa: null, servico_executado: null, pecas: null,
  situacao_equipamento: "NAO_SE_APLICA", recomendacoes: null,
};

const ehTecnico = (i: Interacao) => i.tipo === "DIAGNOSTICO" || i.tipo === "RELATORIO";

/**
 * Diagnóstico técnico do chamado, tudo num lugar só: registrar (relatório externo da empresa ou relatório no modelo do
 * sistema, que também pode levar o arquivo externo), ver, editar depois (data e hora, resumo, campos do relatório,
 * substituir o arquivo) e acrescentar complementos.
 */
export function SecaoDiagnostico({ chamado, aoSalvar }: { chamado: Detalhe; aoSalvar: (c: Detalhe) => void }) {
  const [complemento, setComplemento] = useState(false);
  const registros = chamado.interacoes.filter(ehTecnico);
  const principal = registros.find((i) => i.id === chamado.diagnostico_interacao_id) ?? null;
  const complementos = registros.filter((i) => i !== principal);

  return (
    <section className="painel-bloco secao-diagnostico" id="diagnostico">
      <div className="bloco-topo">
        <div>
          <h2><Stethoscope size={20} aria-hidden /> Diagnóstico técnico</h2>
          <small className="texto-suave">
            {chamado.diagnosticado_em
              ? <>Diagnosticado em <strong>{dataHora(chamado.diagnosticado_em)}</strong>
                {chamado.prazo.horas_ate_diagnostico !== null && ` · ${horas(chamado.prazo.horas_ate_diagnostico)} após a abertura`}
                {chamado.prazo.situacao === "CUMPRIDO" ? " · dentro do prazo" : chamado.prazo.situacao === "CUMPRIDO_COM_ATRASO" ? " · com atraso" : ""}</>
              : <>Aguardando o diagnóstico da {chamado.empresa.nome} · prazo até <strong>{dataHora(chamado.prazo_em)}</strong></>}
          </small>
        </div>
        {principal && chamado.pode_responder && !complemento && (
          <button className="btn btn-secundario" onClick={() => setComplemento(true)}>
            <Plus size={17} /> Adicionar complemento
          </button>
        )}
      </div>

      {!principal && (chamado.pode_responder ? (
        <NovoRegistro chamado={chamado} aoSalvar={aoSalvar} />
      ) : (
        <p className="texto-suave">
          O técnico da empresa registra aqui o relatório externo ou o relatório no modelo do sistema. Ele aparece nesta
          seção assim que for enviado.
        </p>
      ))}

      {principal && (
        <div className="registros-tecnicos">
          <CartaoRegistro chamado={chamado} i={principal} principal aoSalvar={aoSalvar} />
          {complementos.map((i) => <CartaoRegistro key={i.id} chamado={chamado} i={i} aoSalvar={aoSalvar} />)}
        </div>
      )}

      {complemento && (
        <div className="registro-tecnico registro-novo">
          <div className="registro-topo">
            <strong>Novo complemento do diagnóstico</strong>
            <button className="btn-icone" onClick={() => setComplemento(false)} aria-label="Fechar"><X size={18} /></button>
          </div>
          <NovoRegistro chamado={chamado} complemento aoSalvar={(c) => { aoSalvar(c); setComplemento(false); }} />
        </div>
      )}
    </section>
  );
}

// ---------- registrar ----------

function NovoRegistro({ chamado, complemento = false, aoSalvar }: {
  chamado: Detalhe; complemento?: boolean; aoSalvar: (c: Detalhe) => void;
}) {
  const avisar = useToast();
  const [modo, setModo] = useState<Modo>("externo");
  const [quando, setQuando] = useState(agoraLocal());
  const [resumo, setResumo] = useState("");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [rel, setRel] = useState<CamposRelatorio>({ ...RELATORIO_VAZIO, equipamento: chamado.equipamento });
  const minimo = paraInputLocal(complemento && chamado.diagnosticado_em ? chamado.diagnosticado_em : chamado.aberto_em);

  const salvar = useMutation({
    mutationFn: async () => {
      if (modo === "externo") {
        return responderChamado(chamado.id, { diagnostico: true, diagnosticado_em: quando, texto: resumo.trim(), arquivo });
      }
      const c = await criarRelatorio(chamado.id, { ...rel, diagnostico: rel.diagnostico.trim(), atendido_em: quando });
      if (!arquivo) return c;
      // Interligado: o arquivo da empresa fica no mesmo registro do relatório do sistema
      const novo = [...c.interacoes].reverse().find((i) => i.tipo === "RELATORIO");
      return novo ? anexarRelatorioExterno(novo.id, arquivo) : c;
    },
    onSuccess: (c) => {
      aoSalvar(c);
      avisar(complemento ? "Complemento registrado." : "Diagnóstico registrado. O prazo do chamado foi encerrado.");
      setResumo("");
      setArquivo(null);
      setRel({ ...RELATORIO_VAZIO, equipamento: chamado.equipamento });
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    salvar.mutate();
  }
  const pronto = modo === "externo" ? Boolean(arquivo) : rel.diagnostico.trim().length >= 5;

  return (
    <form className="formulario form-diagnostico" onSubmit={enviar}>
      <div className="alternador" role="group" aria-label="Como registrar">
        <button type="button" className={modo === "externo" ? "ativo" : ""} onClick={() => setModo("externo")}>
          <FileUp size={15} /> Relatório externo
        </button>
        <button type="button" className={modo === "sistema" ? "ativo" : ""} onClick={() => setModo("sistema")}>
          <ClipboardList size={15} /> Relatório no modelo do sistema
        </button>
      </div>
      <p className="texto-suave">
        {modo === "externo"
          ? "Anexe o laudo, a ordem de serviço ou o relatório que a empresa emitiu. Com o arquivo, o diagnóstico fica registrado."
          : "Preencha o relatório no modelo do sistema (gera PDF). Se a empresa também emitiu um relatório próprio, anexe junto."}
      </p>

      <Campo rotulo={modo === "externo" ? "Data e hora do diagnóstico *" : "Data e hora do atendimento *"}
        dica={complemento
          ? "Não pode ser anterior ao diagnóstico."
          : "Quando o técnico diagnosticou o problema, não a hora deste registro. É ela que conta para o prazo."}>
        {(id) => <input id={id} className="input input-data-hora" type="datetime-local" required min={minimo}
          max={agoraLocal()} value={quando} onChange={(e) => setQuando(e.target.value)} />}
      </Campo>

      {modo === "externo" ? (
        <>
          <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo} rotulo="Relatório externo da empresa *" />
          <Campo rotulo="Resumo do diagnóstico" dica="Opcional. Ex.: válvula de segurança travada; troca necessária.">
            {(id) => <textarea id={id} className="input" rows={2} maxLength={10000} value={resumo}
              onChange={(e) => setResumo(e.target.value)} />}
          </Campo>
        </>
      ) : (
        <>
          <CamposDoRelatorio valor={rel} aoMudar={setRel} />
          <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo} rotulo="Anexar também o relatório externo (opcional)" compacto />
        </>
      )}

      {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
      <div className="acoes-form">
        <Botao type="submit" carregando={salvar.isPending} disabled={!pronto}>
          <Stethoscope size={16} /> {complemento ? "Registrar complemento" : "Registrar diagnóstico"}
        </Botao>
      </div>
    </form>
  );
}

function CamposDoRelatorio({ valor, aoMudar }: { valor: CamposRelatorio; aoMudar: (v: CamposRelatorio) => void }) {
  const texto = (k: keyof CamposRelatorio) => (e: { target: { value: string } }) =>
    aoMudar({ ...valor, [k]: e.target.value || null });
  const area = (k: keyof CamposRelatorio, rotulo: string, linhas: number, max: number): ReactNode => (
    <Campo rotulo={rotulo}>
      {(id) => <textarea id={id} className="input" rows={linhas} maxLength={max} value={(valor[k] as string | null) ?? ""}
        onChange={texto(k)} />}
    </Campo>
  );
  return (
    <>
      <div className="grade-2">
        <Campo rotulo="Equipamento">
          {(id) => <input id={id} className="input" maxLength={120} value={valor.equipamento ?? ""} onChange={texto("equipamento")} />}
        </Campo>
        <Campo rotulo="Patrimônio / nº de série">
          {(id) => <input id={id} className="input" maxLength={120} value={valor.identificacao ?? ""} onChange={texto("identificacao")} />}
        </Campo>
        <Campo rotulo="Situação do equipamento">
          {(id) => (
            <select id={id} className="input" value={valor.situacao_equipamento}
              onChange={(e) => aoMudar({ ...valor, situacao_equipamento: e.target.value as SituacaoEquipamento })}>
              {Object.entries(ROTULO_EQUIPAMENTO).map(([k, r]) => <option key={k} value={k}>{r}</option>)}
            </select>
          )}
        </Campo>
      </div>
      <Campo rotulo="Diagnóstico *">
        {(id) => <textarea id={id} className="input" rows={3} required minLength={5} maxLength={10000}
          value={valor.diagnostico} onChange={(e) => aoMudar({ ...valor, diagnostico: e.target.value })} />}
      </Campo>
      {area("causa", "Causa provável", 2, 5000)}
      {area("servico_executado", "Serviço executado", 3, 10000)}
      {area("pecas", "Peças e materiais", 2, 5000)}
      {area("recomendacoes", "Recomendações", 2, 5000)}
    </>
  );
}

// ---------- ver e editar ----------

function CartaoRegistro({ chamado, i, principal = false, aoSalvar }: {
  chamado: Detalhe; i: Interacao; principal?: boolean; aoSalvar: (c: Detalhe) => void;
}) {
  const [editando, setEditando] = useState(false);
  const [abrirRelatorio, setAbrirRelatorio] = useState(principal);
  const quando = i.ocorrido_em ?? i.criado_em;
  const tipo = i.relatorio ? `Relatório do sistema ${i.relatorio.codigo}` : "Relatório externo";

  return (
    <article className={`registro-tecnico ${principal ? "registro-principal" : ""}`}>
      <div className="registro-topo">
        <div className="registro-titulo">
          <span className={`badge ${principal ? "chamado-prazo-CUMPRIDO" : "prev-programada"}`}>
            {principal ? "Diagnóstico" : "Complemento"}
          </span>
          <strong>{tipo}</strong>
        </div>
        {chamado.pode_corrigir_diagnostico && !editando && (
          <button className="btn btn-fantasma btn-pequeno" onClick={() => setEditando(true)}>
            <PencilLine size={15} /> Editar
          </button>
        )}
      </div>
      <small className="registro-meta">
        <CalendarClock size={13} aria-hidden />
        {i.relatorio ? "Atendimento" : "Diagnóstico"} em <strong>{dataHora(quando)}</strong>
        {" · "}{i.autor?.nome ?? "—"}{i.autor_papel && ` (${ROTULO_PAPEL_MANUTENCAO[i.autor_papel]})`}
        {" · registrado em "}{dataHora(i.criado_em)}
      </small>

      {editando ? (
        <EditarRegistro chamado={chamado} i={i} aoFechar={() => setEditando(false)}
          aoSalvar={(c) => { aoSalvar(c); setEditando(false); }} />
      ) : (
        <>
          {!i.relatorio && i.texto && <p className="texto-livre">{i.texto}</p>}
          <div className="grupo registro-arquivos">
            {i.arquivo_nome
              ? <ArquivoExterno i={i} />
              : <small className="texto-suave">Sem relatório externo anexado.</small>}
            {i.relatorio && (
              <>
                <button className="btn btn-secundario btn-pequeno" onClick={() => setAbrirRelatorio((v) => !v)}>
                  {abrirRelatorio ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  {abrirRelatorio ? "Esconder" : "Ver"} relatório
                </button>
                <BotaoPdf relatorio={i.relatorio} />
              </>
            )}
          </div>
          {i.relatorio && abrirRelatorio && <VisaoRelatorio r={i.relatorio} />}
        </>
      )}
    </article>
  );
}

function camposDe(r: RelatorioTecnico): CamposRelatorio {
  return {
    equipamento: r.equipamento, identificacao: r.identificacao, diagnostico: r.diagnostico, causa: r.causa,
    servico_executado: r.servico_executado, pecas: r.pecas, situacao_equipamento: r.situacao_equipamento,
    recomendacoes: r.recomendacoes,
  };
}

/** Edição de um registro: data e hora, resumo ou campos do relatório e o relatório externo (substituir ou anexar). */
function EditarRegistro({ chamado, i, aoFechar, aoSalvar }: {
  chamado: Detalhe; i: Interacao; aoFechar: () => void; aoSalvar: (c: Detalhe) => void;
}) {
  const avisar = useToast();
  const original = paraInputLocal(i.ocorrido_em ?? i.criado_em);
  const [quando, setQuando] = useState(original);
  const [resumo, setResumo] = useState(i.texto ?? "");
  const [rel, setRel] = useState<CamposRelatorio | null>(i.relatorio ? camposDe(i.relatorio) : null);
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [motivo, setMotivo] = useState("");
  const principal = i.id === chamado.diagnostico_interacao_id;
  const maximo = chamado.concluido_em ? paraInputLocal(chamado.concluido_em) : agoraLocal();

  const salvar = useMutation({
    mutationFn: async () => {
      let c: Detalhe | null = null;
      const novaData = quando !== original ? quando : undefined;
      if (i.relatorio && rel) {
        const antes = camposDe(i.relatorio);
        const mudou = Object.fromEntries(
          Object.entries(rel).filter(([k, v]) => (v || null) !== (antes[k as keyof CamposRelatorio] || null)),
        );
        if (novaData || Object.keys(mudou).length) {
          c = await editarRelatorio(i.relatorio.id, { ...mudou, atendido_em: novaData, motivo: motivo.trim() || undefined });
        }
      } else {
        const novoResumo = resumo.trim() !== (i.texto ?? "") ? resumo.trim() : undefined;
        if (novaData || novoResumo !== undefined) {
          c = await editarResposta(i.id, { ocorrido_em: novaData, texto: novoResumo, motivo: motivo.trim() || undefined });
        }
      }
      if (arquivo) c = await anexarRelatorioExterno(i.id, arquivo, motivo.trim() || undefined);
      if (!c) throw new Error("Nada foi alterado.");
      return c;
    },
    onSuccess: (c) => {
      aoSalvar(c);
      avisar("Alterações salvas. Ficam registradas na linha do tempo.");
    },
  });

  return (
    <form className="formulario form-diagnostico" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
      <Campo rotulo={i.relatorio ? "Data e hora do atendimento *" : "Data e hora do diagnóstico *"}
        dica={principal
          ? `É a data do diagnóstico do chamado: o prazo${chamado.concluido_em ? " e o tempo de solução são recalculados" : " é recalculado"}.`
          : "Não pode ser anterior ao diagnóstico."}>
        {(id) => <input id={id} className="input input-data-hora" type="datetime-local" required
          min={paraInputLocal(principal ? chamado.aberto_em : chamado.diagnosticado_em ?? chamado.aberto_em)} max={maximo}
          value={quando} onChange={(e) => setQuando(e.target.value)} />}
      </Campo>
      {rel ? (
        <CamposDoRelatorio valor={rel} aoMudar={setRel} />
      ) : (
        <Campo rotulo="Resumo do diagnóstico">
          {(id) => <textarea id={id} className="input" rows={3} maxLength={10000} value={resumo}
            onChange={(e) => setResumo(e.target.value)} />}
        </Campo>
      )}
      <div className="campo">
        <span className="rotulo">Relatório externo</span>
        {i.arquivo_nome && <ArquivoExterno i={i} />}
        <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo} compacto
          rotulo={i.arquivo_nome ? "Substituir o relatório externo (o atual fica guardado na linha do tempo)" : "Anexar o relatório externo"} />
      </div>
      <Campo rotulo="Motivo da alteração" dica="Opcional. Fica na linha do tempo junto da alteração.">
        {(id) => <input id={id} className="input" maxLength={2000} value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
      </Campo>
      {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
      <div className="acoes-form">
        <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
        <Botao type="submit" carregando={salvar.isPending}><PencilLine size={16} /> Salvar alterações</Botao>
      </div>
    </form>
  );
}

// ---------- peças comuns (também usadas na linha do tempo) ----------

export function ArquivoExterno({ i }: { i: Interacao }) {
  const avisar = useToast();
  const baixar = useMutation({
    mutationFn: () => baixarArquivoInteracao(i),
    onSuccess: (blob) => salvarArquivo(blob, i.arquivo_nome ?? "arquivo"),
    onError: (e) => avisar(e.message),
  });
  return (
    <button type="button" className="arquivo-escolhido arquivo-baixar" onClick={() => baixar.mutate()} disabled={baixar.isPending}>
      <Download size={16} />
      <span className="arquivo-nome">{i.arquivo_nome}</span>
      {i.arquivo_tamanho !== null && <small className="texto-suave">{tamanho(i.arquivo_tamanho)}</small>}
    </button>
  );
}

export function BotaoPdf({ relatorio }: { relatorio: RelatorioTecnico }) {
  const avisar = useToast();
  const pdf = useMutation({
    mutationFn: () => baixarRelatorioPdf(relatorio.id),
    onSuccess: (blob) => salvarArquivo(blob, `relatorio-${relatorio.codigo}.pdf`),
    onError: (e) => avisar(e.message),
  });
  return (
    <Botao className="btn btn-fantasma btn-pequeno" carregando={pdf.isPending} onClick={() => pdf.mutate()}>
      <Download size={15} /> PDF
    </Botao>
  );
}

export function VisaoRelatorio({ r }: { r: RelatorioTecnico }) {
  const blocos: [string, string | null][] = [
    ["Diagnóstico", r.diagnostico],
    ["Causa provável", r.causa],
    ["Serviço executado", r.servico_executado],
    ["Peças e materiais", r.pecas],
    ["Recomendações", r.recomendacoes],
  ];
  return (
    <div className="relatorio-visao">
      <dl className="dados dados-chamado">
        <Dado rotulo="Técnico" valor={`${r.tecnico?.nome ?? "—"} · ${r.empresa.nome}`} />
        <Dado rotulo="Atendido em" valor={dataHora(r.atendido_em)} />
        <Dado rotulo="Equipamento" valor={r.equipamento ?? "—"} />
        <Dado rotulo="Patrimônio / nº de série" valor={r.identificacao ?? "—"} />
        <Dado rotulo="Situação do equipamento" valor={ROTULO_EQUIPAMENTO[r.situacao_equipamento]} />
      </dl>
      {blocos.filter(([, v]) => v).map(([t, v]) => (
        <div key={t}>
          <h4>{t}</h4>
          <p className="texto-livre">{v}</p>
        </div>
      ))}
    </div>
  );
}
