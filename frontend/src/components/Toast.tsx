import { CheckCircle2, X, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Tipo = "sucesso" | "erro";
interface Aviso {
  id: number;
  tipo: Tipo;
  texto: string;
}

const ToastContext = createContext<(texto: string, tipo?: Tipo) => void>(() => {});

let proximoId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);

  const remover = useCallback((id: number) => setAvisos((a) => a.filter((x) => x.id !== id)), []);

  const avisar = useCallback(
    (texto: string, tipo: Tipo = "sucesso") => {
      const id = proximoId++;
      setAvisos((a) => [...a, { id, tipo, texto }]);
      setTimeout(() => remover(id), tipo === "erro" ? 7000 : 4000);
    },
    [remover],
  );

  return (
    <ToastContext.Provider value={avisar}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {avisos.map((a) => (
          <div key={a.id} className={`toast toast-${a.tipo}`}>
            {a.tipo === "sucesso" ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
            <span>{a.texto}</span>
            <button className="toast-fechar" onClick={() => remover(a.id)} aria-label="Fechar aviso">
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
