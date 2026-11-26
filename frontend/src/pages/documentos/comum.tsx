import { useMutation, useQuery } from "@tanstack/react-query";
import { CalendarClock, Folder } from "lucide-react";
import { useEffect, useState } from "react";
import { criarDocumento, listarModelos, listarPastas, organizarDocumento } from "../../api/endpoints";
import { Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type {
  Documento, EstruturaDocumento, EtapaDocumento, FormaAssinatura, OrganizacaoDocumento, StatusDocumento,
} from "../../types";
import { data } from "../../utils/formato";

export const ROTULO_ESTRUTURA: Record<EstruturaDocumento, { nome: string; texto: string }> = {
  EXTERNO: { nome: "Externo (como o ofício)", texto: "Número, data e destinatário por extenso: tratamento, nome, cargo e endereço." },
  INTERNO: { nome: "Interno (como o memorando)", texto: "Título e número na mesma linha, a data, De e Para." },
  SIMPLES: { nome: "Simples (declaração, relatório, ata…)", texto: "Só o título centralizado com o número, sem destinatário." },
};

export const ROTULO_FORMA: Record<FormaAssinatura, string> = { APP: "No app, com a senha", GOVBR: "No GOV.BR" };

export const ROTULO_ETAPA: Record<EtapaDocumento, string> = {
  RASCUNHO: "Rascunho",
  AGUARDANDO: "Aguardando assinatura",
  ASSINADO: "Assinado",
  CONCLUIDO: "Concluído",
  CANCELADO: "Cancelado",
};

const CLASSE_ETAPA: Record<EtapaDocumento, string> = {
  RASCUNHO: "NEUTRO",
  AGUARDANDO: "ATENCAO",
  ASSINADO: "NORMAL",
  CONCLUIDO: "CONCLUIDO",
  CANCELADO: "CRITICO",
};

export function SeloEtapa({ etapa }: { etapa: EtapaDocumento }) {
  return <span className={`selo-doc selo-doc-${CLASSE_ETAPA[etapa]}`}>{ROTULO_ETAPA[etapa]}</span>;
}

/** "Atrasado 2 dias", "Vence hoje", "Vence em 5 dias"; concluído ou cancelado: só a data. */
export function textoPrazo(d: OrganizacaoDocumento): string | null {
  if (!d.prazo) return null;
  if (d.dias_prazo === null) return `Prazo ${data(d.prazo)}`;
  if (d.dias_prazo < 0) return `Atrasado ${-d.dias_prazo} dia${d.dias_prazo === -1 ? "" : "s"}`;
  if (d.dias_prazo === 0) return "Vence hoje";
  if (d.dias_prazo === 1) return "Vence amanhã";
  return `Vence em ${d.dias_prazo} dias`;
}

export function SeloPrazo({ doc }: { doc: OrganizacaoDocumento }) {
  const texto = textoPrazo(doc);
  if (!texto || !doc.prazo) return null;
  const classe = doc.alerta_prazo === "ATRASADO" ? "CRITICO" : doc.alerta_prazo === "ATENCAO" ? "ATENCAO" : "NEUTRO";
  return (
    <span className={`selo-doc selo-doc-${classe}`} title={`Prazo: ${data(doc.prazo)}`}>
      <CalendarClock size={13} aria-hidden /> {texto}
    </span>
  );
}

export function EtiquetaPasta({ nome }: { nome: string | null }) {
  if (!nome) return null;
  return <span className="etiqueta-pasta"><Folder size={13} aria-hidden /> {nome}</span>;
}

/** Escolha do modelo para um documento novo (só os modelos ativos). */
export function ModalNovoDocumento({ pastaId, aoFechar, aoCriar }: {
  pastaId?: number; aoFechar: () => void; aoCriar: (d: Documento) => void;
}) {
  const modelos = useQuery({ queryKey: ["modelos-documento"], queryFn: listarModelos });
  const criar = useMutation({
    mutationFn: (tipo: string) => criarDocumento(tipo, pastaId ? { pasta_id: pastaId } : {}),
    onSuccess: aoCriar,
  });
  return (
    <Modal titulo="Novo documento" aoFechar={aoFechar}>
      <p className="texto-suave">Escolha o modelo. O documento sai no timbrado da unidade, com número, data e código de verificação.</p>
      {modelos.isPending ? <Carregando /> : modelos.isError ? <ErroBox erro={modelos.error} /> : (
        <div className="lista-modelos">
          {modelos.data.filter((m) => m.ativo).map((m) => (
            <button key={m.codigo} type="button" className="cartao-modelo" disabled={criar.isPending}
              onClick={() => criar.mutate(m.codigo)}>
              <strong>{m.nome}</strong>
              {m.descricao && <span className="texto-suave">{m.descricao}</span>}
              <small className="texto-suave">
                {ROTULO_ESTRUTURA[m.estrutura].nome} · assinatura sugerida: {ROTULO_FORMA[m.forma_assinatura].toLowerCase()}
              </small>
            </button>
          ))}
        </div>
      )}
      {criar.isError && <div className="alerta-erro" role="alert">{criar.error.message}</div>}
      <p className="texto-suave">Falta algum modelo da instituição? O administrador do módulo cadastra em <strong>Modelos de documento</strong>.</p>
    </Modal>
  );
}

/** Pasta e prazo do documento: mudam a qualquer momento, sem mexer no conteúdo (quem elaborou ou o administrador). */
export function CartaoOrganizacao({ doc, aoMudar }: { doc: Documento; aoMudar: (d: Documento) => void }) {
  const pastas = useQuery({ queryKey: ["pastas-documento"], queryFn: listarPastas });
  const [prazo, setPrazo] = useState(doc.prazo ?? "");
  useEffect(() => setPrazo(doc.prazo ?? ""), [doc.prazo]);
  const salvar = useMutation({
    mutationFn: (dados: { pasta_id?: number | null; prazo?: string | null }) => organizarDocumento(doc.id, dados),
    onSuccess: aoMudar,
  });
  const fechado = doc.etapa === "CONCLUIDO" || doc.etapa === "CANCELADO";
  const bloqueado = !doc.pode_organizar || salvar.isPending;
  const opcoes = (pastas.data ?? []).filter((p) => p.ativo || p.id === doc.pasta_id);
  return (
    <section className="cartao">
      <h2 className="titulo-secao">Organização</h2>
      <p className="texto-suave">
        A pasta e o prazo servem para organizar e acompanhar: não saem no documento e podem mudar a qualquer momento.
        {!doc.pode_organizar && " Só quem elaborou ou o administrador muda."}
      </p>
      <div className="grade-2">
        <Campo rotulo="Pasta">
          {(i) => (
            <select id={i} className="input" value={doc.pasta_id ?? ""} disabled={bloqueado}
              onChange={(e) => salvar.mutate({ pasta_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">Sem pasta</option>
              {opcoes.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
              {doc.pasta_id && !opcoes.some((p) => p.id === doc.pasta_id) && <option value={doc.pasta_id}>{doc.pasta_nome}</option>}
            </select>
          )}
        </Campo>
        <Campo rotulo="Prazo" dica={fechado ? "Concluído ou cancelado: o prazo não conta mais." : "Conta até o documento ser concluído."}>
          {(i) => (
            <input id={i} type="date" className="input" value={prazo} disabled={bloqueado}
              onChange={(e) => {
                const valor = e.target.value;
                setPrazo(valor);
                if (valor === "" || /^\d{4}-\d{2}-\d{2}$/.test(valor)) salvar.mutate({ prazo: valor || null });
              }} />
          )}
        </Campo>
      </div>
      {doc.prazo && <div><SeloPrazo doc={doc} /></div>}
      {salvar.isError && <div className="alerta-erro" role="alert">{salvar.error.message}</div>}
    </section>
  );
}

export const ROTULO_STATUS_DOC: Record<StatusDocumento, string> = {
  RASCUNHO: "Rascunho",
  EMITIDO: "Emitido",
  CANCELADO: "Cancelado",
};

const CLASSE_STATUS_DOC: Record<StatusDocumento, string> = {
  RASCUNHO: "NEUTRO",
  EMITIDO: "NORMAL",
  CANCELADO: "CRITICO",
};

export function SeloDocumento({ status }: { status: StatusDocumento }) {
  return <span className={`selo-doc selo-doc-${CLASSE_STATUS_DOC[status]}`}>{ROTULO_STATUS_DOC[status]}</span>;
}

/** Portais oficiais: onde se assina com a conta GOV.BR e onde qualquer pessoa confere o PDF assinado. */
export const URL_ASSINADOR = "https://assinador.iti.br";
export const URL_VALIDADOR = "https://validar.iti.gov.br";

/** Abre o blob numa aba nova (a aba é aberta já no clique, para o navegador não bloquear). */
export async function abrirEmNovaAba(obter: () => Promise<Blob>) {
  const janela = window.open("", "_blank");
  try {
    const url = URL.createObjectURL(await obter());
    if (janela) janela.location.href = url;
    setTimeout(() => URL.revokeObjectURL(url), 120_000);
  } catch (e) {
    janela?.close();
    throw e;
  }
}

/** Papel no módulo Documentos: o cliente é o "redator" (redige e assina). */
export const ROTULO_PAPEL_DOCUMENTOS: Record<"MASTER" | "ADMIN" | "CLIENTE" | "TECNICO", string> = {
  MASTER: "Master",
  ADMIN: "Administrador",
  CLIENTE: "Redator",
  TECNICO: "Técnico",
};
