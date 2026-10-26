// Documentos do ofício e evidências de resposta/entrega: visualizar, baixar, anexar, substituir.
import { useMutation } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Download, Eye, FileText, Paperclip, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import * as ep from "../../api/endpoints";
import { ListaLixeira, useLixeira } from "../../components/Lixeira";
import { ACEITOS, SeletorArquivo, validarArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Carregando } from "../../components/ui";
import type { Anexo, Historico, OficioDetalhe as Detalhe, TipoAnexo } from "../../types";
import { salvarArquivo } from "../../utils/arquivo";
import { dataHora, tamanho } from "../../utils/formato";
import { type TipoEvidencia, useAtualizarOficio } from "./comum";

/** Visualizar (nova aba) e baixar, com o token — links comuns não levam a autenticação. */
function useArquivo() {
  const avisar = useToast();
  return {
    async visualizar(a: Anexo) {
      const janela = window.open("", "_blank"); // abre já no clique para o navegador não bloquear
      try {
        const url = URL.createObjectURL(await ep.baixarAnexo(a));
        if (janela) janela.location.href = url;
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } catch (e) {
        janela?.close();
        avisar(e instanceof Error ? e.message : "Não foi possível abrir", "erro");
      }
    },
    async baixar(a: Anexo) {
      try {
        salvarArquivo(await ep.baixarAnexo(a), a.nome_original);
      } catch (e) {
        avisar(e instanceof Error ? e.message : "Não foi possível baixar", "erro");
      }
    },
  };
}

function InfoArquivo({ anexo, compacto }: { anexo: Anexo; compacto?: boolean }) {
  return (
    <div className="anexo-info">
      <FileText size={compacto ? 18 : 28} className="texto-suave" />
      <div>
        <strong className="arquivo-nome" title={anexo.nome_original}>
          {anexo.nome_original}
        </strong>
        <small className="texto-suave">
          {tamanho(anexo.tamanho_bytes)} · enviado em {dataHora(anexo.enviado_em)}
        </small>
      </div>
    </div>
  );
}

