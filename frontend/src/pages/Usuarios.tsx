import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, UserPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { atualizarUsuario, criarUsuario, listarUsuarios } from "../api/endpoints";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Modal } from "../components/ui";
import type { Perfil, Usuario } from "../types";
import { ROTULO_PERFIL } from "../utils/formato";

const CLASSE_PERFIL: Record<Perfil, string> = { MASTER: "badge-master", ADMIN: "badge-admin", CLIENTE: "badge-neutro" };

export function Usuarios() {
  const { usuario: eu, ehMaster } = useAuth();
  // Admin gerencia só clientes; contas de admin/master só o MASTER altera (o próprio usuário sempre pode).
  const podeEditar = (u: Usuario) => ehMaster || u.perfil === "CLIENTE" || u.id === eu?.id;
  const consulta = useQuery({ queryKey: ["usuarios"], queryFn: listarUsuarios });
  const [editando, setEditando] = useState<Usuario | "novo" | null>(null);

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Usuários</h1>
          <p className="texto-suave">
            {ehMaster
              ? "Como MASTER, você gerencia todas as contas, inclusive administradores."
              : "Administradores gerenciam clientes. Contas de administradores são geridas pelo MASTER."}
          </p>
        </div>
        <button className="btn btn-primario" onClick={() => setEditando("novo")}>
          <UserPlus size={18} /> Novo usuário
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
                <th>Nome</th>
                <th>Login</th>
                <th>Perfil</th>
                <th>Situação</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {consulta.data.map((u) => (
                <tr key={u.id} className={u.ativo ? "" : "linha-inativa"}>
                  <td>
                    {u.nome}
                    {u.id === eu?.id && <small className="texto-suave"> (você)</small>}
                  </td>
                  <td>{u.login}</td>
                  <td>
                    <span className={`badge ${CLASSE_PERFIL[u.perfil]}`}>{ROTULO_PERFIL[u.perfil]}</span>
                  </td>
                  <td>{u.ativo ? "Ativo" : "Inativo"}</td>
                  <td className="num">
                    <button className="btn btn-fantasma btn-pequeno" onClick={() => setEditando(u)}
                      disabled={!podeEditar(u)} title={podeEditar(u) ? undefined : "Só o MASTER altera esta conta"}>
                      <Pencil size={15} /> Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editando && (
        <ModalUsuario usuario={editando === "novo" ? null : editando} ehEu={editando !== "novo" && editando.id === eu?.id}
          ehMaster={ehMaster} aoFechar={() => setEditando(null)} />
      )}
    </>
  );
}

function ModalUsuario({
  usuario,
  ehEu,
  ehMaster,
  aoFechar,
}: {
  usuario: Usuario | null;
  ehEu: boolean;
  ehMaster: boolean;
  aoFechar: () => void;
}) {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const [nome, setNome] = useState(usuario?.nome ?? "");
  const [login, setLogin] = useState(usuario?.login ?? "");
  const [senha, setSenha] = useState("");
  const [perfil, setPerfil] = useState<Perfil>(usuario?.perfil ?? "CLIENTE");
  const [ativo, setAtivo] = useState(usuario?.ativo ?? true);

  const salvar = useMutation({
    mutationFn: () =>
      usuario
        ? atualizarUsuario(usuario.id, {
            nome: nome.trim(),
            ...(login.trim() !== usuario.login ? { login: login.trim() } : {}),
            ...(ehEu ? {} : { perfil, ativo }),
            ...(senha ? { senha } : {}),
          })
        : criarUsuario({ nome: nome.trim(), login: login.trim(), senha, perfil }),
    onSuccess: (u) => {
      queryClient.invalidateQueries({ queryKey: ["usuarios"] });
      avisar(usuario ? `Usuário ${u.nome} atualizado.` : `Usuário ${u.nome} criado.`);
      aoFechar();
    },
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    salvar.mutate();
  }

  return (
    <Modal titulo={usuario ? `Editar ${usuario.nome}` : "Novo usuário"} aoFechar={aoFechar}>
      <form className="formulario" onSubmit={enviar}>
        <Campo rotulo="Nome *">
          {(id) => <input id={id} className="input" required maxLength={120} value={nome} autoFocus
            onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Login *"
          dica={usuario ? "Usado para entrar no sistema. Se mudar, avise o usuário (a senha continua a mesma)." : "Letras, números, ponto, hífen ou _"}>
          {(id) => <input id={id} className="input" required minLength={3} maxLength={60} pattern="[A-Za-z0-9._\-]+"
            value={login} onChange={(e) => setLogin(e.target.value)} />}
        </Campo>
        <Campo rotulo={usuario ? "Nova senha" : "Senha *"} dica={usuario ? "Deixe em branco para manter a atual." : "Mínimo de 8 caracteres."}>
          {(id) => <input id={id} className="input" type="password" autoComplete="new-password" minLength={8}
            required={!usuario} value={senha} onChange={(e) => setSenha(e.target.value)} />}
        </Campo>
        <Campo rotulo="Perfil"
          dica={ehEu ? "Você não pode mudar o perfil do próprio usuário." : !ehMaster ? "Só o MASTER cria ou promove administradores." : undefined}>
          {(id) => (
            <select id={id} className="input" value={perfil} disabled={ehEu || !ehMaster}
              onChange={(e) => setPerfil(e.target.value as Perfil)}>
              <option value="CLIENTE">Cliente — faz tudo nos próprios ofícios; exclusão precisa de aprovação</option>
              <option value="ADMIN">Administrador — vê todos os ofícios, exclui e gerencia clientes</option>
              {(ehMaster || perfil === "MASTER") && (
                <option value="MASTER">Master — administrador geral, gerencia também os administradores</option>
              )}
            </select>
          )}
        </Campo>
        {usuario && !ehEu && (
          <label className="checkbox">
            <input type="checkbox" checked={ativo} onChange={(e) => setAtivo(e.target.checked)} />
            Usuário ativo (desmarque para bloquear o acesso)
          </label>
        )}
        {salvar.isError && <div className="alerta-erro">{salvar.error.message}</div>}
        <div className="acoes-form">
          <button type="button" className="btn btn-secundario" onClick={aoFechar}>Cancelar</button>
          <Botao type="submit" carregando={salvar.isPending}>{usuario ? "Salvar" : "Criar usuário"}</Botao>
        </div>
      </form>
    </Modal>
  );
}
