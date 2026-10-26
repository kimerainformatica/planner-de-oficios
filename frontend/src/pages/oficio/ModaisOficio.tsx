// Editar e excluir o ofício, e o pedido de exclusão do cliente.
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PackageCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import * as ep from "../../api/endpoints";
import { CamposDestinatario, SeletorTipo } from "../../components/CamposOficio";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Modal } from "../../components/ui";
import type { Destinatario, OficioDetalhe as Detalhe, SolicitacaoExclusao, TipoOficio } from "../../types";
import { dataHora, hojeIso } from "../../utils/formato";
import { useTipos } from "../../utils/tipos";
import { useAtualizarOficio } from "./comum";

export function ModalEditar({ oficio, aoFechar }: { oficio: Detalhe; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const { exigeEntrega } = useTipos();
  const [numero, setNumero] = useState(oficio.numero);
  const [dataOficio, setDataOficio] = useState(oficio.data_oficio);
  const [protocolo, setProtocolo] = useState(oficio.protocolo ?? "");
  const [tipo, setTipo] = useState<TipoOficio | "">(oficio.tipo ?? "");
  const [destinatario, setDestinatario] = useState<Destinatario | "">(oficio.destinatario_tipo ?? "");
  const [setor, setSetor] = useState(oficio.destinatario_setor ?? "");
  const [observacao, setObservacao] = useState(oficio.observacao ?? "");
  // Resposta já confirmada: trocar entre tipo com e sem recebimento muda o status (ver ajustar_etapa_recebimento)
  const confirmado = ["CONFIRMADO", "PENDENTE_RECEBIMENTO", "RECEBIDO"].includes(oficio.status);
  const mudaEtapa = confirmado && tipo !== "" && exigeEntrega(tipo) !== exigeEntrega(oficio.tipo);

  const salvar = useMutation({
    mutationFn: () =>
      ep.atualizarOficio(oficio.id, {
        numero: numero.trim(),
        data_oficio: dataOficio,
        tipo: tipo as TipoOficio,
        protocolo: protocolo.trim() || null,
        destinatario_tipo: destinatario || null,
        destinatario_setor: destinatario ? setor.trim() : null,
        observacao: observacao.trim() || null,
      }),
    onSuccess: (novo) => {
      atualizar(novo);
      avisar("Dados atualizados.");
      aoFechar();
    },
  });

  return (
    <Modal titulo={`Editar ofício nº ${oficio.numero}`} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); salvar.mutate(); }}>
        <div className="grade-2">
          <Campo rotulo="Número *">
            {(id) => <input id={id} className="input" required maxLength={30} value={numero}
              onChange={(e) => setNumero(e.target.value)} />}
          </Campo>
          <Campo rotulo="Data do ofício *">
            {(id) => <input id={id} type="date" className="input" required max={hojeIso()} value={dataOficio}
              onChange={(e) => setDataOficio(e.target.value)} />}
          </Campo>
        </div>
        <div className="grade-2">
          <SeletorTipo valor={tipo} aoMudar={setTipo} obrigatorio />
          <Campo rotulo="Protocolo" dica="Opcional">
            {(id) => <input id={id} className="input" maxLength={50} value={protocolo}
              onChange={(e) => setProtocolo(e.target.value)} />}
          </Campo>
        </div>
        {mudaEtapa && (
          <div className="aviso-etapa" role="note">
            <PackageCheck size={18} />
            <p>
              {exigeEntrega(tipo)
                ? <>Com este tipo, o ofício passa a <strong>aguardar a confirmação do recebimento</strong>.</>
                : <>Este tipo não exige recebimento: o ofício passa a <strong>Confirmado</strong> (o histórico é mantido).</>}
            </p>
          </div>
        )}
        <CamposDestinatario tipo={destinatario} setor={setor} aoMudarTipo={setDestinatario} aoMudarSetor={setSetor} />
        <Campo rotulo="Observação">
          {(id) => <textarea id={id} className="input" rows={3} maxLength={5000} value={observacao}
            onChange={(e) => setObservacao(e.target.value)} />}
        </Campo>
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>Salvar</Botao>
        </div>
      </form>
    </Modal>
  );
}

