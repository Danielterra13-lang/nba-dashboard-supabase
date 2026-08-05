# NBA Dashboard — Temporada 2025-26

Painel interativo com estatísticas de todos os jogadores da NBA na temporada 2025-26, filtrável por time, com identidade visual que se adapta automaticamente às cores oficiais de cada franquia.

**Dashboard ao vivo:** https://danielterra13-lang.github.io/nba-dashboard-supabase/
<img width="1885" height="905" alt="image" src="https://github.com/user-attachments/assets/c7ca47f6-7540-4319-b3a5-7a4798523d2a" />


## Por que esse projeto

Sou torcedor do Boston Celtics e queria um painel de estatísticas com a mesma qualidade dos dashboards executivos que construo no trabalho (RevOps e BI), mas usando uma stack diferente da que uso no dia a dia: SQL em ambiente real (Postgres via Supabase) em vez de planilha, e consumo direto de API REST no front-end em vez de exportação estática.

O objetivo não era só mostrar números de basquete. Era provar a mesma coisa que meus outros projetos de portfólio provam: pegar um problema, modelar os dados direito, e entregar algo que alguém sem contexto técnico consegue abrir e entender.

## Arquitetura

```
nba_api (Python)  →  CSV local  →  Supabase (Postgres)  →  REST API (PostgREST)  →  Dashboard HTML
   coleta              validação        armazenamento           entrega               visualização
```

Três camadas, cada uma isolada da outra:

1. **Coleta**: script Python roda localmente, busca dados na API pública da NBA e grava em CSV.
2. **Armazenamento**: os CSVs são carregados num banco Postgres (Supabase), modelado em esquema estrela.
3. **Visualização**: uma página HTML estática consulta o banco direto pela API REST automática do Supabase (sem backend próprio) e renderiza os gráficos no navegador.

Essa separação foi proposital. Cada camada pode ser trocada sem mexer nas outras, o que importa porque, na prática, a camada de coleta foi a que mais me deu trabalho (ver seção de desafios).

## Stack

| Camada | Tecnologia | Por quê |
|---|---|---|
| Coleta | Python + `nba_api` | Único cliente gratuito que expõe as métricas avançadas (TS%, USG%, Net Rating) que eu queria mostrar |
| Banco | Supabase (Postgres) | SQL de verdade, RLS nativo, API REST gerada automaticamente a partir do schema |
| Front-end | HTML + JS puro + Plotly.js | Sem framework, sem build step. Um arquivo único, hospedável em qualquer lugar |
| Hospedagem | GitHub Pages | Estático, gratuito, sem servidor pra manter |

## Modelagem de dados

Esquema estrela simples:

- `dim_players`: dados biográficos (altura, peso, college, país, draft)
- `dim_teams`: os 30 times
- `fact_player_stats`: estatísticas por jogador, por temporada, por time (grão pensado pra suportar trade no meio da temporada)
- `vw_player_stats`: view que já entrega tudo junto, pra o front-end não precisar fazer join client-side

O campo `season` está na tabela de fatos mesmo só existindo uma temporada carregada até agora. Isso é intencional: adicionar uma nova temporada no futuro é rodar a coleta de novo, não redesenhar o banco.

## Decisões e trade-offs

- **Snapshot único de temporada, não histórico completo.** A 2025-26 já tinha encerrado quando construí isso. Dava pra puxar múltiplas temporadas, mas isso é escopo pra uma v2, não pro MVP.
- **Escudos dos times via hotlink (CDN da ESPN), não hospedados no repositório.** Mantém o projeto leve, mas cria uma dependência de terceiro: se a ESPN reorganizar essas URLs, os escudos somem. Pra um portfólio pessoal, aceitável. Pra produção, eu hospedaria os assets.
- **Logo da NBA embutido em base64 direto no HTML**, ao contrário dos escudos dos times. Diferença de critério: não achei uma URL pública estável pra esse logo específico (a maioria dos resultados de busca eram sites de marketplace de logo, não CDNs confiáveis), então preferi eliminar a dependência externa completamente nesse caso.
- **Front-end consulta o Supabase direto, sem backend intermediário.** Só é seguro porque a chave usada no navegador é a `publishable` (antiga `anon`), que só tem permissão de leitura via Row Level Security. A chave com permissão de escrita nunca sai do ambiente local.

## Desafios reais (e o que aprendi com eles)

- **`stats.nba.com` bloqueia IPs de provedores de nuvem.** Tentei rodar a coleta no Google Colab e recebi timeout puro. Pesquisei e confirmei: é bloqueio deliberado de IPs de datacenter (AWS, GCP, Azure). Resolvido rodando a coleta localmente, na máquina de casa.
- **A API devolve altura como texto, não número.** O campo `player_height` vem formatado tipo `"6-6"` (pés-polegadas), o que quebra ao tentar salvar num campo numérico do banco. A correção foi usar o campo irmão `player_height_inches`, que vem numérico, e converter pra centímetros.
- **`NaN` não é JSON válido.** Jogadores sem alguma estatística registrada geram `NaN` no pandas, que o `httpx` recusa serializar (`ValueError: Out of range float values are not JSON compliant`). Resolvido com uma segunda passada de limpeza explícita antes do envio.
- **Nomenclatura de chaves do Supabase mudou em 2026.** O painel agora usa `publishable`/`secret` no lugar de `anon`/`service_role`. Funcionalmente equivalentes, mas a documentação e capturas de tela antigas ainda usam os nomes antigos, o que gerou confusão na hora de achar a chave certa.

## Como rodar localmente

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install nba_api pandas supabase python-dotenv

python collect_nba_data.py      # gera os CSVs em ./data
python load_to_supabase.py      # carrega no banco (precisa de .env com credenciais)
```

O `dashboard.html` (aqui, `index.html`) não precisa de build. Basta abrir no navegador ou hospedar como está.

## Melhorias futuras

- Histórico multi-temporada, com gráfico de evolução por jogador
- Hospedar os escudos dos times como assets próprios, removendo a dependência do CDN da ESPN
- Automatizar a coleta com um agendamento (ex: início de cada temporada), já que hoje é um processo manual
