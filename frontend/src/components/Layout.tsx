import { useQuery } from "@tanstack/react-query";
import {
  Archive,
  CalendarOff,
  FilePlus2,
  FileText,
  FileX2,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  ShieldCheck,
  Tags,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { exclusoesPendentes } from "../api/endpoints";
import { useVerificacao } from "../pages/Arquivos";
import logo from "../assets/acqua-logo.svg";
import { SeletorTema } from "./SeletorTema";
import { useAuth } from "../auth/AuthContext";
import { ROTULO_PERFIL } from "../utils/formato";

export function Layout() {
  const { usuario, ehAdmin, ehMaster, sair } = useAuth();
  const [menuAberto, setMenuAberto] = useState(false);
  const { pathname } = useLocation();

  // Aviso de pedidos de exclusão aguardando decisão (só admin/master), atualizado a cada minuto
  const pendentes = useQuery({
    queryKey: ["exclusoes-pendentes"],
    queryFn: exclusoesPendentes,
    enabled: ehAdmin,
    refetchInterval: 60_000,
  });
  const totalPendentes = pendentes.data?.total ?? 0;
  // Arquivos que sumiram ou foram alterados (verificação diária): aviso no menu para admin/master
  const problemasArquivos = useVerificacao(ehAdmin).data?.problemas.length ?? 0;

  // "Ofícios" fica ativo na lista e no detalhe, mas não em "Novo ofício".
  const emOficios = pathname.startsWith("/oficios") && pathname !== "/oficios/novo";
  const links = [
    { para: "/", rotulo: "Painel", icone: LayoutDashboard, ativo: pathname === "/" },
    { para: "/oficios", rotulo: "Ofícios", icone: FileText, ativo: emOficios },
    { para: "/oficios/novo", rotulo: "Novo ofício", icone: FilePlus2, ativo: pathname === "/oficios/novo" },
    {
      para: "/exclusoes",
      rotulo: ehAdmin ? "Pedidos de exclusão" : "Meus pedidos de exclusão",
      icone: FileX2,
      ativo: pathname === "/exclusoes",
      contador: ehAdmin ? totalPendentes : 0,
    },
    { para: "/atividades", rotulo: "Atividades", icone: History, ativo: pathname === "/atividades" },
    ...(ehAdmin
      ? [
          { para: "/usuarios", rotulo: "Usuários", icone: Users, ativo: pathname === "/usuarios" },
          { para: "/feriados", rotulo: "Feriados", icone: CalendarOff, ativo: pathname === "/feriados" },
          { para: "/tipos", rotulo: "Tipos de ofício", icone: Tags, ativo: pathname === "/tipos" },
          {
            para: "/arquivos",
            rotulo: "Arquivos",
            icone: Archive,
            ativo: pathname === "/arquivos",
            contador: problemasArquivos,
            avisoContador: "arquivo(s) com problema",
          },
        ]
      : []),
  ];

  return (
    <div className="app">
      <aside className={`lateral ${menuAberto ? "aberta" : ""}`}>
        <div className="marca">
          <NavLink to="/" className="marca-link" onClick={() => setMenuAberto(false)}>
            <img src={logo} alt="Instituto ACQUA" className="marca-logo" />
            <span className="marca-sistema">Planner de Ofícios</span>
          </NavLink>
          <button className="btn-icone so-mobile" onClick={() => setMenuAberto((v) => !v)} aria-label="Menu">
            {menuAberto ? <X size={20} /> : <Menu size={20} />}
            {!menuAberto && totalPendentes + problemasArquivos > 0 && <span className="ponto-aviso" aria-hidden />}
          </button>
        </div>

        <nav className="nav" onClick={() => setMenuAberto(false)}>
          {links.map(({ para, rotulo, icone: Icone, ativo, contador, avisoContador }) => (
            <NavLink key={para} to={para} className={`nav-link ${ativo ? "ativo" : ""}`}>
              <Icone size={18} />
              <span className="nav-rotulo">{rotulo}</span>
              {contador ? (
                <span className="contador" aria-label={`${contador} ${avisoContador ?? "aguardando decisão"}`}>
                  {contador}
                </span>
              ) : null}
            </NavLink>
          ))}
        </nav>

        <SeletorTema />

        <div className="usuario-box">
          <div>
            <strong>{usuario?.nome}</strong>
            <small className="texto-suave perfil-linha">
              {ehMaster && <ShieldCheck size={13} />}
              {usuario ? ROTULO_PERFIL[usuario.perfil] : ""}
            </small>
          </div>
          <button className="btn-icone" onClick={sair} title="Sair" aria-label="Sair">
            <LogOut size={18} />
          </button>
        </div>
      </aside>

      <main className="conteudo">
        <Outlet />
      </main>
    </div>
  );
}
