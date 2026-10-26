// Correções do admin/master: resposta, recebimento e desfazer.
import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Undo2, XCircle } from "lucide-react";
import { useState } from "react";
import * as ep from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Modal } from "../../components/ui";
import type { Historico, OficioDetalhe as Detalhe } from "../../types";
import { data, hojeIso } from "../../utils/formato";
import { useTipos } from "../../utils/tipos";
import { useAtualizarOficio } from "./comum";

export function ModalCorrigirResposta({ oficio, evento, aoFechar }: { oficio: Detalhe; evento: Historico; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const [confirmada, setConfirmada] = useState(evento.status_novo !== "NAO_CONFIRMADO");
  const [dataResposta, setDataResposta] = useState(oficio.data_resposta ?? hojeIso());
  const [observacao, setObservacao] = useState(evento.observacao ?? "");
  const recebido = oficio.status === "RECEBIDO";
  const itens = useTipos().exigeEntrega(oficio.tipo);

  const salvar = useMutation({
    mutationFn: () =>
      ep.corrigirResposta(oficio.id, {
        status: confirmada ? "CONFIRMADO" : "NAO_CONFIRMADO",
        data_resposta: dataResposta,
        observacao: observacao.trim() || null,
      }),
    onSuccess: (novo) => {
      atualizar(novo);
      avisar("Resposta corrigida.");
      aoFechar();
    },
  });

  return (
    <Modal titulo="Corrigir resposta" aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <div className="opcoes-status">
          <label className={`opcao ${confirmada ? "selecionada opcao-confirmado" : ""}`}>
            <input type="radio" name="resultado" checked={confirmada} disabled={recebido}
              onChange={() => setConfirmada(true)} />
            <CheckCircle2 size={20} />
            <span>
              <strong>Confirmado</strong>
              <small className="texto-suave">{itens ? "Aguarda o recebimento" : "Encerra o ofício"}</small>
            </span>
          </label>
          <label className={`opcao ${!confirmada ? "selecionada opcao-nao-confirmado" : ""}`}>
            <input type="radio" name="resultado" checked={!confirmada} disabled={recebido}
              onChange={() => setConfirmada(false)} />
            <XCircle size={20} />
            <span>
              <strong>Não confirmado</strong>
              <small className="texto-suave">Pode ser reaberto depois</small>
            </span>
          </label>
        </div>
        {recebido ? (
          <p className="texto-suave">
            Os itens já foram recebidos: para mudar o resultado, desfaça o recebimento antes.
          </p>
        ) : (
          confirmada !== (evento.status_novo !== "NAO_CONFIRMADO") && (
            <div className="aviso-etapa" role="note">
              <Undo2 size={18} />
              <p>
                A resposta atual fica no histórico como <strong>desfeita</strong> e a corrigida é registrada no lugar,
                levando a evidência junto.
              </p>
            </div>
          )
        )}
        <Campo rotulo="Data da resposta *">
          {(id) => (
            <input id={id} type="date" className="input" required value={dataResposta} min={oficio.inicio_prazo}
              max={oficio.data_recebimento ?? hojeIso()} onChange={(e) => setDataResposta(e.target.value)} />
          )}
        </Campo>
        <Campo rotulo="Observação">
          {(id) => (
            <textarea id={id} className="input" rows={3} maxLength={500} value={observacao}
              onChange={(e) => setObservacao(e.target.value)} />
          )}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Salvar correção</Botao>
        </div>
      </form>
    </Modal>
  );
}

export function ModalCorrigirRecebimento({
  oficio,
  evento,
  aoFechar,
}: {
  oficio: Detalhe;
  evento: Historico;
  aoFechar: () => void;
}) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const [dataRecebimento, setDataRecebimento] = useState(oficio.data_recebimento ?? hojeIso());
  const [observacao, setObservacao] = useState(evento.observacao ?? "");

  const salvar = useMutation({
    mutationFn: () =>
      ep.corrigirRecebimento(oficio.id, { data_recebimento: dataRecebimento, observacao: observacao.trim() || null }),
    onSuccess: (novo) => {
      atualizar(novo);
      avisar("Recebimento corrigido.");
      aoFechar();
    },
  });

  return (
    <Modal titulo="Corrigir recebimento" aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <Campo rotulo="Data do recebimento *">
          {(id) => (
            <input id={id} type="date" className="input" required value={dataRecebimento}
              min={oficio.data_resposta ?? undefined} max={hojeIso()}
              onChange={(e) => setDataRecebimento(e.target.value)} />
          )}
        </Campo>
        <Campo rotulo="Observação">
          {(id) => (
            <textarea id={id} className="input" rows={3} maxLength={500} value={observacao}
              onChange={(e) => setObservacao(e.target.value)} />
          )}
        </Campo>
        <p className="texto-suave">O comprovante de entrega pode ser substituído ou removido no histórico.</p>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Salvar correção</Botao>
        </div>
      </form>
    </Modal>
  );
}

export function ModalDesfazer({ oficio, aoFechar }: { oficio: Detalhe; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const [motivo, setMotivo] = useState("");
  const recebimento = oficio.status === "RECEBIDO";

  const desfazer = useMutation({
    mutationFn: () => ep.desfazerEtapa(oficio.id, motivo.trim()),
    onSuccess: (novo) => {
      atualizar(novo);
      avisar(recebimento ? "Recebimento desfeito: o ofício voltou a aguardar a entrega." :
        "Resposta desfeita: o ofício voltou a aguardar resposta.");
      aoFechar();
    },
  });

  return (
    <Modal titulo={recebimento ? "Desfazer recebimento" : "Desfazer resposta"} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); desfazer.mutate(); }}>
        <p>
          {recebimento ? (
            <>O ofício volta para <strong>pendente de recebimento</strong>. A resposta continua valendo.</>
          ) : (
            <>
              O ofício volta para <strong>pendente de resposta</strong>. O prazo <strong>não</strong> recomeça: continua
              contando de {data(oficio.inicio_prazo)}.
            </>
          )}{" "}
          O registro desfeito e sua evidência continuam visíveis no histórico, marcados como desfeitos.
        </p>
        <Campo rotulo="Motivo *" dica="Mínimo de 5 caracteres · fica no histórico">
          {(id) => (
            <textarea id={id} className="input" rows={3} required minLength={5} maxLength={500} value={motivo}
              onChange={(e) => setMotivo(e.target.value)} autoFocus
              placeholder={recebimento ? "Ex.: os itens ainda não chegaram" : "Ex.: resposta lançada no ofício errado"} />
          )}
        </Campo>
        {desfazer.isError && <div className="alerta-erro">{desfazer.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" className="btn btn-perigo" carregando={desfazer.isPending}>
            <Undo2 size={16} /> Desfazer
          </Botao>
        </div>
      </form>
    </Modal>
  );
}
