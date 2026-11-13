import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { abrirChamado, listarEmpresas, responderChamado } from "../../api/endpoints";
import { SeletorArquivo } from "../../components/SeletorArquivo";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox } from "../../components/ui";
import { agoraLocal } from "../../utils/manutencao";

/** Abertura de chamado (operacional ou administrador). */
export function ChamadoNovo() {
  const navegar = useNavigate();
  const avisar = useToast();
  const queryClient = useQueryClient();
  const empresas = useQuery({ queryKey: ["empresas-manutencao", "ativas"], queryFn: () => listarEmpresas(true) });

  const [empresaId, setEmpresaId] = useState<number | "">("");
  const [titulo, setTitulo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [local, setLocal] = useState("");
  const [equipamento, setEquipamento] = useState("");
  const [ocorrido, setOcorrido] = useState(agoraLocal());
  const [arquivo, setArquivo] = useState<File | null>(null);

  const salvar = useMutation({
    mutationFn: async () => {
      const criado = await abrirChamado({
        empresa_id: Number(empresaId), titulo: titulo.trim(), descricao: descricao.trim(),
        local: local.trim() || null, equipamento: equipamento.trim() || null, ocorrido_em: ocorrido || null,
      });
      // A foto ou documento do problema entra como o primeiro comentário do chamado
      if (arquivo) await responderChamado(criado.id, { texto: "Arquivo enviado na abertura do chamado.", arquivo });
      return criado;
    },
    onSuccess: (c) => {
      queryClient.invalidateQueries({ queryKey: ["chamados"] });
      queryClient.invalidateQueries({ queryKey: ["manutencao-painel"] });
      avisar(`Chamado ${c.codigo} aberto para ${c.empresa.nome}.`);
      navegar(`/manutencao/chamados/${c.id}`);
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    salvar.mutate();
  }

  if (empresas.isPending) return <Carregando />;
  if (empresas.isError) return <ErroBox erro={empresas.error} />;
  const empresa = empresas.data.find((x) => x.id === empresaId);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <Link to="/manutencao/chamados" className="voltar"><ArrowLeft size={16} /> Chamados</Link>
          <h1>Abrir chamado</h1>
          <p className="texto-suave">Descreva o problema. O técnico da empresa escolhida tem um prazo em horas úteis para o diagnóstico.</p>
        </div>
      </header>

      <form className="cartao formulario" onSubmit={enviar}>
        <div className="grade-2">
          <Campo rotulo="Empresa / modalidade *"
            dica={empresa ? `Prazo para o diagnóstico: ${empresa.prazo_horas} h úteis.` : "Quem vai atender o chamado."}>
            {(id) => (
              <select id={id} className="input" required value={empresaId}
                onChange={(e) => setEmpresaId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Escolha a empresa</option>
                {empresas.data.map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}
              </select>
            )}
          </Campo>
          <Campo rotulo="Data e hora do problema *" dica="Quando o problema aconteceu ou foi percebido.">
            {(id) => <input id={id} className="input" type="datetime-local" required max={agoraLocal()} value={ocorrido}
              onChange={(e) => setOcorrido(e.target.value)} />}
          </Campo>
        </div>
        <Campo rotulo="Título *" dica="Um resumo curto. Ex.: Monitor do leito 4 sem imagem">
          {(id) => <input id={id} className="input" required minLength={3} maxLength={150} value={titulo}
            onChange={(e) => setTitulo(e.target.value)} />}
        </Campo>
        <Campo rotulo="Descrição do problema *" dica="O que aconteceu, desde quando, o que já foi tentado.">
          {(id) => <textarea id={id} className="input" required minLength={5} maxLength={5000} rows={6} value={descricao}
            onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        <div className="grade-2">
          <Campo rotulo="Local / setor">
            {(id) => <input id={id} className="input" maxLength={120} placeholder="Ex.: UTI adulto, leito 4" value={local}
              onChange={(e) => setLocal(e.target.value)} />}
          </Campo>
          <Campo rotulo="Equipamento">
            {(id) => <input id={id} className="input" maxLength={120} placeholder="Ex.: Monitor multiparamétrico" value={equipamento}
              onChange={(e) => setEquipamento(e.target.value)} />}
          </Campo>
        </div>
        <SeletorArquivo arquivo={arquivo} aoEscolher={setArquivo} rotulo="Foto ou documento do problema (opcional)" compacto />
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <Link to="/manutencao/chamados" className="btn btn-secundario">Cancelar</Link>
          <Botao type="submit" carregando={salvar.isPending}>Abrir chamado</Botao>
        </div>
      </form>
    </>
  );
}
