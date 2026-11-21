import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BadgeCheck, Ban, Copy, Download, ExternalLink, FileCheck2, Hourglass, RefreshCw, Signature, Trash2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  assinarDocumento, cancelarDocumento, descartarDocumento, duplicarDocumento, emitirDocumento, listarAssinantes,
  listarTipos, obterDocumento, pdfDocumento, salvarDocumento,
} from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type { CamposDocumento, Destinatario, Documento as Doc, PapelAssinatura } from "../../types";
import { salvarArquivo } from "../../utils/arquivo";
import { data, dataHora, ROTULO_DESTINATARIO } from "../../utils/formato";
import { abrirEmNovaAba, NOME_TIPO_DOC, SeloDocumento } from "./comum";

const CAMPOS: (keyof CamposDocumento)[] = [
  "assunto", "vocativo", "corpo", "fecho", "dest_tratamento", "dest_nome", "dest_cargo", "dest_endereco", "de", "para",
  "registrar_no_planner", "oficio_tipo", "destinatario_tipo", "destinatario_setor", "elaborador_cargo", "elaborador_ident", "validador_id",
  "validador_nome", "validador_cargo", "validador_ident",
];

function camposDe(d: Doc): CamposDocumento {
  return Object.fromEntries(CAMPOS.map((c) => [c, d[c]])) as unknown as CamposDocumento;
}

function nomeArquivo(d: Doc) {
  const base = d.titulo.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `${base.replace(/^-|-$/g, "")}${d.numero_formatado ? "" : `-${d.id}`}.pdf`;
}

/** Prévia do PDF (o mesmo arquivo que sai para impressão), num quadro ao lado. */
function PreviaPdf({ doc, versao }: { doc: Doc; versao: number }) {
  const [url, setUrl] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => {
    let ativo = true;
    let criada: string | null = null;
    pdfDocumento(doc.id)
      .then((blob) => {
        if (!ativo) return;
        criada = URL.createObjectURL(blob);
        setUrl(criada);
        setErro(null);
      })
      .catch((e: Error) => ativo && setErro(e.message));
    return () => {
      ativo = false;
      if (criada) setTimeout(() => URL.revokeObjectURL(criada!), 1000);
    };
  }, [doc.id, versao]);
  if (erro) return <div className="alerta-erro">{erro}</div>;
  if (!url) return <Carregando texto="Montando o PDF…" />;
  return <iframe className="previa-pdf" src={`${url}#view=FitH&toolbar=0`} title={`Prévia do ${doc.titulo}`} />;
}

export function Documento() {
  const id = Number(useParams().id);
  const consulta = useQuery({ queryKey: ["documento", id], queryFn: () => obterDocumento(id) });
  if (consulta.isPending) return <Carregando />;
  if (consulta.isError) return <ErroBox erro={consulta.error} />;
  return consulta.data.pode_editar ? <Editor doc={consulta.data} /> : <Visao doc={consulta.data} />;
}

// ---------- rascunho ----------