export function ModalExcluir({ oficio, aoFechar }: { oficio: Detalhe; aoFechar: () => void }) {
  const avisar = useToast();
  const navegar = useNavigate();
  const queryClient = useQueryClient();
  const excluir = useMutation({
    mutationFn: () => ep.excluirOficio(oficio.id),
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ["oficio", oficio.id] });
      for (const chave of ["oficios", "resumo", "analise"]) queryClient.invalidateQueries({ queryKey: [chave] });
      avisar(`Ofício nº ${oficio.numero} excluído.`);
      navegar("/oficios");
    },
  });

  return (
    <Modal
      titulo="Excluir ofício"
      aoFechar={aoFechar}
      rodape={
        <>
          <button className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao className="btn btn-perigo" carregando={excluir.isPending} onClick={() => excluir.mutate()}>
            <Trash2 size={16} /> Excluir definitivamente
          </Botao>
        </>
      }
    >
      <p>
        O ofício nº <strong>{oficio.numero}</strong>
        {oficio.protocolo && <> (protocolo {oficio.protocolo})</>}, seus documentos e evidências anexados e todo
        o histórico serão apagados. Esta ação não pode ser desfeita.
      </p>
      {excluir.isError && <div className="alerta-erro">{excluir.error.message}</div>}
    </Modal>
  );
}

export function AvisoExclusao({
  oficioId,
  pedido,
  ehAdmin,
  podeCancelar,
  aoDecidir,
}: {
  oficioId: number;
  pedido: SolicitacaoExclusao;
  ehAdmin: boolean;
  podeCancelar: boolean;
  aoDecidir: (acao: "aprovar" | "recusar") => void;
}) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficioId);
  const queryClient = useQueryClient();
  const cancelar = useMutation({
    mutationFn: () => ep.cancelarExclusao(oficioId),
    onSuccess: () => {
      atualizar();
      queryClient.invalidateQueries({ queryKey: ["exclusoes"] });
      queryClient.invalidateQueries({ queryKey: ["exclusoes-pendentes"] });
      avisar("Pedido de exclusão cancelado.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  return (
    <section className="aviso-exclusao" role="status">
      <div>
        <strong>Exclusão solicitada</strong> por {pedido.solicitante_nome} em {dataHora(pedido.criado_em)} — aguardando
        um administrador.
        <p className="texto-suave">Motivo: {pedido.motivo}</p>
      </div>
      <div className="grupo">
        {podeCancelar && !ehAdmin && (
          <Botao className="btn btn-secundario btn-pequeno" carregando={cancelar.isPending} onClick={() => cancelar.mutate()}>
            Cancelar pedido
          </Botao>
        )}
        {ehAdmin && (
          <>
            <button className="btn btn-secundario btn-pequeno" onClick={() => aoDecidir("recusar")}>Recusar</button>
            <button className="btn btn-perigo btn-pequeno" onClick={() => aoDecidir("aprovar")}>Aprovar e excluir</button>
          </>
        )}
      </div>
    </section>
  );
}

export function ModalPedirExclusao({ oficio, aoFechar }: { oficio: Detalhe; aoFechar: () => void }) {
  const avisar = useToast();
  const atualizar = useAtualizarOficio(oficio.id);
  const queryClient = useQueryClient();
  const [motivo, setMotivo] = useState("");
  const pedir = useMutation({
    mutationFn: () => ep.solicitarExclusao(oficio.id, motivo.trim()),
    onSuccess: () => {
      atualizar();
      queryClient.invalidateQueries({ queryKey: ["exclusoes"] });
      avisar("Pedido enviado. Um administrador vai analisar a exclusão.");
      aoFechar();
    },
  });
  return (
    <Modal titulo="Solicitar exclusão" aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e) => { e.preventDefault(); pedir.mutate(); }}>
        <p>
          A exclusão do ofício nº <strong>{oficio.numero}</strong> precisa ser aprovada por um administrador. Até lá,
          o ofício continua ativo normalmente.
        </p>
        <Campo rotulo="Motivo da exclusão *" dica="Mínimo de 5 caracteres">
          {(id) => (
            <textarea id={id} className="input" rows={3} required minLength={5} maxLength={1000} value={motivo}
              onChange={(e) => setMotivo(e.target.value)} placeholder="Ex.: cadastrado em duplicidade" autoFocus />
          )}
        </Campo>
        {pedir.isError && <div className="alerta-erro">{pedir.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" className="btn btn-perigo" carregando={pedir.isPending}>Enviar pedido</Botao>
        </div>
      </form>
    </Modal>
  );
}
