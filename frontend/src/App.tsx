import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { Carregando } from "./components/ui";
import { Arquivos } from "./pages/Arquivos";
import { Atividades } from "./pages/Atividades";
import { Exclusoes } from "./pages/Exclusoes";
import { Feriados } from "./pages/Feriados";
import { Login } from "./pages/Login";
import { OficioDetalhe } from "./pages/oficio/OficioDetalhe";
import { OficioNovo } from "./pages/OficioNovo";
import { Oficios } from "./pages/Oficios";
import { Painel } from "./pages/Painel";
import { TiposOficio } from "./pages/TiposOficio";
import { Usuarios } from "./pages/Usuarios";

function Protegido() {
  const { usuario, carregando } = useAuth();
  if (carregando) return <Carregando texto="Verificando sessão…" />;
  return usuario ? <Outlet /> : <Navigate to="/login" replace />;
}

function SoAdmin() {
  const { ehAdmin } = useAuth();
  return ehAdmin ? <Outlet /> : <Navigate to="/" replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protegido />}>
        <Route element={<Layout />}>
          <Route index element={<Painel />} />
          <Route path="oficios" element={<Oficios />} />
          <Route path="oficios/novo" element={<OficioNovo />} />
          <Route path="oficios/:id" element={<OficioDetalhe />} />
          <Route path="exclusoes" element={<Exclusoes />} />
          <Route path="atividades" element={<Atividades />} />
          <Route element={<SoAdmin />}>
            <Route path="usuarios" element={<Usuarios />} />
            <Route path="feriados" element={<Feriados />} />
            <Route path="tipos" element={<TiposOficio />} />
            <Route path="arquivos" element={<Arquivos />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
