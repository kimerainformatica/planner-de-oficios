import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { atualizarEmpresa, criarEmpresa, excluirEmpresa, listarEmpresas } from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type { EmpresaManutencao } from "../../types";

/** Empresas / modalidades técnicas que atendem os chamados (administrador do módulo). */
export function Empresas() {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const consulta = useQuery({ queryKey: ["empresas-manutencao"], queryFn: () => listarEmpresas() });
  const [editando, setEditando] = useState<EmpresaManutencao | "nova" | null>(null);
  const excluir = useMutation({
    mutationFn: (e: EmpresaManutencao) => excluirEmpresa(e.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["empresas-manutencao"] });
      avisar("Empresa excluída.");
    },
    onError: (e) => avisar(e.message),
  });

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Empresas técnicas</h1>
          <p className="texto-suave">
            Quem atende os chamados. Cada técnico é cadastrado em Usuários e vinculado a uma empresa. O prazo vale para os
            chamados abertos a partir da mudança.
          </p>
        </div>
        <button className="btn btn-primario" onClick={() => setEditando("nova")}>
          <Plus size={18} /> Nova empresa
        </button>
      </header>

      {consulta.isPending ? (
        <Carregando />
      ) : consulta.isError ? (
        <ErroBox erro={consulta.error} />
      ) : (
        <div className="tabela-box">
          <table className="tabela">
            <thead>
              <tr>
                <th>Empresa / modalidade</th>
                <th className="num">Prazo do diagnóstico</th>
                <th className="num">Técnicos</th>
                <th className="num">Chamados</th>
                <th>Situação</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {consulta.data.map((e) => (
                <tr key={e.id} className={e.ativo ? "" : "linha-inativa"}>
                  <td>
                    {e.nome}
                    {e.descricao && <small className="celula-sub">{e.descricao}</small>}
                  </td>
                  <td className="num">{e.prazo_horas} h corridas</td>
                  <td className="num">{e.tecnicos}</td>
                  <td className="num">{e.chamados}</td>
                  <td>{e.ativo ? "Ativa" : "Inativa"}</td>
                  <td className="num">
                    <div className="grupo grupo-fim">
                      <button className="btn btn-fantasma btn-pequeno" onClick={() => setEditando(e)}>
                        <Pencil size={15} /> Editar
                      </button>
                      {e.chamados === 0 && e.tecnicos === 0 && (
                        <button className="btn btn-fantasma btn-pequeno" disabled={excluir.isPending}
                          onClick={() => window.confirm(`Excluir a empresa ${e.nome}?`) && excluir.mutate(e)}>
                          <Trash2 size={15} /> Excluir
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && <ModalEmpresa empresa={editando === "nova" ? null : editando} aoFechar={() => setEditando(null)} />}
    </>
  );
}

function ModalEmpresa({ empresa, aoFechar }: { empresa: EmpresaManutencao | null; aoFechar: () => void }) {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const [nome, setNome] = useState(empresa?.nome ?? "");
  const [descricao, setDescricao] = useState(empresa?.descricao ?? "");
  const [prazo, setPrazo] = useState(empresa?.prazo_horas ?? 24);
  const [ativo, setAtivo] = useState(empresa?.ativo ?? true);
  const salvar = useMutation({
    mutationFn: () => {
      const dados = { nome: nome.trim(), descricao: descricao.trim() || null, prazo_horas: prazo };
      return empresa ? atualizarEmpresa(empresa.id, { ...dados, ativo }) : criarEmpresa(dados);
    },
    onSuccess: (e) => {
      queryClient.invalidateQueries({ queryKey: ["empresas-manutencao"] });
      avisar(empresa ? `Empresa ${e.nome} atualizada.` : `Empresa ${e.nome} cadastrada.`);
      aoFechar();
    },
  });

  function enviar(ev: FormEvent) {
    ev.preventDefault();
    salvar.mutate();
  }

  return (
    <Modal titulo={empresa ? `Editar ${empresa.nome}` : "Nova empresa"} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={enviar}>
        <Campo rotulo="Nome *" dica="Ex.: MSI, REALIZA PREDIAL, REALIZA CLIMATIZAÇÃO">
          {(id) => <input id={id} className="input" required minLength={2} maxLength={80} autoFocus value={nome}
            onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Descrição" dica="O que a empresa atende (opcional).">
          {(id) => <input id={id} className="input" maxLength={200} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        <Campo rotulo="Prazo para o diagnóstico (horas corridas) *"
          dica="Contadas da abertura, com noites, fins de semana e feriados (24 = 1 dia). Vale para os chamados abertos a partir de agora.">
          {(id) => <input id={id} className="input" type="number" required min={1} max={720} value={prazo}
            onChange={(e) => setPrazo(Number(e.target.value))} />}
        </Campo>
        {empresa && (
          <label className="checkbox">
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
            Ativa (desmarque para não receber chamados novos)
          </label>
        )}
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>{empresa ? "Salvar" : "Cadastrar"}</Botao>
        </div>
      </form>
    </Modal>
  );
}
