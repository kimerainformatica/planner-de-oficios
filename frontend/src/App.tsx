import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { LayoutManutencao } from "./components/LayoutManutencao";
import { LayoutPortal } from "./components/LayoutPortal";
import { LayoutTetos } from "./components/LayoutTetos";
import { Carregando } from "./components/ui";
import type { Modulo } from "./types";
import { Arquivos } from "./pages/Arquivos";
import { Atividades } from "./pages/Atividades";
import { Exclusoes } from "./pages/Exclusoes";
import { Login } from "./pages/Login";
import { ChamadoDetalhe } from "./pages/manutencao/ChamadoDetalhe";
import { ChamadoNovo } from "./pages/manutencao/ChamadoNovo";
import { Chamados } from "./pages/manutencao/Chamados";
import { Avisos } from "./pages/manutencao/Avisos";
import { Empresas } from "./pages/manutencao/Empresas";
import { InicioManutencao } from "./pages/manutencao/Inicio";
import { Preventivas } from "./pages/manutencao/Preventivas";
import { Quadro } from "./pages/manutencao/Quadro";
import { Modulos } from "./pages/Modulos";
import { OficioDetalhe } from "./pages/oficio/OficioDetalhe";
import { OficioNovo } from "./pages/OficioNovo";
import { Oficios } from "./pages/Oficios";
import { Painel } from "./pages/Painel";
import { Lancamentos } from "./pages/tetos/Lancamentos";
import { PainelTetos } from "./pages/tetos/Painel";
import { SetoresTetos } from "./pages/tetos/Setores";
import { TipoTetoDetalhe } from "./pages/tetos/TipoDetalhe";
import { TiposTeto } from "./pages/tetos/Tipos";
import { TiposOficio } from "./pages/TiposOficio";
import { Usuarios } from "./pages/Usuarios";

function Protegido() {
  const { usuario, carregando } = useAuth();
  if (carregando) return <Carregando texto="Verificando sessão…" />;
  return usuario ? <Outlet /> : <Navigate to="/login" replace />;
}

/** Só entra quem foi habilitado no módulo (o MASTER sempre); os demais voltam para a escolha de módulos. */
function ComAcesso({ modulo }: { modulo: Modulo }) {
  const { modulos } = useAuth();
  return modulos.includes(modulo) ? <Outlet /> : <Navigate to="/modulos" replace />;
}

/** Administrador do Planner de Ofícios (as telas de administração desse módulo). */
function SoAdmin() {
  const { ehAdmin } = useAuth();
  return ehAdmin ? <Outlet /> : <Navigate to="/" replace />;
}

/** Administrador de um módulo específico (ADMIN do módulo ou MASTER). */
function SoAdminDe({ modulo, volta }: { modulo: Modulo; volta: string }) {
  const { ehAdminNo } = useAuth();
  return ehAdminNo(modulo) ? <Outlet /> : <Navigate to={volta} replace />;
}

/** MASTER ou administrador de algum módulo: gestão de usuários. */
function SoGestor() {
  const { ehGestor } = useAuth();
  return ehGestor ? <Outlet /> : <Navigate to="/modulos" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protegido />}>
        {/* Acima dos módulos: escolha do módulo e gestão de usuários */}
        <Route element={<LayoutPortal />}>
          <Route path="modulos" element={<Modulos />} />
          <Route element={<SoGestor />}>
            <Route path="usuarios" element={<Usuarios />} />
          </Route>
        </Route>

        {/* Módulo Manutenção Clínica */}
        <Route element={<ComAcesso modulo="MANUTENCAO" />}>
          <Route path="manutencao" element={<LayoutManutencao />}>
            <Route index element={<InicioManutencao />} />
            <Route path="quadro" element={<Quadro />} />
            <Route path="chamados" element={<Chamados />} />
            <Route path="chamados/novo" element={<ChamadoNovo />} />
            <Route path="chamados/:id" element={<ChamadoDetalhe />} />
            <Route path="preventivas" element={<Preventivas />} />
            <Route path="avisos" element={<Avisos />} />
            <Route element={<SoAdminDe modulo="MANUTENCAO" volta="/manutencao" />}>
              <Route path="empresas" element={<Empresas />} />
            </Route>
            <Route path="*" element={<Navigate to="/manutencao" replace />} />
          </Route>
        </Route>

        {/* Módulo Controle de Tetos */}
        <Route element={<ComAcesso modulo="TETOS" />}>
          <Route path="tetos" element={<LayoutTetos />}>
            <Route index element={<PainelTetos />} />
            <Route path="lancamentos" element={<Lancamentos />} />
            <Route path="tipo/:id" element={<TipoTetoDetalhe />} />
            <Route element={<SoAdminDe modulo="TETOS" volta="/tetos" />}>
              <Route path="tipos" element={<TiposTeto />} />
              <Route path="setores" element={<SetoresTetos />} />
            </Route>
            <Route path="*" element={<Navigate to="/tetos" replace />} />
          </Route>
        </Route>

        {/* Módulo Planner de Ofícios (mantém os endereços de sempre) */}
        <Route element={<ComAcesso modulo="OFICIOS" />}>
          <Route element={<Layout />}>
            <Route index element={<Painel />} />
            <Route path="oficios" element={<Oficios />} />
            <Route path="oficios/novo" element={<OficioNovo />} />
            <Route path="oficios/:id" element={<OficioDetalhe />} />
            <Route path="exclusoes" element={<Exclusoes />} />
            <Route path="atividades" element={<Atividades />} />
            <Route element={<SoAdmin />}>
              <Route path="tipos" element={<TiposOficio />} />
              <Route path="arquivos" element={<Arquivos />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}
