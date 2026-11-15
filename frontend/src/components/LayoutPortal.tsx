import { LayoutGrid, LogOut, ShieldCheck, Users } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import logo from "../assets/acqua-logo.svg";
import { useAuth } from "../auth/AuthContext";
import { ROTULO_PERFIL } from "../utils/formato";
import { SeletorTema } from "./SeletorTema";
import { NomeUnidade } from "./Unidade";

/** Estrutura das páginas que ficam acima dos módulos: a escolha do módulo e a gestão de usuários. */
export function LayoutPortal() {
  const { usuario, ehMaster, ehGestor, modulos, sair } = useAuth();
  return (
    <div className="portal">
      <header className="portal-topo">
        <NavLink to="/modulos" className="portal-marca" aria-label="Instituto ACQUA, ir para os módulos">
          <img src={logo} alt="Instituto ACQUA" />
          <NomeUnidade className="portal-unidade" />
        </NavLink>
        <nav className="portal-menu" aria-label="Menu principal">
          {modulos.length > 1 && (
            <NavLink to="/modulos" className="portal-link">
              <LayoutGrid size={17} aria-hidden /> Módulos
            </NavLink>
          )}
          {ehGestor && (
            <NavLink to="/usuarios" className="portal-link">
              <Users size={17} aria-hidden /> Usuários
            </NavLink>
          )}
        </nav>
        <div className="portal-usuario">
          <SeletorTema claro />
          <div className="portal-quem">
            <strong>{usuario?.nome}</strong>
            <small className="perfil-linha">
              {ehMaster && <ShieldCheck size={13} aria-hidden />}
              {ehMaster ? ROTULO_PERFIL.MASTER : "Usuário"}
            </small>
          </div>
          <button className="btn btn-secundario btn-pequeno" onClick={sair} title="Sair" aria-label="Sair">
            <LogOut size={16} aria-hidden /> Sair
          </button>
        </div>
      </header>
      <main className="portal-conteudo">
        <Outlet />
      </main>
    </div>
  );
}
