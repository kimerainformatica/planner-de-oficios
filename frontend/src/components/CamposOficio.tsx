import { useQuery } from "@tanstack/react-query";
import { sugestoesSetor } from "../api/endpoints";
import type { Destinatario, TipoOficio } from "../types";
import { useTipos } from "../utils/tipos";
import { Campo } from "./ui";

export function SeletorTipo({
  valor,
  aoMudar,
  obrigatorio,
}: {
  valor: TipoOficio | "";
  aoMudar: (t: TipoOficio | "") => void;
  obrigatorio?: boolean;
}) {
  const tipos = useTipos();
  // Tipos desativados não aparecem para ofícios novos, mas o tipo atual de um ofício antigo continua na lista
  const opcoes = tipos.todos.filter((t) => t.ativo || t.codigo === valor);
  return (
    <Campo rotulo={obrigatorio ? "Tipo de ofício *" : "Tipo de ofício"}
      dica={tipos.exigeEntrega(valor) ? "Após a resposta, a entrega (dos itens ou do serviço) também precisa ser confirmada" : undefined}>
      {(id) => (
        <select id={id} className="input" required={obrigatorio} value={valor}
          onChange={(e) => aoMudar(e.target.value)}>
          <option value="">Selecione…</option>
          {opcoes.map((t) => (
            <option key={t.codigo} value={t.codigo}>
              {t.nome}
              {!t.ativo && " (desativado)"}
            </option>
          ))}
        </select>
      )}
    </Campo>
  );
}

const OPCOES: { valor: Destinatario | ""; rotulo: string }[] = [
  { valor: "", rotulo: "Não informar" },
  { valor: "SES", rotulo: "SES" },
  { valor: "ACQUA", rotulo: "ACQUA" },
  { valor: "OUTROS", rotulo: "Outros" },
];

/** SES / ACQUA pedem o setor; Outros pede o destino por extenso. */
export function CamposDestinatario({
  tipo,
  setor,
  aoMudarTipo,
  aoMudarSetor,
}: {
  tipo: Destinatario | "";
  setor: string;
  aoMudarTipo: (t: Destinatario | "") => void;
  aoMudarSetor: (s: string) => void;
}) {
  // Sugere os setores/destinos já usados, para não surgirem duplicados como "CME" e "C.M.E."
  const sugestoes = useQuery({
    queryKey: ["setores", tipo],
    queryFn: () => sugestoesSetor(tipo as Destinatario),
    enabled: !!tipo,
    staleTime: 60_000,
  });
  const lista = `setores-${tipo || "nenhum"}`;
  return (
    <div className="campo">
      <span className="rotulo">Destinatário</span>
      <div className="segmentado" role="radiogroup" aria-label="Destinatário">
        {OPCOES.map((o) => (
          <label key={o.valor || "nenhum"} className={`segmento ${tipo === o.valor ? "ativo" : ""}`}>
            <input type="radio" name="destinatario" checked={tipo === o.valor}
              onChange={() => aoMudarTipo(o.valor)} />
            {o.rotulo}
          </label>
        ))}
      </div>
      {tipo && (
        <input
          className="input"
          aria-label={tipo === "OUTROS" ? "Destino" : `Setor da ${tipo}`}
          placeholder={tipo === "OUTROS" ? "Digite o destino (ex.: Prefeitura, Ministério Público…)" : `Digite o setor da ${tipo}`}
          required
          maxLength={120}
          list={lista}
          autoComplete="off"
          value={setor}
          onChange={(e) => aoMudarSetor(e.target.value)}
        />
      )}
      {tipo && (
        <datalist id={lista}>
          {(sugestoes.data ?? []).map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      )}
    </div>
  );
}
