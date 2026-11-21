import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { atualizarSetor, criarSetor, excluirSetor, listarSetores } from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../../components/ui";
import type { Setor } from "../../types";

/** Setores da unidade (só o administrador do módulo). As pessoas são ligadas ao setor na tela de usuários. */
export function SetoresTetos() {
  const consulta = useQuery({ queryKey: ["setores-tetos"], queryFn: listarSetores });
  const [modal, setModal] = useState<Setor | "novo" | null>(null);
  const [excluindo, setExcluindo] = useState<Setor | null>(null);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Setores</h1>
          <p className="texto-suave">
            Cada setor tem os seus tipos de teto. Para ligar uma pessoa a um setor, abra <Link to="/usuarios">Usuários</Link> e
            escolha o setor no acesso ao Controle de Tetos.
          </p>
        </div>
        <button className="btn btn-primario" onClick={() => setModal("novo")}><Plus size={18} /> Novo setor</button>
      </header>

      {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : consulta.data.length === 0 ? (
        <div className="aviso-vazio" role="status">Nenhum setor cadastrado. Comece pelo seu, por exemplo Gerência Operacional.</div>
      ) : (
        <div className="tabela-box">
          <table className="tabela tabela-tetos">
            <thead>
              <tr>
                <th>Setor</th>
                <th>Quem lança os gastos</th>
                <th className="num">Tipos de teto</th>
                <th>Situação</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {consulta.data.map((s) => (
                <tr key={s.id} className={s.ativo ? "" : "linha-inativa"}>
                  <td><strong>{s.nome}</strong>{s.descricao && <small className="texto-suave"><br />{s.descricao}</small>}</td>
                  <td>{s.usuarios.length ? s.usuarios.map((u) => u.nome).join(", ") : <span className="texto-suave">Ninguém ainda</span>}</td>
                  <td className="num"><Link to={`/tetos/tipos?setor=${s.id}`}>{s.tipos}</Link></td>
                  <td>{s.ativo ? "Ativo" : "Inativo"}</td>
                  <td className="num">
                    <div className="grupo grupo-fim acoes-linha">
                      <button className="btn btn-fantasma btn-pequeno" onClick={() => setModal(s)}><Pencil size={15} /> Editar</button>
                      {s.tipos === 0 && s.usuarios.length === 0 && (
                        <button className="btn btn-fantasma btn-pequeno btn-perigo" onClick={() => setExcluindo(s)} aria-label={`Excluir ${s.nome}`}>
                          <Trash2 size={15} />
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

      {modal && <ModalSetor setor={modal === "novo" ? null : modal} aoFechar={() => setModal(null)} />}
      {excluindo && <ModalExcluirSetor setor={excluindo} aoFechar={() => setExcluindo(null)} />}
    </>
  );
}

function ModalSetor({ setor, aoFechar }: { setor: Setor | null; aoFechar: () => void }) {
  const avisar = useToast();
  const qc = useQueryClient();
  const [nome, setNome] = useState(setor?.nome ?? "");
  const [descricao, setDescricao] = useState(setor?.descricao ?? "");
  const [ativo, setAtivo] = useState(setor?.ativo ?? true);
  const salvar = useMutation({
    mutationFn: () => setor
      ? atualizarSetor(setor.id, { nome: nome.trim(), descricao: descricao.trim() || null, ativo })
      : criarSetor({ nome: nome.trim(), descricao: descricao.trim() || null }),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ["setores-tetos"] });
      qc.invalidateQueries({ queryKey: ["tetos-painel"] });
      avisar(setor ? `Setor ${s.nome} atualizado.` : `Setor ${s.nome} criado.`);
      aoFechar();
    },
  });
  return (
    <Modal titulo={setor ? `Editar ${setor.nome}` : "Novo setor"} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={(e: FormEvent) => { e.preventDefault(); salvar.mutate(); }}>
        <Campo rotulo="Nome *">
          {(id) => <input id={id} className="input" required minLength={2} maxLength={120} value={nome} autoFocus onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Descrição">
          {(id) => <textarea id={id} className="input" rows={2} maxLength={2000} value={descricao} onChange={(e) => setDescricao(e.target.value)} />}
        </Campo>
        {setor && (
          <label className="checkbox">
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
            Ativo (inativo, sai do painel e não recebe lançamentos; o histórico fica)
          </label>
        )}
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>{setor ? "Salvar" : "Criar setor"}</Botao>
        </div>
      </form>
    </Modal>
  );
}

function ModalExcluirSetor({ setor, aoFechar }: { setor: Setor; aoFechar: () => void }) {
  const avisar = useToast();
  const qc = useQueryClient();
  const excluir = useMutation({
    mutationFn: () => excluirSetor(setor.id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["setores-tetos"] }); avisar(`Setor ${setor.nome} excluído.`); aoFechar(); },
  });
  return (
    <Modal titulo={`Excluir ${setor.nome}`} aoFechar={aoFechar}>
      <p>O setor não tem tipos de teto nem usuários e será excluído.</p>
      {excluir.isError && <div className="alerta-erro">{excluir.error.message}</div>}
      <div className="acoes-form">
        <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
        <Botao className="btn btn-perigo" carregando={excluir.isPending} onClick={() => excluir.mutate()}>Excluir</Botao>
      </div>
    </Modal>
  );
}
