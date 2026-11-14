import { useQuery } from "@tanstack/react-query";
import { listarUsuarios } from "../api/endpoints";
import { papelNo } from "../utils/modulos";

/** Select de clientes, usado só pelo admin (filtros e cadastro em nome de alguém). */
export function SeletorCliente({
  id,
  valor,
  aoMudar,
  rotuloVazio,
}: {
  id?: string;
  valor: number | undefined;
  aoMudar: (id: number | undefined) => void;
  rotuloVazio: string;
}) {
  // Só quem tem acesso ao Planner de Ofícios pode ser dono de um ofício
  const { data: usuarios = [] } = useQuery({
    queryKey: ["usuarios", "OFICIOS"],
    queryFn: () => listarUsuarios("OFICIOS"),
  });
  return (
    <select
      id={id}
      className="input"
      value={valor ?? ""}
      onChange={(e) => aoMudar(e.target.value ? Number(e.target.value) : undefined)}
    >
      <option value="">{rotuloVazio}</option>
      {usuarios
        .filter((u) => u.ativo)
        .map((u) => (
          <option key={u.id} value={u.id}>
            {u.nome}
            {papelNo(u, "OFICIOS") === "ADMIN" ? " (admin)" : ""}
          </option>
        ))}
    </select>
  );
}
