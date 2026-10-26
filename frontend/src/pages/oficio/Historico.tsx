// Linha do tempo do ofício e registro de alterações (auditoria).
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Eye, EyeOff, FileCheck2, Pencil, Undo2 } from "lucide-react";
import { useState } from "react";
import * as ep from "../../api/endpoints";
import { ListaAtividades } from "../../components/Atividades";
import { Carregando, ErroBox } from "../../components/ui";
import type { Historico } from "../../types";
import { data, dataHora, ROTULO_STATUS } from "../../utils/formato";
import { ConteudoEvidencia } from "./Anexos";
import { type Correcoes, ativo, ehRecebimento, ehResposta, tipoEvidencia } from "./comum";

function descreverEvento(h: Historico): { titulo: string; classe: string } {
  if (h.status_anterior === null) return { titulo: "Ofício cadastrado", classe: "PENDENTE_RESPOSTA" };
  if (h.status_novo === "PENDENTE_RESPOSTA") return { titulo: "Reaberto — prazo reiniciado", classe: "REABERTO" };
  if (h.status_novo === "RECEBIDO") return { titulo: "Entrega confirmada — recebido", classe: "RECEBIDO" };
  if (h.status_novo === "PENDENTE_RECEBIMENTO") {
    return ehResposta(h)
      ? { titulo: "Resposta registrada: Confirmado — aguardando recebimento", classe: "PENDENTE_RECEBIMENTO" }
      : { titulo: "Passou a exigir confirmação do recebimento", classe: "PENDENTE_RECEBIMENTO" };
  }
  if (!ehResposta(h)) return { titulo: "Deixou de exigir confirmação do recebimento", classe: "CONFIRMADO" };
  return { titulo: `Resposta registrada: ${ROTULO_STATUS[h.status_novo]}`, classe: h.status_novo };
}

export function LinhaDoTempo({
  oficioId,
  historico,
  podeEvidencia,
  correcoes,
}: {
  oficioId: number;
  historico: Historico[];
  podeEvidencia: boolean;
  correcoes: Correcoes | null;
}) {
  // Respostas e entregas desfeitas ficam recolhidas: continuam no histórico, mas não atrapalham a leitura
  const [verDesfeitos, setVerDesfeitos] = useState(false);
  const desfeitos = historico.filter((h) => !ativo(h)).length;
  const visiveis = [...historico].reverse().filter((h) => verDesfeitos || ativo(h));
  return (
    <section className="painel-bloco">
      <div className="bloco-topo">
        <h2>Histórico</h2>
        {desfeitos > 0 && (
          <button type="button" className="btn btn-fantasma btn-pequeno" aria-expanded={verDesfeitos}
            onClick={() => setVerDesfeitos((v) => !v)}>
            {verDesfeitos ? <EyeOff size={14} /> : <Eye size={14} />}
            {verDesfeitos
              ? "Ocultar desfeitos"
              : `Mostrar ${desfeitos} ${desfeitos === 1 ? "evento desfeito" : "eventos desfeitos"}`}
          </button>
        )}
      </div>
    <ol className="linha-tempo">
      {visiveis.map((h) => {
        const { titulo, classe } = descreverEvento(h);
        const evidencia = tipoEvidencia(h);
        const valendo = ativo(h);
        const corrigir =
          h.id === correcoes?.respostaId ? "corrigir-resposta" : h.id === correcoes?.recebimentoId ? "corrigir-recebimento" : null;
        return (
          <li key={h.id} className={`evento evento-${valendo ? classe : "anulado"}`}>
            <span className="evento-ponto" aria-hidden />
            <div>
              <strong>
                {titulo}
                {!valendo && <span className="badge badge-neutro">Desfeito</span>}
              </strong>
              <small className="texto-suave">
                {dataHora(h.alterado_em)}
                {h.usuario_nome && ` · por ${h.usuario_nome}`}
                {ehRecebimento(h)
                  ? ` · entregue em ${data(h.data_recebimento)}`
                  : h.data_resposta && ` · resposta de ${data(h.data_resposta)}`}
              </small>
              {!valendo && h.anulado_em && (
                <small className="evento-desfeito">
                  Desfeito em {dataHora(h.anulado_em)}
                  {h.anulado_por_nome && ` por ${h.anulado_por_nome}`}
                  {h.anulado_motivo && ` · ${h.anulado_motivo}`}
                </small>
              )}
              {h.observacao && <p className="evento-obs">{h.observacao}</p>}
              {evidencia && (h.evidencia || (podeEvidencia && valendo)) && (
                <div className="evento-evidencia">
                  {h.evidencia && (
                    <span className="rotulo-evidencia">
                      <FileCheck2 size={14} /> {evidencia === "RECEBIMENTO" ? "Comprovante de entrega" : "Evidência"}
                    </span>
                  )}
                  <ConteudoEvidencia oficioId={oficioId} evento={h} tipo={evidencia}
                    podeEditar={podeEvidencia && valendo} podeRemover={!!correcoes} compacto />
                </div>
              )}
              {correcoes && (corrigir || h.id === correcoes.desfazerId) && (
                <div className="evento-acoes">
                  {corrigir && (
                    <button className="btn btn-secundario btn-pequeno" onClick={() => correcoes.abrir(corrigir)}>
                      <Pencil size={14} /> {corrigir === "corrigir-resposta" ? "Corrigir resposta" : "Corrigir recebimento"}
                    </button>
                  )}
                  {h.id === correcoes.desfazerId && (
                    <button className="btn btn-fantasma btn-pequeno texto-perigo" onClick={() => correcoes.abrir("desfazer")}>
                      <Undo2 size={14} /> {ehRecebimento(h) ? "Desfazer recebimento" : "Desfazer resposta"}
                    </button>
                  )}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
    </section>
  );
}

/** Auditoria do ofício: recolhida por padrão (o histórico acima já conta a história); carrega só ao abrir. */
export function RegistroAlteracoes({ oficioId }: { oficioId: number }) {
  const [aberto, setAberto] = useState(false);
  const filtros = { oficio_id: oficioId, por_pagina: 200 };
  const consulta = useQuery({
    queryKey: ["atividades", filtros],
    queryFn: () => ep.listarAtividades(filtros),
    enabled: aberto,
  });
  return (
    <section className="painel-bloco">
      <div className="bloco-topo">
        <h2>
          <button type="button" className="titulo-recolhivel" aria-expanded={aberto} onClick={() => setAberto((v) => !v)}>
            {aberto ? <ChevronDown size={18} /> : <ChevronRight size={18} />} Registro de alterações
          </button>
        </h2>
        <small className="texto-suave">Quem alterou o quê, e quando · auditoria completa do ofício</small>
      </div>
      {!aberto ? null : consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : consulta.data.itens.length === 0 ? (
        <p className="texto-suave">Nenhuma alteração registrada (ofícios anteriores ao registro aparecem a partir da próxima alteração).</p>
      ) : (
        <ListaAtividades itens={consulta.data.itens} mostrarReferencia={false} />
      )}
    </section>
  );
}
