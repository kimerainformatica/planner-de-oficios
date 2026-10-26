import { AlertTriangle, ArrowRight, Info } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import logo from "../assets/acqua-logo.svg";
import { CHAVE_SESSAO_ENCERRADA, useAuth } from "../auth/AuthContext";
import { SeletorTema } from "../components/SeletorTema";

// Símbolo do Instituto ACQUA (o mesmo de public/favicon.svg), desenhado aqui para poder ser animado:
// a onda se desenha, a gota cai e solta anéis de água.
const ONDA =
  "M0 0C-18.342-10.598-37.091-22.418-61.547-54.21-85.595-86.41-101.899-125.946-108.012-157.331-116.98-123.908-130.023-94.562-147.549-69.698-71.329-10.598-34.646-2.038-.408 1.63 .815 2.038 .815 .407 0 0M-218.47-145.919C-222.953-143.473-227.437-141.028-231.92-137.767-218.47-127.577-202.982-114.534-184.64-99.453L-161.407-80.296C-144.695-104.752-132.875-132.061-124.724-170.781-156.924-168.743-190.754-160.999-218.47-145.919M15.897 13.043C-43.612 11.82-86.41-4.483-156.924-57.064-161.407-51.765-165.891-46.059-170.374-41.167-184.559-26.062-200.225-15.087-215.722-8.016-215.76-9.236-215.933-10.47-216.291-11.696-217.156-14.661-218.873-17.144-221.095-18.964-208.832-26.408-196.587-36.686-185.455-49.319-180.156-55.433-175.265-61.547-170.781-67.661-177.711-72.552-184.64-78.258-191.977-83.964-212.764-100.676-230.29-115.349-246.187-127.577-288.576-93.339-311.809-41.983-291.837-17.935-281.06-5.162-264.023-2.574-245.188-8.07-245.24-6.541-245.064-4.98-244.612-3.432-244.199-2.017-243.587-.714-242.824 .463-265.025 4.181-284.616-.778-295.912-13.858-320.368-42.798-293.875-95.784-249.855-130.838-275.961-151.371-295.336-166.143-317.375-172.556-329.828-175.296-344.453-176.785-359.216-174.417-361.368-174.071-363.357-175.528-363.7-177.66-364.041-179.794-362.589-181.801-360.456-182.143-354.783-183.053-349.165-183.446-343.679-183.446-325.816-183.446-309.428-179.271-297.606-175.159-277.238-168.786-257.749-157.727-235.996-141.028-231.106-144.288-226.214-147.142-220.915-149.994-191.569-165.484-156.924-173.228-123.908-175.265L-121.463-188.716C-121.463-188.716-108.827-184.64-108.42-182.195L-108.012-175.673C-81.519-175.673-56.655-172.412-37.091-165.891-34.238-165.075-33.423-164.26-33.83-162.63-34.238-160.999-35.461-160.999-38.313-162.222-56.248-167.929-80.703-171.597-107.197-171.597-95.784-120.648-78.666-84.779-58.693-57.878-43.205-37.091-26.086-22.011-8.56-9.782 7.337 1.63 21.194 1.63 20.787 4.483 20.38 7.744 19.564 13.043 15.897 13.043";
const GOTA =
  "M0 0C-1.656-5.674-7.598-8.932-13.272-7.277-18.947-5.621-22.204 .321-20.549 5.996-18.893 11.67-12.951 14.928-7.277 13.272-1.602 11.617 1.656 5.674 0 0";
const ONDA_FUNDO = "M0 60 C240 20 480 20 720 60 S1200 100 1440 60 S1920 20 2160 60 S2640 100 2880 60 V120 H0Z";

function SimboloAnimado() {
  return (
    <svg className="simbolo" viewBox="26 -71 392 392" aria-hidden="true">
      <circle className="simbolo-anel" cx="162.4" cy="44.8" r="11" />
      <circle className="simbolo-anel a2" cx="162.4" cy="44.8" r="11" />
      <path className="simbolo-onda" pathLength={1} transform="matrix(1,0,0,-1,392.9742,37.286409)" d={ONDA} />
      <g className="simbolo-gota">
        <path transform="matrix(1,0,0,-1,172.7969,47.848207)" d={GOTA} />
      </g>
    </svg>
  );
}

