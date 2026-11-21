import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ImageUp, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { enviarTimbrado, imagemTimbrado, obterTimbrado, removerTimbrado } from "../../api/endpoints";
import { useToast } from "../../components/Toast";
import { Botao, Carregando, ErroBox } from "../../components/ui";
import type { Timbrado as TimbradoInfo } from "../../types";

type Parte = "cabecalho" | "fundo";
const PARTES: Record<Parte, { titulo: string; texto: string }> = {
  cabecalho: {
    titulo: "Cabeçalho",
    texto: "Faixa do topo de todas as páginas (logotipos, endereço e telefones). No modelo atual: 21,96 × 4,42 cm.",
  },
  fundo: {
    titulo: "Marca-d'água",
    texto: "Imagem de página inteira, atrás do texto (A4 em pé). Use cores bem claras para não atrapalhar a leitura.",
  },
};

function Imagem({ parte, versao }: { parte: Parte; versao: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let criada: string | null = null;
    let ativo = true;
    imagemTimbrado(parte).then((b) => {
      if (!ativo) return;
      criada = URL.createObjectURL(b);
      setUrl(criada);
    }).catch(() => setUrl(null));
    return () => { ativo = false; if (criada) URL.revokeObjectURL(criada); };
  }, [parte, versao]);
  return url ? <img src={url} alt={PARTES[parte].titulo} className={`timbrado-img timbrado-${parte}`} /> : <Carregando />;
}

function CartaoParte({ parte, info }: { parte: Parte; info: TimbradoInfo }) {
  const qc = useQueryClient();
  const avisar = useToast();
  const entrada = useRef<HTMLInputElement>(null);
  const [versao, setVersao] = useState(0);
  const depois = (t: TimbradoInfo, msg: string) => { qc.setQueryData(["timbrado"], t); setVersao((v) => v + 1); avisar(msg); };
  const enviar = useMutation({
    mutationFn: (f: File) => enviarTimbrado(parte, f),
    onSuccess: (t) => depois(t, `${PARTES[parte].titulo} atualizado.`),
    onError: (e) => avisar(e.message, "erro"),
  });
  const remover = useMutation({
    mutationFn: () => removerTimbrado(parte),
    onSuccess: (t) => depois(t, `${PARTES[parte].titulo} removido.`),
    onError: (e) => avisar(e.message, "erro"),
  });
  const tem = info[parte];
  return (
    <section className="cartao">
      <h2 className="titulo-secao">{PARTES[parte].titulo}</h2>
      <p className="texto-suave">{PARTES[parte].texto}</p>
      <div className={`timbrado-quadro ${tem ? "" : "vazio"}`}>
        {tem ? <Imagem parte={parte} versao={versao} /> : <span className="texto-suave">Nenhuma imagem enviada</span>}
      </div>
      <input ref={entrada} type="file" accept=".png,.jpg,.jpeg,image/png,image/jpeg" hidden
        onChange={(e) => { const f = e.target.files?.[0]; if (f) enviar.mutate(f); e.target.value = ""; }} />
      <div className="grupo">
        <Botao className="btn btn-secundario" carregando={enviar.isPending} onClick={() => entrada.current?.click()}>
          <ImageUp size={16} /> {tem ? "Trocar imagem" : "Enviar imagem"}
        </Botao>
        {tem && (
          <Botao className="btn btn-fantasma btn-perigo" carregando={remover.isPending} onClick={() => remover.mutate()}>
            <Trash2 size={16} /> Remover
          </Botao>
        )}
      </div>
    </section>
  );
}

/** Timbrado dos documentos (só o administrador do módulo Documentos). */
export function Timbrado() {
  const consulta = useQuery({ queryKey: ["timbrado"], queryFn: obterTimbrado });
  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Timbrado dos documentos</h1>
          <p className="texto-suave">
            As imagens valem para todos os ofícios e memorandos, inclusive os já emitidos quando forem baixados de novo.
            Se o endereço ou o telefone mudar, basta trocar o cabeçalho aqui.
          </p>
        </div>
      </header>
      {consulta.isPending ? <Carregando /> : consulta.isError ? <ErroBox erro={consulta.error} /> : (
        <>
          <div className="grade-2">
            <CartaoParte parte="cabecalho" info={consulta.data} />
            <CartaoParte parte="fundo" info={consulta.data} />
          </div>
          <p className="texto-suave nota-timbrado">
            Linha da data: <strong>{consulta.data.cidade ? `${consulta.data.cidade}${consulta.data.uf ? ` - ${consulta.data.uf}` : ""}` : "sem cidade"}</strong>
            {" "}(definida no servidor, em DOCUMENTOS_CIDADE e DOCUMENTOS_UF).
          </p>
        </>
      )}
    </>
  );
}
