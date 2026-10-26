import { FileUp, X } from "lucide-react";
import { useRef, useState } from "react";
import { tamanho } from "../utils/formato";

export const ACEITOS = ".pdf,.png,.jpg,.jpeg,.doc,.docx,.odt";
export const LIMITE_MB = 20;

export function validarArquivo(arquivo: File): string | null {
  const ext = arquivo.name.slice(arquivo.name.lastIndexOf(".")).toLowerCase();
  if (!ACEITOS.split(",").includes(ext)) return `Tipo não aceito. Use: ${ACEITOS.replaceAll(",", ", ")}`;
  if (arquivo.size > LIMITE_MB * 1024 * 1024) return `Arquivo maior que ${LIMITE_MB} MB`;
  if (arquivo.size === 0) return "Arquivo vazio";
  return null;
}

/** Área de arrastar-e-soltar / clicar para escolher um arquivo. */
export function SeletorArquivo({
  arquivo,
  aoEscolher,
  rotulo,
  compacto,
}: {
  arquivo: File | null;
  aoEscolher: (f: File | null) => void;
  rotulo: string;
  compacto?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [arrastando, setArrastando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  function escolher(f: File | undefined) {
    if (!f) return;
    const problema = validarArquivo(f);
    setErro(problema);
    if (!problema) aoEscolher(f);
  }

  if (arquivo) {
    return (
      <div className="arquivo-escolhido">
        <FileUp size={18} />
        <span className="arquivo-nome">{arquivo.name}</span>
        <small className="texto-suave">{tamanho(arquivo.size)}</small>
        <button type="button" className="btn-icone" onClick={() => aoEscolher(null)} aria-label="Remover arquivo">
          <X size={16} />
        </button>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        className={`soltar ${arrastando ? "arrastando" : ""} ${compacto ? "soltar-compacto" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setArrastando(true);
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={(e) => {
          e.preventDefault();
          setArrastando(false);
          escolher(e.dataTransfer.files[0]);
        }}
      >
        <FileUp size={20} />
        <span>
          <strong>{rotulo}</strong>
          <small className="texto-suave">
            Clique ou arraste · PDF, imagem ou Word <span className="sem-quebra">até {LIMITE_MB} MB</span>
          </small>
        </span>
      </button>
      <input
        ref={input}
        type="file"
        accept={ACEITOS}
        hidden
        onChange={(e) => {
          escolher(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {erro && <small className="texto-erro">{erro}</small>}
    </>
  );
}
