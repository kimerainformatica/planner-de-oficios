import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { criarOficio, enviarAnexo } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { CamposDestinatario, SeletorTipo } from "../components/CamposOficio";
import { SeletorArquivo } from "../components/SeletorArquivo";
import { SeletorCliente } from "../components/SeletorCliente";
import { useToast } from "../components/Toast";
import { Botao, Campo } from "../components/ui";
import type { Destinatario, TipoOficio } from "../types";
import { hojeIso } from "../utils/formato";

export function OficioNovo() {
  const { ehAdmin } = useAuth();
  const avisar = useToast();
  const navegar = useNavigate();
  const queryClient = useQueryClient();

  const [numero, setNumero] = useState("");
  const [dataOficio, setDataOficio] = useState(hojeIso());
  const [protocolo, setProtocolo] = useState("");
  const [tipo, setTipo] = useState<TipoOficio | "">("");
  const [destinatario, setDestinatario] = useState<Destinatario | "">("");
  const [setor, setSetor] = useState("");
  const [observacao, setObservacao] = useState("");
  const [donoId, setDonoId] = useState<number | undefined>();
  const [docOficio, setDocOficio] = useState<File | null>(null);
  const [docReferencia, setDocReferencia] = useState<File | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const salvar = useMutation({
    mutationFn: async () => {
      const oficio = await criarOficio({
        numero: numero.trim(),
        data_oficio: dataOficio,
        tipo: tipo as TipoOficio,
        protocolo: protocolo.trim() || null,
        destinatario_tipo: destinatario || null,
        destinatario_setor: destinatario ? setor.trim() : null,
        observacao: observacao.trim() || null,
        dono_id: donoId ?? null,
      });
      // O ofício já existe; se um anexo falhar, ainda dá para reenviar na tela de detalhe.
      const falhas: string[] = [];
      for (const [tipo, arquivo] of [
        ["OFICIO", docOficio],
        ["REFERENCIA", docReferencia],
      ] as const) {
        if (!arquivo) continue;
        try {
          await enviarAnexo(oficio.id, tipo, arquivo);
        } catch (e) {
          falhas.push(`${arquivo.name}: ${e instanceof Error ? e.message : "erro"}`);
        }
      }
      return { oficio, falhas };
    },
    onSuccess: ({ oficio, falhas }) => {
      queryClient.invalidateQueries({ queryKey: ["oficios"] });
      queryClient.invalidateQueries({ queryKey: ["resumo"] });
      if (falhas.length) avisar(`Ofício salvo, mas um anexo falhou — ${falhas.join("; ")}`, "erro");
      else avisar(`Ofício nº ${oficio.numero} cadastrado como pendente de resposta.`);
      navegar(`/oficios/${oficio.id}`);
    },
    onError: (e) => setErro(e.message),
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    salvar.mutate();
  }

  return (
    <>
      <header className="pagina-topo">
        <div>
          <Link to="/oficios" className="link voltar">
            <ArrowLeft size={16} /> Ofícios
          </Link>
          <h1>Novo ofício</h1>
          <p className="texto-suave">Todo ofício novo entra como pendente de resposta.</p>
        </div>
      </header>

      <form className="cartao formulario" onSubmit={enviar}>
        <div className="grade-3">
          <Campo rotulo="Número do ofício *">
            {(id) => (
              <input id={id} className="input" required maxLength={30} value={numero}
                onChange={(e) => setNumero(e.target.value)} placeholder="Ex.: 123/2026" autoFocus />
            )}
          </Campo>
          <Campo rotulo="Data do ofício *">
            {(id) => (
              <input id={id} type="date" className="input" required max={hojeIso()} value={dataOficio}
                onChange={(e) => setDataOficio(e.target.value)} />
            )}
          </Campo>
          <Campo rotulo="Protocolo" dica="Opcional">
            {(id) => (
              <input id={id} className="input" maxLength={50} value={protocolo}
                onChange={(e) => setProtocolo(e.target.value)} />
            )}
          </Campo>
        </div>

        <div className="grade-2">
          <SeletorTipo valor={tipo} aoMudar={setTipo} obrigatorio />
          <CamposDestinatario tipo={destinatario} setor={setor} aoMudarTipo={setDestinatario} aoMudarSetor={setSetor} />
        </div>

        {ehAdmin && (
          <Campo rotulo="Cliente" dica="Deixe em branco para cadastrar como seu.">
            {(id) => <SeletorCliente id={id} valor={donoId} aoMudar={setDonoId} rotuloVazio="Eu mesmo" />}
          </Campo>
        )}

        <Campo rotulo="Observação">
          {(id) => (
            <textarea id={id} className="input" rows={3} maxLength={5000} value={observacao}
              onChange={(e) => setObservacao(e.target.value)} />
          )}
        </Campo>

        <div className="grade-2">
          <div className="campo">
            <span className="rotulo">Documento do ofício</span>
            <SeletorArquivo arquivo={docOficio} aoEscolher={setDocOficio} rotulo="Anexar o ofício" />
          </div>
          <div className="campo">
            <span className="rotulo">Documento de referência</span>
            <SeletorArquivo arquivo={docReferencia} aoEscolher={setDocReferencia} rotulo="Anexar referência" />
          </div>
        </div>

        {erro && <div className="alerta-erro">{erro}</div>}

        <div className="acoes-form">
          <Link to="/oficios" className="btn btn-secundario">
            Cancelar
          </Link>
          <Botao type="submit" carregando={salvar.isPending}>
            Cadastrar ofício
          </Botao>
        </div>
      </form>
    </>
  );
}