function Editor({ doc }: { doc: Doc }) {
  const qc = useQueryClient();
  const avisar = useToast();
  const navegar = useNavigate();
  const oficio = doc.tipo === "OFICIO";
  const [f, setF] = useState<CamposDocumento>(() => camposDe(doc));
  const salvo = useRef(JSON.stringify(camposDe(doc)));
  const [versaoPrevia, setVersaoPrevia] = useState(0);
  const [emitindo, setEmitindo] = useState(false);
  const [descartando, setDescartando] = useState(false);
  const tipos = useQuery({ queryKey: ["tipos"], queryFn: listarTipos, enabled: oficio && doc.usa_planner });
  const assinantes = useQuery({ queryKey: ["assinantes"], queryFn: listarAssinantes });

  const salvar = useMutation({
    mutationFn: (dados: CamposDocumento) => {
      // só o que mudou desde o último salvamento
      const antes = JSON.parse(salvo.current) as CamposDocumento;
      const mudou = Object.fromEntries(CAMPOS.filter((c) => antes[c] !== dados[c]).map((c) => [c, dados[c]]));
      return salvarDocumento(doc.id, mudou);
    },
    onSuccess: (novo, enviado) => {
      // compara com o que foi enviado (o servidor guarda texto vazio como nulo; assim não fica salvando em laço)
      const antes = JSON.parse(salvo.current) as CamposDocumento;
      if (antes.validador_id !== enviado.validador_id) {
        // trocou a pessoa do "De acordo": o servidor completa nome, cargo e ID com o cadastro dela
        const sinc = { validador_id: novo.validador_id, validador_nome: novo.validador_nome,
          validador_cargo: novo.validador_cargo, validador_ident: novo.validador_ident };
        salvo.current = JSON.stringify({ ...enviado, ...sinc });
        setF((a) => ({ ...a, ...sinc }));
      } else {
        salvo.current = JSON.stringify(enviado);
      }
      qc.setQueryData(["documento", doc.id], novo);
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  const pendente = JSON.stringify(f) !== salvo.current;

  // salva sozinho um pouco depois da última alteração
  useEffect(() => {
    if (!pendente) return;
    const t = setTimeout(() => salvar.mutate(f), 900);
    return () => clearTimeout(t);
  }, [f]); // eslint-disable-line react-hooks/exhaustive-deps

  const salvarAgora = useCallback(async () => {
    if (JSON.stringify(f) !== salvo.current) await salvar.mutateAsync(f);
  }, [f, salvar]);

  const atual = (qc.getQueryData(["documento", doc.id]) as Doc | undefined) ?? doc;
  const pendencias = atual.pendencias;
  const muda = <K extends keyof CamposDocumento>(campo: K) => (valor: CamposDocumento[K]) =>
    setF((a) => ({ ...a, [campo]: valor }));

  async function atualizarPrevia() {
    await salvarAgora();
    setVersaoPrevia((v) => v + 1);
  }

  const escolhaDeAcordo = f.validador_id ? String(f.validador_id) : f.validador_nome !== null ? "outra" : "";

  return (
    <>
      <header className="pagina-topo">
        <div>
          <Link to="/documentos" className="voltar"><ArrowLeft size={16} /> Documentos</Link>
          <h1>{NOME_TIPO_DOC[doc.tipo]} <SeloDocumento status="RASCUNHO" /></h1>
          <p className="texto-suave" aria-live="polite">
            {salvar.isPending ? "Salvando…" : pendente ? "Alterações ainda não salvas" : `Rascunho salvo · ${dataHora(atual.atualizado_em)}`}
            {" · "}O número e a data saem na emissão.
          </p>
        </div>
        <div className="grupo">
          <button className="btn btn-fantasma btn-perigo" onClick={() => setDescartando(true)}><Trash2 size={16} /> Descartar</button>
          <Botao className="btn btn-secundario" onClick={() => atualizarPrevia()}><RefreshCw size={16} /> Atualizar prévia</Botao>
          <Botao disabled={pendencias.length > 0 && !pendente} onClick={async () => { await salvarAgora(); setEmitindo(true); }}>
            <FileCheck2 size={18} /> Emitir
          </Botao>
        </div>
      </header>

      <div className="documento-grade">
        <form className="formulario documento-form" onSubmit={(e: FormEvent) => { e.preventDefault(); salvarAgora(); }}>
          {oficio ? (
            <section className="cartao">
              <h2 className="titulo-secao">Destinatário</h2>
              <div className="grade-2">
                <Campo rotulo="Tratamento">
                  {(i) => <input id={i} className="input" maxLength={60} value={f.dest_tratamento ?? ""}
                    placeholder="A/C sr. (sra.)" onChange={(e) => muda("dest_tratamento")(e.target.value)} />}
                </Campo>
                <Campo rotulo="Nome *">
                  {(i) => <input id={i} className="input" maxLength={160} value={f.dest_nome ?? ""}
                    onChange={(e) => muda("dest_nome")(e.target.value)} />}
                </Campo>
                <Campo rotulo="Cargo ou função">
                  {(i) => <input id={i} className="input" maxLength={160} value={f.dest_cargo ?? ""}
                    onChange={(e) => muda("dest_cargo")(e.target.value)} />}
                </Campo>
                <Campo rotulo="Órgão ou empresa e endereço">
                  {(i) => <input id={i} className="input" maxLength={300} value={f.dest_endereco ?? ""}
                    onChange={(e) => muda("dest_endereco")(e.target.value)} />}
                </Campo>
              </div>
              <h3 className="subtitulo-secao">Integração com o Planner de Ofícios</h3>
              <label className="checkbox">
                <input type="checkbox" checked={f.registrar_no_planner} disabled={!doc.usa_planner}
                  onChange={(e) => muda("registrar_no_planner")(e.target.checked)} />
                Registrar no Planner de Ofícios ao emitir
              </label>
              <p className="texto-suave">
                {!doc.usa_planner
                  ? "Você não usa o Planner de Ofícios. Para registrar os ofícios lá, peça o acesso a um administrador."
                  : f.registrar_no_planner
                    ? "Na emissão o ofício entra no Planner com o mesmo número, e os prazos de resposta começam a contar."
                    : "O ofício sai só como documento, sem acompanhamento de prazo no Planner."}
              </p>
              {f.registrar_no_planner && doc.usa_planner && <div className="grade-3">
                <Campo rotulo="Tipo de ofício *">
                  {(i) => (
                    <select id={i} className="input" value={f.oficio_tipo ?? ""} onChange={(e) => muda("oficio_tipo")(e.target.value || null)}>
                      <option value="">Escolha…</option>
                      {tipos.data?.filter((t) => t.ativo || t.codigo === f.oficio_tipo).map((t) => <option key={t.codigo} value={t.codigo}>{t.nome}</option>)}
                    </select>
                  )}
                </Campo>
                <Campo rotulo="Destinatário no Planner">
                  {(i) => (
                    <select id={i} className="input" value={f.destinatario_tipo ?? ""}
                      onChange={(e) => setF((a) => ({ ...a, destinatario_tipo: (e.target.value || null) as Destinatario | null,
                        destinatario_setor: e.target.value ? a.destinatario_setor : null }))}>
                      <option value="">Não informar</option>
                      {(Object.keys(ROTULO_DESTINATARIO) as Destinatario[]).map((d) => <option key={d} value={d}>{ROTULO_DESTINATARIO[d]}</option>)}
                    </select>
                  )}
                </Campo>
                {f.destinatario_tipo && (
                  <Campo rotulo={f.destinatario_tipo === "OUTROS" ? "Destino *" : "Setor *"}>
                    {(i) => <input id={i} className="input" maxLength={120} value={f.destinatario_setor ?? ""}
                      onChange={(e) => muda("destinatario_setor")(e.target.value)} />}
                  </Campo>
                )}
              </div>}
            </section>
          ) : (
            <section className="cartao">
              <h2 className="titulo-secao">Setores</h2>
              <div className="grade-2">
                <Campo rotulo="De *">
                  {(i) => <input id={i} className="input" maxLength={160} value={f.de ?? ""} placeholder="Setor de quem envia"
                    onChange={(e) => muda("de")(e.target.value)} />}
                </Campo>
                <Campo rotulo="Para *">
                  {(i) => <input id={i} className="input" maxLength={160} value={f.para ?? ""} placeholder="Setor de destino"
                    onChange={(e) => muda("para")(e.target.value)} />}
                </Campo>
              </div>
            </section>
          )}

          <section className="cartao">
            <h2 className="titulo-secao">Texto</h2>
            <Campo rotulo="Assunto *" dica={oficio ? "Sai em negrito, depois de “Assunto:”." : undefined}>
              {(i) => <input id={i} className="input" maxLength={300} value={f.assunto} onChange={(e) => muda("assunto")(e.target.value)} />}
            </Campo>
            <Campo rotulo="Vocativo">
              {(i) => <input id={i} className="input" maxLength={160} value={f.vocativo} onChange={(e) => muda("vocativo")(e.target.value)} />}
            </Campo>
            <Campo rotulo="Corpo do texto *"
              dica={`Cada linha vira um parágrafo, em Times New Roman 12, justificado, com recuo de ${oficio ? "1,75" : "1,25"} cm. Linguagem direta, frases curtas, sem negrito, sublinhado ou exclamação.`}>
              {(i) => <textarea id={i} className="input texto-documento" rows={12} maxLength={30000} value={f.corpo}
                onChange={(e) => muda("corpo")(e.target.value)} />}
            </Campo>
            <Campo rotulo="Fecho">
              {(i) => <input id={i} className="input" maxLength={120} value={f.fecho} onChange={(e) => muda("fecho")(e.target.value)} />}
            </Campo>
          </section>

          <section className="cartao">
            <h2 className="titulo-secao">Assinaturas</h2>
            <p className="texto-suave">
              O PDF sai com o espaço para assinar à mão. Depois de emitido, cada pessoa também pode assinar aqui no app, com a
              senha: a assinatura eletrônica aparece no lugar da assinatura à mão.
            </p>
            <h3 className="subtitulo-secao">Quem elaborou</h3>
            <div className="grade-3">
              <Campo rotulo="Nome">{(i) => <input id={i} className="input" value={atual.elaborador_nome} readOnly disabled />}</Campo>
              <Campo rotulo="Cargo *">
                {(i) => <input id={i} className="input" maxLength={120} value={f.elaborador_cargo ?? ""}
                  onChange={(e) => muda("elaborador_cargo")(e.target.value)} />}
              </Campo>
              <Campo rotulo={oficio ? "ID" : "Matrícula"}>
                {(i) => <input id={i} className="input" maxLength={30} value={f.elaborador_ident ?? ""}
                  onChange={(e) => muda("elaborador_ident")(e.target.value)} />}
              </Campo>
            </div>
            <h3 className="subtitulo-secao">De acordo</h3>
            <Campo rotulo="Quem valida">
              {(i) => (
                <select id={i} className="input" value={escolhaDeAcordo} onChange={(e) => {
                  const v = e.target.value;
                  if (!v) setF((a) => ({ ...a, validador_id: null, validador_nome: null, validador_cargo: null, validador_ident: null }));
                  else if (v === "outra") setF((a) => ({ ...a, validador_id: null, validador_nome: "", validador_cargo: null, validador_ident: null }));
                  else {
                    const p = assinantes.data?.find((x) => x.id === Number(v));
                    setF((a) => ({ ...a, validador_id: Number(v), validador_nome: p?.nome ?? a.validador_nome,
                      validador_cargo: p?.cargo ?? null, validador_ident: p?.matricula ?? null }));
                  }
                }}>
                  <option value="">Sem “De acordo”</option>
                  {assinantes.data?.map((p) => <option key={p.id} value={p.id}>{p.nome}{p.cargo ? ` · ${p.cargo}` : ""}</option>)}
                  <option value="outra">Outra pessoa (só assinatura à mão)</option>
                </select>
              )}
            </Campo>
            {escolhaDeAcordo && (
              <div className="grade-3">
                <Campo rotulo="Nome *">
                  {(i) => <input id={i} className="input" maxLength={120} value={f.validador_nome ?? ""}
                    onChange={(e) => muda("validador_nome")(e.target.value)} />}
                </Campo>
                <Campo rotulo="Cargo *">
                  {(i) => <input id={i} className="input" maxLength={120} value={f.validador_cargo ?? ""}
                    onChange={(e) => muda("validador_cargo")(e.target.value)} />}
                </Campo>
                <Campo rotulo={oficio ? "ID" : "Matrícula"}>
                  {(i) => <input id={i} className="input" maxLength={30} value={f.validador_ident ?? ""}
                    onChange={(e) => muda("validador_ident")(e.target.value)} />}
                </Campo>
              </div>
            )}
          </section>

          {pendencias.length > 0 && !pendente && (
            <div className="alerta-info" role="status">Para emitir, falta preencher {pendencias.join(", ")}.</div>
          )}
        </form>

        <aside className="cartao documento-previa">
          <div className="grupo documento-previa-topo">
            <strong>Prévia</strong>
            <button className="btn btn-fantasma btn-pequeno" onClick={() => abrirEmNovaAba(() => pdfDocumento(doc.id)).catch((e) => avisar(e.message, "erro"))}>
              <ExternalLink size={15} /> Abrir
            </button>
          </div>
          <PreviaPdf doc={doc} versao={versaoPrevia} />
        </aside>
      </div>

      {emitindo && (
        <ModalEmitir doc={atual} aoFechar={() => setEmitindo(false)} aoEmitir={(d) => {
          qc.setQueryData(["documento", d.id], d);
          qc.invalidateQueries({ queryKey: ["documentos"] });
          qc.invalidateQueries({ queryKey: ["oficios"] });
          avisar(`${d.titulo} emitido.`);
        }} />
      )}
      {descartando && (
        <Modal titulo="Descartar o rascunho" aoFechar={() => setDescartando(false)}>
          <p>O rascunho será apagado. Como ele ainda não tem número, nenhuma numeração fica para trás.</p>
          <div className="acoes-form">
            <button className="btn btn-secundario" onClick={() => setDescartando(false)}>Voltar</button>
            <Botao className="btn btn-perigo" onClick={async () => {
              try {
                await descartarDocumento(doc.id);
                qc.invalidateQueries({ queryKey: ["documentos"] });
                navegar("/documentos");
              } catch (e) { avisar((e as Error).message, "erro"); }
            }}>Descartar</Botao>
          </div>
        </Modal>
      )}
    </>
  );
}

function ModalEmitir({ doc, aoFechar, aoEmitir }: { doc: Doc; aoFechar: () => void; aoEmitir: (d: Doc) => void }) {
  const emitir = useMutation({ mutationFn: () => emitirDocumento(doc.id), onSuccess: (d) => { aoEmitir(d); aoFechar(); } });
  const oficio = doc.tipo === "OFICIO";
  return (
    <Modal titulo={`Emitir o ${oficio ? "ofício" : "memorando"}`} aoFechar={aoFechar}>
      {doc.pendencias.length > 0 ? (
        <div className="alerta-info">Para emitir, falta preencher {doc.pendencias.join(", ")}.</div>
      ) : (
        <ul className="lista-explicacao">
          <li>Recebe o próximo número da sua sequência e a data de hoje.</li>
          <li>O texto fica travado. Para corrigir depois, cancele e faça um novo a partir dele.</li>
          <li>Ganha um código de verificação e um QR code no rodapé.</li>
          {oficio && doc.registrar_no_planner && <li>Entra no Planner de Ofícios como pendente de resposta, com o PDF ligado a ele.</li>}
        </ul>
      )}
      {emitir.isError && <div className="alerta-erro">{emitir.error.message}</div>}
      <div className="acoes-form">
        <button className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
        <Botao carregando={emitir.isPending} disabled={doc.pendencias.length > 0} onClick={() => emitir.mutate()}>
          <FileCheck2 size={16} /> Emitir agora
        </Botao>
      </div>
    </Modal>
  );
}

// ---------- emitido, cancelado ou rascunho de outra pessoa ----------

const ROTULO_PAPEL: Record<PapelAssinatura, string> = { ELABORADOR: "Quem elaborou", VALIDADOR: "De acordo" };

function Visao({ doc }: { doc: Doc }) {
  const usaPlanner = useAuth().modulos.includes("OFICIOS");
  const qc = useQueryClient();
  const avisar = useToast();
  const navegar = useNavigate();
  const [assinando, setAssinando] = useState(false);
  const [cancelando, setCancelando] = useState(false);
  const atualizar = (d: Doc) => {
    qc.setQueryData(["documento", d.id], d);
    qc.invalidateQueries({ queryKey: ["documentos"] });
    qc.invalidateQueries({ queryKey: ["documentos-resumo"] });
  };
  const baixar = useMutation({
    mutationFn: () => pdfDocumento(doc.id),
    onSuccess: (blob) => salvarArquivo(blob, nomeArquivo(doc)),
    onError: (e) => avisar(e.message, "erro"),
  });
  const duplicar = useMutation({
    mutationFn: () => duplicarDocumento(doc.id),
    onSuccess: (d) => { qc.invalidateQueries({ queryKey: ["documentos"] }); navegar(`/documentos/${d.id}`); },
    onError: (e) => avisar(e.message, "erro"),
  });
  const feitas = new Map(doc.assinaturas.map((a) => [a.papel, a]));
  const blocos: { papel: PapelAssinatura; nome: string; cargo: string | null }[] = [
    { papel: "ELABORADOR", nome: doc.elaborador_nome, cargo: doc.elaborador_cargo },
    ...(doc.validador_nome ? [{ papel: "VALIDADOR" as const, nome: doc.validador_nome, cargo: doc.validador_cargo }] : []),
  ];

  return (
    <>
      <header className="pagina-topo">
        <div>
          <Link to="/documentos" className="voltar"><ArrowLeft size={16} /> Documentos</Link>
          <h1>{doc.titulo} <SeloDocumento status={doc.status} /></h1>
          <p className="texto-suave">{doc.assunto}</p>
        </div>
        <div className="grupo">
          {doc.assinar_como && (
            <button className="btn btn-primario" onClick={() => setAssinando(true)}><Signature size={18} /> Assinar no app</button>
          )}
          <Botao className="btn btn-secundario" carregando={baixar.isPending} onClick={() => baixar.mutate()}><Download size={16} /> Baixar PDF</Botao>
          <button className="btn btn-secundario" onClick={() => abrirEmNovaAba(() => pdfDocumento(doc.id)).catch((e) => avisar(e.message, "erro"))}>
            <ExternalLink size={16} /> Abrir para imprimir
          </button>
          {doc.status !== "RASCUNHO" && (
            <Botao className="btn btn-fantasma" carregando={duplicar.isPending} onClick={() => duplicar.mutate()}><Copy size={16} /> Fazer um novo a partir deste</Botao>
          )}
          {doc.pode_cancelar && (
            <button className="btn btn-fantasma btn-perigo" onClick={() => setCancelando(true)}><Ban size={16} /> Cancelar</button>
          )}
        </div>
      </header>

      <div className="documento-grade">
        <div className="documento-form">
          {doc.status === "RASCUNHO" && (
            <div className="alerta-info">Rascunho em elaboração por {doc.elaborador_nome}. Ele ainda pode mudar e não tem número.</div>
          )}
          {doc.status === "CANCELADO" && (
            <div className="alerta-erro">
              Cancelado em {doc.cancelado_em ? dataHora(doc.cancelado_em) : "—"}{doc.cancelado_por_nome ? ` por ${doc.cancelado_por_nome}` : ""}:
              {" "}{doc.motivo_cancelamento}. A verificação pelo código mostra o cancelamento.
            </div>
          )}
          <section className="cartao">
            <h2 className="titulo-secao">Dados</h2>
            <dl className="dados-documento">
              <dt>Tipo</dt><dd>{NOME_TIPO_DOC[doc.tipo]}</dd>
              <dt>Data</dt><dd>{doc.data_documento ? data(doc.data_documento) : "—"}</dd>
              <dt>{doc.tipo === "OFICIO" ? "Destinatário" : "De → Para"}</dt>
              <dd>{doc.tipo === "OFICIO" ? [doc.dest_nome, doc.dest_cargo].filter(Boolean).join(" · ") : `${doc.de ?? "—"} → ${doc.para ?? "—"}`}</dd>
              {doc.codigo && (<><dt>Código de verificação</dt><dd><strong className="codigo-verificacao">{doc.codigo}</strong>{" "}
                <Link to={`/verificar/${doc.codigo}`} target="_blank" className="link">conferir</Link></dd></>)}
              {doc.emitido_em && (<><dt>Emitido em</dt><dd>{dataHora(doc.emitido_em)}</dd></>)}
              {doc.oficio_id && (<><dt>No Planner</dt><dd>{usaPlanner
                ? <Link className="link-forte" to={`/oficios/${doc.oficio_id}`}>Abrir o ofício e acompanhar os prazos</Link>
                : "Registrado no Planner de Ofícios"}</dd></>)}
            </dl>
          </section>
          <section className="cartao">
            <h2 className="titulo-secao">Assinaturas</h2>
            <ul className="lista-assinaturas">
              {blocos.map((b) => {
                const a = feitas.get(b.papel);
                return (
                  <li key={b.papel}>
                    <span className="assinatura-icone" aria-hidden>{a ? <BadgeCheck size={20} /> : <Hourglass size={18} />}</span>
                    <div>
                      <strong>{b.nome}</strong>{b.cargo && <span className="texto-suave"> · {b.cargo}</span>}
                      <small className="texto-suave"><br />{ROTULO_PAPEL[b.papel]} · {a
                        ? `assinado eletronicamente em ${dataHora(a.assinado_em)}`
                        : doc.status === "EMITIDO" ? "assinatura à mão no papel ou aqui no app" : "—"}</small>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        </div>
        <aside className="cartao documento-previa">
          <PreviaPdf doc={doc} versao={doc.assinaturas.length + (doc.status === "CANCELADO" ? 100 : 0)} />
        </aside>
      </div>

      {assinando && doc.assinar_como && (
        <ModalAssinar doc={doc} papel={doc.assinar_como} aoFechar={() => setAssinando(false)}
          aoAssinar={(d) => { atualizar(d); avisar("Documento assinado."); }} />
      )}
      {cancelando && (
        <ModalCancelar doc={doc} aoFechar={() => setCancelando(false)} aoCancelar={(d) => { atualizar(d); avisar(`${d.titulo} cancelado.`); }} />
      )}
    </>
  );
}

function ModalAssinar({ doc, papel, aoFechar, aoAssinar }: {
  doc: Doc; papel: PapelAssinatura; aoFechar: () => void; aoAssinar: (d: Doc) => void;
}) {
  const [senha, setSenha] = useState("");
  const assinar = useMutation({ mutationFn: () => assinarDocumento(doc.id, senha), onSuccess: (d) => { aoAssinar(d); aoFechar(); } });
  const nome = papel === "ELABORADOR" ? doc.elaborador_nome : doc.validador_nome;
  return (
    <Modal titulo={`Assinar o ${doc.titulo}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); assinar.mutate(); }}>
        <p>
          Você assina como <strong>{nome}</strong> ({papel === "ELABORADOR" ? "quem elaborou" : "De acordo"}). A assinatura fica
          registrada com data, hora e o computador usado, e aparece no PDF no lugar da assinatura à mão.
        </p>
        <Campo rotulo="Confirme a sua senha">
          {(i) => <input id={i} className="input" type="password" autoComplete="current-password" required autoFocus
            value={senha} onChange={(e) => setSenha(e.target.value)} />}
        </Campo>
        {assinar.isError && <div className="alerta-erro">{assinar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
          <Botao type="submit" carregando={assinar.isPending}><Signature size={16} /> Assinar</Botao>
        </div>
      </form>
    </Modal>
  );
}

function ModalCancelar({ doc, aoFechar, aoCancelar }: { doc: Doc; aoFechar: () => void; aoCancelar: (d: Doc) => void }) {
  const [motivo, setMotivo] = useState("");
  const cancelar = useMutation({ mutationFn: () => cancelarDocumento(doc.id, motivo.trim()), onSuccess: (d) => { aoCancelar(d); aoFechar(); } });
  return (
    <Modal titulo={`Cancelar o ${doc.titulo}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); cancelar.mutate(); }}>
        <p>
          O documento continua registrado, mas passa a sair marcado como cancelado, e a verificação pelo código mostra o motivo.
          {doc.oficio_id && " O ofício no Planner não é apagado: se ele não vale mais, peça a exclusão por lá."}
        </p>
        <Campo rotulo="Motivo *">
          {(i) => <textarea id={i} className="input" rows={3} minLength={5} maxLength={500} required autoFocus
            value={motivo} onChange={(e) => setMotivo(e.target.value)} />}
        </Campo>
        {cancelar.isError && <div className="alerta-erro">{cancelar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Voltar</button>
          <Botao type="submit" className="btn btn-perigo" carregando={cancelar.isPending} disabled={motivo.trim().length < 5}>
            Cancelar o documento
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
