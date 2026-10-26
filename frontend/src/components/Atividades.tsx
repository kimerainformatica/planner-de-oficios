import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { Atividade } from "../types";
import {
  data,
  dataHora,
  ROTULO_ACAO,
  ROTULO_DESTINATARIO,
  ROTULO_PERFIL,
  ROTULO_STATUS,
} from "../utils/formato";
import { useTipos } from "../utils/tipos";

const CAMPOS: Record<string, string> = {
  numero: "Nº",
  data_oficio: "Data do ofício",
  tipo: "Tipo",
  protocolo: "Protocolo",
  destinatario_tipo: "Destinatário",
  destinatario_setor: "Setor / destino",
  observacao: "Observação",
  status: "Status",
  data_resposta: "Data da resposta",
  data_recebimento: "Data do recebimento",
  perfil: "Perfil",
  ativo: "Ativo",
  nome: "Nome",
  senha: "Senha",
  motivo: "Motivo",
  motivo_do_pedido: "Motivo do pedido",
  resposta: "Resposta",
  arquivo: "Arquivo",
  tamanho_bytes: "Tamanho",
  sha256: "Hash SHA-256",
  dono: "Cliente",
  anexos: "Documentos",
  datas: "Datas",
};

const ROTULOS_VALOR: Record<string, string> = {
  IMOBILIARIO: "Mobiliários", // código antigo (antes da migração 0004), pode aparecer em registros antigos
  ...ROTULO_STATUS,
  ...ROTULO_DESTINATARIO,
  ...ROTULO_PERFIL,
};

function valor(v: unknown, rotulos: Record<string, string>): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "Sim" : "Não";
  if (Array.isArray(v)) return v.map((x) => valor(x, rotulos)).join(", ") || "—";
  if (typeof v === "string") {
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return data(v);
    return rotulos[v] ?? v;
  }
  return String(v);
}

function ehMudanca(v: unknown): v is { de: unknown; para: unknown } {
  return typeof v === "object" && v !== null && "de" in v && "para" in v;
}

export function DetalhesAtividade({ detalhes }: { detalhes: Record<string, unknown> }) {
  const { todos } = useTipos();
  // códigos dos tipos de ofício aparecem pelo nome cadastrado
  const rotulos = { ...ROTULOS_VALOR, ...Object.fromEntries(todos.map((t) => [t.codigo, t.nome])) };
  return (
    <dl className="detalhes-atividade">
      {Object.entries(detalhes).map(([campo, v]) => (
        <div key={campo}>
          <dt>{CAMPOS[campo] ?? campo}</dt>
          <dd>
            {ehMudanca(v) ? (
              v.de === null || v.de === undefined ? (
                valor(v.para, rotulos)
              ) : (
                <>
                  <span className="valor-antigo">{valor(v.de, rotulos)}</span> →{" "}
                  <strong>{valor(v.para, rotulos)}</strong>
                </>
              )
            ) : (
              valor(v, rotulos)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Lista de atividades com detalhes expansíveis. */
export function ListaAtividades({
  itens,
  mostrarReferencia = true,
}: {
  itens: Atividade[];
  mostrarReferencia?: boolean;
}) {
  const [aberta, setAberta] = useState<number | null>(null);
  return (
    <ul className="atividades">
      {itens.map((a) => {
        const temDetalhes = a.detalhes && Object.keys(a.detalhes).length > 0;
        const expandida = aberta === a.id;
        return (
          <li key={a.id} className={`atividade acao-${a.acao}`}>
            <button
              className="atividade-linha"
              onClick={() => temDetalhes && setAberta(expandida ? null : a.id)}
              aria-expanded={temDetalhes ? expandida : undefined}
              disabled={!temDetalhes}
            >
              <span className="atividade-seta" aria-hidden>
                {temDetalhes ? expandida ? <ChevronDown size={15} /> : <ChevronRight size={15} /> : null}
              </span>
              <span className="atividade-texto">
                <strong>{a.descricao}</strong>
                <small className="texto-suave">
                  {dataHora(a.criado_em)} · {a.usuario_nome ?? "Sistema"} · {ROTULO_ACAO[a.acao] ?? a.acao}
                </small>
              </span>
            </button>
            {mostrarReferencia && a.referencia && (
              <span className="atividade-ref">
                {a.oficio_id ? <Link to={`/oficios/${a.oficio_id}`}>{a.referencia}</Link> : a.referencia}
              </span>
            )}
            {expandida && a.detalhes && <DetalhesAtividade detalhes={a.detalhes} />}
          </li>
        );
      })}
    </ul>
  );
}
