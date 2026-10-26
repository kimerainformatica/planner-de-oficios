import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, ChevronLeft, ChevronRight, Plus, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { criarFeriado, excluirFeriado, gerarFeriadosNacionais, listarFeriados } from "../api/endpoints";
import { useToast } from "../components/Toast";
import { Botao, Campo, Carregando, ErroBox, Vazio } from "../components/ui";
import type { Feriado } from "../types";
import { data } from "../utils/formato";

const DIAS_SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

function diaDaSemana(iso: string) {
  const [a, m, d] = iso.split("-").map(Number);
  return DIAS_SEMANA[new Date(a, m - 1, d).getDay()];
}

export function Feriados() {
  const avisar = useToast();
  const queryClient = useQueryClient();
  const [ano, setAno] = useState(new Date().getFullYear());
  const [novaData, setNovaData] = useState("");
  const [descricao, setDescricao] = useState("");
  const consulta = useQuery({ queryKey: ["feriados", ano], queryFn: () => listarFeriados(ano) });

  // Feriados mudam a contagem de dias úteis: recarrega listas e painel.
  const aposMudanca = () => {
    for (const chave of ["feriados", "oficios", "oficio", "resumo"]) {
      queryClient.invalidateQueries({ queryKey: [chave] });
    }
  };

  const gerar = useMutation({
    mutationFn: () => gerarFeriadosNacionais(ano),
    onSuccess: (novos) => {
      aposMudanca();
      avisar(novos.length ? `${novos.length} feriado(s) nacional(is) cadastrado(s).` : "Os feriados nacionais já estavam cadastrados.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  const criar = useMutation({
    mutationFn: () => criarFeriado({ data: novaData, descricao: descricao.trim() }),
    onSuccess: (f) => {
      aposMudanca();
      setNovaData("");
      setDescricao("");
      avisar(`Feriado de ${data(f.data)} cadastrado.`);
      const anoNovo = Number(f.data.slice(0, 4));
      if (anoNovo !== ano) setAno(anoNovo);
    },
    onError: (e) => avisar(e.message, "erro"),
  });
  const excluir = useMutation({
    mutationFn: (f: Feriado) => excluirFeriado(f.id),
    onSuccess: () => {
      aposMudanca();
      avisar("Feriado removido.");
    },
    onError: (e) => avisar(e.message, "erro"),
  });

  function enviar(e: FormEvent) {
    e.preventDefault();
    criar.mutate();
  }

  return (
    <>
      <header className="pagina-topo">
        <div>
          <h1>Feriados</h1>
          <p className="texto-suave">Datas que não contam como dia útil no prazo dos ofícios.</p>
        </div>
        <div className="grupo">
          <button className="btn btn-secundario btn-icone-so" onClick={() => setAno(ano - 1)} aria-label="Ano anterior">
            <ChevronLeft size={18} />
          </button>
          <strong className="ano">{ano}</strong>
          <button className="btn btn-secundario btn-icone-so" onClick={() => setAno(ano + 1)} aria-label="Próximo ano">
            <ChevronRight size={18} />
          </button>
        </div>
      </header>

      <div className="duas-colunas duas-colunas-largura">
        <section className="painel-bloco">
          <div className="bloco-topo">
            <h2>Feriados de {ano}</h2>
            <Botao className="btn btn-secundario btn-pequeno" carregando={gerar.isPending} onClick={() => gerar.mutate()}>
              <CalendarPlus size={15} /> Cadastrar nacionais de {ano}
            </Botao>
          </div>
          {consulta.isPending ? (
            <Carregando />
          ) : consulta.isError ? (
            <ErroBox erro={consulta.error} />
          ) : consulta.data.length === 0 ? (
            <Vazio>
              Nenhum feriado em {ano}. Sem eles, só sábados e domingos deixam de contar.
            </Vazio>
          ) : (
            <ul className="lista-feriados">
              {consulta.data.map((f) => (
                <li key={f.id}>
                  <span className="feriado-data">
                    {data(f.data)} <small className="texto-suave">{diaDaSemana(f.data)}</small>
                  </span>
                  <span className="feriado-desc">{f.descricao}</span>
                  <button className="btn-icone texto-perigo" aria-label={`Remover ${f.descricao}`}
                    onClick={() => confirm(`Remover "${f.descricao}" (${data(f.data)})?`) && excluir.mutate(f)}>
                    <Trash2 size={16} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="painel-bloco">
          <h2>Adicionar feriado</h2>
          <p className="texto-suave">Use para feriados estaduais, municipais ou pontos facultativos.</p>
          <form className="formulario" onSubmit={enviar}>
            <Campo rotulo="Data *">
              {(id) => <input id={id} type="date" className="input" required value={novaData}
                onChange={(e) => setNovaData(e.target.value)} />}
            </Campo>
            <Campo rotulo="Descrição *">
              {(id) => <input id={id} className="input" required maxLength={120} value={descricao}
                placeholder="Ex.: Aniversário da cidade" onChange={(e) => setDescricao(e.target.value)} />}
            </Campo>
            <Botao type="submit" carregando={criar.isPending}>
              <Plus size={16} /> Adicionar
            </Botao>
          </form>
        </section>
      </div>
    </>
  );
}
