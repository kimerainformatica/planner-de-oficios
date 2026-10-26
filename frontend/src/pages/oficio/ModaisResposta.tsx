// Registrar resposta, confirmar recebimento e reabrir.
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, PackageCheck, RotateCcw, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import * as ep from "../../api/endpoints";
import { SeletorArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Modal } from "../../components/ui";
import type { OficioDetalhe as Detalhe, StatusOficio } from "../../types";
import { data, hojeIso, ROTULO_STATUS } from "../../utils/formato";
import { useTipos } from "../../utils/tipos";
import { useAtualizarOficio } from "./comum";

export function ModalResposta({ oficio, aoFechar }: { oficio: Detalhe; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const [status, setStatus] = useState<StatusOficio>("CONFIRMADO");
  const [dataResposta, setDataResposta] = useState(hojeIso());
  const [observacao, setObservacao] = useState("");
  const [evidencia, setEvidencia] = useState<File | null>(null);
  const tipos = useTipos();
  const itens = tipos.exigeEntrega(oficio.tipo);

  const salvar = useMutation({
    mutationFn: async () => {
      const novo = await ep.alterarStatus(oficio.id, {
        status,
        data_resposta: dataResposta,
        observacao: observacao.trim() || null,
      });
      if (!evidencia) return { novo, falhaEvidencia: null };
      // A resposta já está gravada; se a evidência falhar, dá para anexar depois pelo histórico.
      const evento = novo.historico[novo.historico.length - 1];
      try {
        await ep.enviarAnexo(oficio.id, "RESPOSTA", evidencia, evento.id);
        return { novo: null, falhaEvidencia: null };
      } catch (e) {
        return { novo, falhaEvidencia: e instanceof Error ? e.message : "erro" };
      }
    },
    onSuccess: ({ novo, falhaEvidencia }) => {
      atualizar(novo ?? undefined);
      if (falhaEvidencia) {
        avisar(`Resposta registrada, mas a evidência não foi enviada (${falhaEvidencia}). Anexe pelo histórico.`, "erro");
      } else {
        const resultado = status === "CONFIRMADO" && itens ? "Confirmado, aguardando o recebimento" : ROTULO_STATUS[status];
        avisar(`Resposta registrada: ${resultado}${evidencia ? ", com evidência" : ""}.`);
      }
      aoFechar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    salvar.mutate();
  }

  return (
    <Modal titulo="Registrar resposta" aoFechar={aoFechar}>
      <form onSubmit={enviar} className="formulario">
        <div className="opcoes-status">
          <label className={`opcao ${status === "CONFIRMADO" ? "selecionada opcao-confirmado" : ""}`}>
            <input type="radio" name="status" checked={status === "CONFIRMADO"}
              onChange={() => setStatus("CONFIRMADO")} />
            <CheckCircle2 size={20} />
            <span>
              <strong>Confirmado</strong>
              <small className="texto-suave">
                {itens ? "Segue para pendente de recebimento" : "Encerra o ofício (definitivo)"}
              </small>
            </span>
          </label>
          <label className={`opcao ${status === "NAO_CONFIRMADO" ? "selecionada opcao-nao-confirmado" : ""}`}>
            <input type="radio" name="status" checked={status === "NAO_CONFIRMADO"}
              onChange={() => setStatus("NAO_CONFIRMADO")} />
            <XCircle size={20} />
            <span>
              <strong>Não confirmado</strong>
              <small className="texto-suave">Pode ser reaberto depois</small>
            </span>
          </label>
        </div>
        {itens && status === "CONFIRMADO" && (
          <div className="aviso-etapa" role="note">
            <PackageCheck size={18} />
            <p>
              Ofício de <strong>{tipos.rotulo(oficio.tipo)}</strong>: depois da resposta confirmada, ele fica{" "}
              <strong>pendente de recebimento</strong> até a entrega ser confirmada.
            </p>
          </div>
        )}
        <Campo rotulo="Data da resposta *">
          {(id) => (
            <input id={id} type="date" className="input" required value={dataResposta}
              min={oficio.inicio_prazo} max={hojeIso()} onChange={(e) => setDataResposta(e.target.value)} />
          )}
        </Campo>
        <div className="campo">
          <span className="rotulo">
            Documento de resposta <small className="texto-suave">(opcional · fica como evidência)</small>
          </span>
          <SeletorArquivo arquivo={evidencia} aoEscolher={setEvidencia} rotulo="Anexar evidência da resposta" compacto />
        </div>
        <Campo rotulo="Observação">
          {(id) => (
            <textarea id={id} className="input" rows={3} maxLength={500} value={observacao}
              onChange={(e) => setObservacao(e.target.value)} />
          )}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Registrar</Botao>
        </div>
      </form>
    </Modal>
  );
}

export function ModalRecebimento({ oficio, aoFechar }: { oficio: Detalhe; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const [dataRecebimento, setDataRecebimento] = useState(hojeIso());
  const [observacao, setObservacao] = useState("");
  const [comprovante, setComprovante] = useState<File | null>(null);

  const salvar = useMutation({
    mutationFn: async () => {
      const novo = await ep.alterarStatus(oficio.id, {
        status: "RECEBIDO",
        data_recebimento: dataRecebimento,
        observacao: observacao.trim() || null,
      });
      if (!comprovante) return { novo, falha: null };
      // O recebimento já está gravado; se o arquivo falhar, dá para anexar depois pelo histórico.
      const evento = novo.historico[novo.historico.length - 1];
      try {
        await ep.enviarAnexo(oficio.id, "RECEBIMENTO", comprovante, evento.id);
        return { novo: null, falha: null };
      } catch (e) {
        return { novo, falha: e instanceof Error ? e.message : "erro" };
      }
    },
    onSuccess: ({ novo, falha }) => {
      atualizar(novo ?? undefined);
      if (falha) {
        avisar(`Recebimento confirmado, mas o comprovante não foi enviado (${falha}). Anexe pelo histórico.`, "erro");
      } else {
        avisar(`Recebimento confirmado${comprovante ? ", com comprovante de entrega" : ""}. Ofício concluído.`);
      }
      aoFechar();
    },
  });

  return (
    <Modal titulo="Confirmar recebimento" aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <p>
          A resposta foi confirmada em <strong>{data(oficio.data_resposta)}</strong>. Confirme a entrega (dos itens
          ou do serviço) para concluir o ofício como <strong>recebido</strong> (definitivo).
        </p>
        <Campo rotulo="Data do recebimento *">
          {(id) => (
            <input id={id} type="date" className="input" required value={dataRecebimento}
              min={oficio.data_resposta ?? undefined} max={hojeIso()}
              onChange={(e) => setDataRecebimento(e.target.value)} />
          )}
        </Campo>
        <div className="campo">
          <span className="rotulo">
            Comprovante de entrega <small className="texto-suave">(opcional · canhoto, termo, nota, relatório, foto…)</small>
          </span>
          <SeletorArquivo arquivo={comprovante} aoEscolher={setComprovante} rotulo="Anexar evidência da entrega"
            compacto />
        </div>
        <Campo rotulo="Observação">
          {(id) => (
            <textarea id={id} className="input" rows={3} maxLength={500} value={observacao}
              onChange={(e) => setObservacao(e.target.value)}
              placeholder="Ex.: entregue no almoxarifado, conferido por…" />
          )}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}><PackageCheck size={16} /> Confirmar recebimento</Botao>
        </div>
      </form>
    </Modal>
  );
}

export function ModalReabrir({ oficio, aoFechar }: { oficio: Detalhe; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const [observacao, setObservacao] = useState("");
  const salvar = useMutation({
    mutationFn: () =>
      ep.alterarStatus(oficio.id, { status: "PENDENTE_RESPOSTA", observacao: observacao.trim() || null }),
    onSuccess: (novo) => {
      atualizar(novo);
      avisar("Ofício reaberto. O prazo recomeçou hoje.");
      aoFechar();
    },
  });

  return (
    <Modal titulo="Reabrir ofício" aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <p>
          O ofício volta para <strong>pendente de resposta</strong> e a contagem de dias úteis
          <strong> recomeça do zero hoje</strong>. A resposta anterior e sua evidência continuam no histórico.
        </p>
        <Campo rotulo="Motivo / observação">
          {(id) => (
            <textarea id={id} className="input" rows={3} maxLength={500} value={observacao}
              onChange={(e) => setObservacao(e.target.value)} placeholder="Ex.: ofício reenviado ao órgão" />
          )}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}><RotateCcw size={16} /> Reabrir</Botao>
        </div>
      </form>
    </Modal>
  );
}