export function SlotAnexo({
  oficio,
  tipo,
  titulo,
  podeEditar,
}: {
  oficio: Detalhe;
  tipo: TipoAnexo;
  titulo: string;
  podeEditar: boolean;
}) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const arquivo = useArquivo();
  const anexo = oficio.anexos.find((a) => a.tipo === tipo);
  const input = useRef<HTMLInputElement>(null);

  const enviar = useMutation({
    mutationFn: (f: File) => ep.enviarAnexo(oficio.id, tipo, f),
    onSuccess: () => {
      atualizar();
      avisar(anexo ? "Documento substituído." : "Documento anexado.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  const remover = useMutation({
    mutationFn: (a: Anexo) => ep.excluirAnexo(a.id),
    onSuccess: () => {
      atualizar();
      avisar("Documento removido.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });

  function escolher(f: File | null | undefined) {
    if (!f) return;
    const problema = validarArquivo(f);
    if (problema) avisar(problema, "erro");
    else enviar.mutate(f);
  }

  return (
    <div className="cartao anexo">
      <span className="rotulo">{titulo}</span>
      {anexo ? (
        <>
          <InfoArquivo anexo={anexo} />
          <div className="grupo">
            <button className="btn btn-secundario btn-pequeno" onClick={() => arquivo.visualizar(anexo)}>
              <Eye size={15} /> Visualizar
            </button>
            <button className="btn btn-secundario btn-pequeno" onClick={() => arquivo.baixar(anexo)}>
              <Download size={15} /> Baixar
            </button>
            {podeEditar && (
              <>
                <Botao className="btn btn-secundario btn-pequeno" carregando={enviar.isPending}
                  onClick={() => input.current?.click()}>
                  <Upload size={15} /> Substituir
                </Botao>
                <Botao className="btn btn-fantasma btn-pequeno texto-perigo" carregando={remover.isPending}
                  onClick={() => confirm(`Remover "${anexo.nome_original}"?`) && remover.mutate(anexo)}>
                  <Trash2 size={15} /> Remover
                </Botao>
              </>
            )}
          </div>
          <input ref={input} type="file" accept={ACEITOS} hidden
            onChange={(e) => { escolher(e.target.files?.[0]); e.target.value = ""; }} />
        </>
      ) : podeEditar ? (
        enviar.isPending ? (
          <Carregando texto="Enviando…" />
        ) : (
          <SeletorArquivo arquivo={null} aoEscolher={escolher} rotulo="Anexar documento" compacto />
        )
      ) : (
        <p className="texto-suave">Nenhum documento anexado.</p>
      )}
    </div>
  );
}

/** Evidência de um evento de resposta ou de recebimento: mostra o arquivo, ou permite anexar/substituir. */
export function ConteudoEvidencia({
  oficioId,
  evento,
  tipo,
  podeEditar,
  podeRemover = false,
  compacto,
}: {
  oficioId: number;
  evento: Historico;
  tipo: TipoEvidencia;
  podeEditar: boolean;
  podeRemover?: boolean; // só admin/master
  compacto?: boolean;
}) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficioId);
  const arquivo = useArquivo();
  const input = useRef<HTMLInputElement>(null);
  const evidencia = evento.evidencia;
  const entrega = tipo === "RECEBIMENTO";

  const enviar = useMutation({
    mutationFn: (f: File) => ep.enviarAnexo(oficioId, tipo, f, evento.id),
    onSuccess: () => {
      atualizar();
      avisar(evidencia ? "Evidência substituída." : "Evidência anexada.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  const remover = useMutation({
    mutationFn: (a: Anexo) => ep.excluirAnexo(a.id),
    onSuccess: () => {
      atualizar();
      avisar("Evidência removida.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });

  function escolher(f: File | null | undefined) {
    if (!f) return;
    const problema = validarArquivo(f);
    if (problema) avisar(problema, "erro");
    else enviar.mutate(f);
  }

  const seletor = (
    <input ref={input} type="file" accept={ACEITOS} hidden
      onChange={(e) => { escolher(e.target.files?.[0]); e.target.value = ""; }} />
  );

  if (!evidencia) {
    if (!podeEditar) return compacto ? null : <p className="texto-suave">Nenhuma evidência anexada.</p>;
    if (compacto) {
      return (
        <>
          <Botao className="btn btn-fantasma btn-pequeno" carregando={enviar.isPending}
            onClick={() => input.current?.click()}>
            <Paperclip size={14} /> {entrega ? "Anexar comprovante de entrega" : "Anexar evidência"}
          </Botao>
          {seletor}
        </>
      );
    }
    return enviar.isPending ? (
      <Carregando texto="Enviando…" />
    ) : (
      <SeletorArquivo arquivo={null} aoEscolher={escolher}
        rotulo={entrega ? "Anexar comprovante de entrega" : "Anexar documento de resposta"} compacto />
    );
  }

  return (
    <div className={compacto ? "evidencia-compacta" : ""}>
      <InfoArquivo anexo={evidencia} compacto={compacto} />
      <div className="grupo">
        <button className="btn btn-secundario btn-pequeno" onClick={() => arquivo.visualizar(evidencia)}>
          <Eye size={15} /> Visualizar
        </button>
        <button className="btn btn-secundario btn-pequeno" onClick={() => arquivo.baixar(evidencia)}>
          <Download size={15} /> Baixar
        </button>
        {podeEditar && !compacto && (
          <Botao className="btn btn-secundario btn-pequeno" carregando={enviar.isPending}
            onClick={() => input.current?.click()}>
            <Upload size={15} /> Substituir
          </Botao>
        )}
        {podeRemover && (
          <Botao className="btn btn-fantasma btn-pequeno texto-perigo" carregando={remover.isPending}
            onClick={() => confirm(`Remover "${evidencia.nome_original}"?`) && remover.mutate(evidencia)}>
            <Trash2 size={15} /> Remover
          </Botao>
        )}
      </div>
      {seletor}
    </div>
  );
}

/** Admin/master: versões anteriores dos documentos deste ofício (substituídas ou removidas). */
export function LixeiraDoOficio({ oficioId }: { oficioId: number }) {
  const [aberta, setAberta] = useState(false);
  const itens = useLixeira(oficioId).data ?? [];
  if (itens.length === 0) return null;
  return (
    <div className="lixeira-oficio">
      <button type="button" className="titulo-recolhivel" aria-expanded={aberta} onClick={() => setAberta((v) => !v)}>
        {aberta ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        Versões anteriores na lixeira ({itens.length})
      </button>
      {aberta && <ListaLixeira oficioId={oficioId} />}
    </div>
  );
}
