import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import logo from "../assets/acqua-logo.svg";
import { CHAVE_SESSAO_ENCERRADA, useAuth } from "../auth/AuthContext";
import { SeletorTema } from "../components/SeletorTema";
import { Botao, Campo } from "../components/ui";

export function Login() {
  const { usuario, entrar } = useAuth();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [encerrada] = useState(() => {
    try {
      const v = sessionStorage.getItem(CHAVE_SESSAO_ENCERRADA) === "1";
      sessionStorage.removeItem(CHAVE_SESSAO_ENCERRADA);
      return v;
    } catch {
      return false;
    }
  });

  if (usuario) return <Navigate to="/" replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await entrar(login.trim(), senha);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível entrar");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login-fundo">
      <div className="login-tema">
        <SeletorTema compacto />
      </div>
      <form className="login-cartao" onSubmit={enviar}>
        <div className="login-marca">
          <img src={logo} alt="Instituto ACQUA" />
          <div>
            <h1>Planner de Ofícios</h1>
            <p className="texto-suave">Entre com seu usuário</p>
          </div>
        </div>
        <Campo rotulo="Usuário">
          {(id) => (
            <input id={id} className="input" autoComplete="username" autoFocus required value={login}
              onChange={(e) => setLogin(e.target.value)} />
          )}
        </Campo>
        <Campo rotulo="Senha">
          {(id) => (
            <input id={id} className="input" type="password" autoComplete="current-password" required
              value={senha} onChange={(e) => setSenha(e.target.value)} />
          )}
        </Campo>
        {encerrada && !erro && (
          <div className="alerta-info" role="status">
            Sua sessão foi encerrada (a senha foi alterada ou o tempo de acesso acabou). Entre novamente.
          </div>
        )}
        {erro && <div className="alerta-erro">{erro}</div>}
        <Botao type="submit" carregando={enviando} className="btn btn-primario btn-largo">
          Entrar
        </Botao>
      </form>
    </div>
  );
}
