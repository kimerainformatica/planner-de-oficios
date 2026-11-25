import type { StatusDocumento, TipoDocumento } from "../../types";

export const NOME_TIPO_DOC: Record<TipoDocumento, string> = { OFICIO: "Ofício", MEMORANDO: "Memorando" };

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