export function Login() {
  const { usuario, entrar } = useAuth();
  const [login, setLogin] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [tentativas, setTentativas] = useState(0); // a cada erro o cartão balança de novo
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
      setTentativas((n) => n + 1);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="login">
      <section className="login-hero" aria-label="Instituto ACQUA">
        {[12, 28, 47, 66, 84].map((x, i) => (
          <span key={x} className="bolha" aria-hidden style={{ left: `${x}%`, animationDelay: `${[0, 2.5, 4.2, 1.3, 6][i]}s` }} />
        ))}
        <span className="login-kicker">Instituto ACQUA</span>
        <div className="login-hero-centro">
          <SimboloAnimado />
          <div className="login-hero-texto">
            <h2>Planner de Ofícios</h2>
            <p>Cadastro, prazos e entregas dos ofícios em um só lugar.</p>
          </div>
        </div>
        <div className="login-caminho" aria-hidden>
          <div className="trilha">
            <span />
          </div>
          <div className="login-etapas">
            <span>Cadastro</span>
            <span>Resposta</span>
            <span>Entrega</span>
          </div>
        </div>
        <div className="ondas" aria-hidden>
          {["o1", "o2", "o3"].map((o) => (
            <svg key={o} className={`onda ${o}`} viewBox="0 0 2880 120" preserveAspectRatio="none">
              <path d={ONDA_FUNDO} />
            </svg>
          ))}
        </div>
      </section>

      <section className="login-lado">
        <div className="login-tema">
          <SeletorTema claro />
        </div>
        <form key={tentativas} className={`login-cartao ${tentativas ? "tremer" : ""}`} onSubmit={enviar}>
          <div className="login-marca">
            <img src={logo} alt="Instituto ACQUA" />
            <div>
              <h1>Acesse o Planner</h1>
              <p className="texto-suave">Entre com seu usuário</p>
            </div>
          </div>
          <div className="campo-flutuante">
            <input id="login-usuario" className="input" placeholder=" " autoComplete="username" autoFocus={!tentativas}
              required value={login} onChange={(e) => setLogin(e.target.value)} />
            <label htmlFor="login-usuario">Usuário</label>
            <svg className="ic campo-ic" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="8.5" r="4" />
              <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
            </svg>
          </div>
          <div className="campo-flutuante">
            <input id="login-senha" className="input" type="password" placeholder=" " autoComplete="current-password"
              autoFocus={!!tentativas} required value={senha} onChange={(e) => setSenha(e.target.value)} />
            <label htmlFor="login-senha">Senha</label>
            <svg className="ic campo-ic" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="5" y="10.5" width="14" height="10" rx="2.5" />
              <path className="cadeado-arco" d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" />
              <path className="ac" d="M12 14.5v2" />
            </svg>
          </div>
          {encerrada && !erro && (
            <div className="alerta-info" role="status">
              <Info size={18} aria-hidden />
              <span>Sua sessão foi encerrada (a senha foi alterada ou o tempo de acesso acabou). Entre novamente.</span>
            </div>
          )}
          {erro && (
            <div className="alerta-erro" role="alert">
              <AlertTriangle size={18} aria-hidden />
              <span>{erro}</span>
            </div>
          )}
          <button type="submit" className="btn btn-primario btn-largo btn-entrar" disabled={enviando}>
            {enviando ? (
              <span className="pontos" role="status" aria-label="Entrando">
                <i />
                <i />
                <i />
              </span>
            ) : (
              <>
                Entrar <ArrowRight size={20} className="seta-entrar" aria-hidden />
              </>
            )}
          </button>
        </form>
        <p className="login-rodape texto-suave">Instituto ACQUA · Planner de Ofícios</p>
      </section>
    </div>
  );
}
