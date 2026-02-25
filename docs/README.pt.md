<div align="center">
  <img src="../assets/hero.png" alt="CachiBot" width="800" />

  <h1>CachiBot</h1>

  <p><strong>O Agente de IA Blindado</strong></p>
  <p><em>Visual. Transparente. Seguro.</em></p>

  <p>
    <a href="../README.md">English</a> ·
    <a href="https://codewiki.google/github.com/jhd3197/cachibot">CodeWiki</a> ·
    <a href="README.es.md">Español</a> ·
    <a href="README.zh-CN.md">中文版</a> ·
    Português
  </p>

  <p>
    <img src="https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" />
    <img src="https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white" alt="macOS" />
    <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" />
  </p>

  <p>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/v/cachibot.svg" alt="PyPI" /></a>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/dm/cachibot.svg" alt="Downloads" /></a>
    <a href="https://github.com/jhd3197/CachiBot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="Licenca" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python" /></a>
    <a href="https://react.dev"><img src="https://img.shields.io/badge/React-19-61DAFB.svg" alt="React" /></a>
    <a href="https://github.com/jhd3197/CachiBot/stargazers"><img src="https://img.shields.io/github/stars/jhd3197/CachiBot?style=social" alt="Stars" /></a>
    <a href="https://discord.gg/93QEWZeHRK"><img src="https://img.shields.io/discord/1470624345188732992?label=Discord&logo=discord&logoColor=white&color=5865F2" alt="Discord" /></a>
  </p>

  <p>
    Uma plataforma de agentes de IA visual com total transparência. Nomeado em homenagem ao <em>cachicamo</em> venezuelano (tatu) — construído para ser blindado, auditável e seu para controlar.
  </p>

  <p>
    <a href="#instalação">Instalação</a> ·
    <a href="#recursos">Recursos</a> ·
    <a href="#provedores-suportados">Provedores</a> ·
    <a href="#segurança">Segurança</a> ·
    <a href="#contribuindo">Contribuindo</a> ·
    <a href="https://discord.gg/93QEWZeHRK">Discord</a>
  </p>

</div>

---

## Por que CachiBot?

A maioria das plataformas de IA te força a escolher: interfaces de chatbot sem automação, construtores de workflows sem IA conversacional, ou frameworks de desenvolvimento que levam semanas para entregar algo.

**CachiBot te dá os três.** Crie bots especializados, implante-os em qualquer plataforma de mensagens, execute-os em salas colaborativas e automatize workflows — tudo a partir de um painel visual com total transparência sobre o que seus agentes estão fazendo.

![arepa-war](https://github.com/user-attachments/assets/5996fc02-0c4c-4a61-a998-f007189494fd)

<p align="center">
  <a href="https://youtu.be/G8JEhkcRxD8">
    <img src="https://img.shields.io/badge/YouTube-Assistir_Demo-red?style=for-the-badge&logo=youtube&logoColor=white" alt="Assistir no YouTube" />
  </a>
  <a href="https://cachibot.ai/marketplace/rooms/great-arepa-war?utm_source=github&utm_medium=readme&utm_campaign=arepa_war_room">
    <img src="https://img.shields.io/badge/CachiBot-Ver_Sala-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Ver o Chat no CachiBot" />
  </a>
  <a href="https://dev.to/juandenis/ai-settles-the-ultimate-venezuelan-vs-colombian-arepa-debate-2ngm">
    <img src="https://img.shields.io/badge/Dev.to-Ler_Artigo-0A0A0A?style=for-the-badge&logo=devdotto&logoColor=white" alt="Ler no Dev.to" />
  </a>
</p>

## Instalação

### Linux / macOS

```bash
curl -fsSL cachibot.ai/install.sh | bash
```

Configura Python, um ambiente virtual e um serviço systemd — tudo que você precisa em um único comando.

### Windows

```powershell
irm cachibot.ai/install.ps1 | iex
```

### pip

```bash
pip install cachibot
```

Depois inicie o servidor:

```bash
cachibot server
```

Abra **http://localhost:5870** — o frontend é empacotado e servido automaticamente. Nenhum passo de build separado necessário.

### Docker

```bash
docker compose up
```

### App Desktop

Baixe o instalador para sua plataforma em [GitHub Releases](https://github.com/jhd3197/CachiBot/releases). Disponível como instalador NSIS (Windows), DMG (macOS) e AppImage/DEB/RPM (Linux). Inclui atualização automática.

### Configure suas chaves de API

Você pode configurar as chaves de API diretamente pela interface do painel — sem necessidade de variáveis de ambiente. Basta abrir o painel de configurações e adicionar suas chaves lá.

Se preferir variáveis de ambiente, elas também funcionam:

```bash
export OPENAI_API_KEY="sua-chave"       # OpenAI / GPT-4
export ANTHROPIC_API_KEY="sua-chave"    # Claude
export MOONSHOT_API_KEY="sua-chave"     # Kimi
# ou use Ollama localmente (sem necessidade de chave)
```

### Uso via CLI

```bash
cachibot server                    # Inicia o painel
cachibot "resuma este projeto"     # Executa uma única tarefa
cachibot                           # Modo interativo
cachibot --model claude/sonnet     # Sobrescrever modelo
cachibot --workspace ./meu-projeto # Definir workspace
cachibot --approve                 # Requer aprovação para cada ação
cachibot --verbose                 # Mostrar processo de raciocínio
cachibot diagnose                  # Verificar saúde da instalação
cachibot repair                    # Corrigir instalação corrompida
cachi server                       # Alias curto
```

## Recursos

### Plataforma Multi-Agente

- **Bots Especializados Ilimitados** — Crie bots com prompts de sistema personalizados, roteamento de modelos por bot, toggles de capacidades e chaves de API isoladas por provedor
- **Salas Colaborativas** — Execute múltiplos bots juntos com 9 modos de resposta: paralelo, sequencial, cadeia, roteador, debate, cascata, relay, consenso e entrevista
- **Marketplace de Bots** — Templates pré-construídos de bots e salas para casos de uso comuns, instaláveis pelo painel

### Sistema de Plugins por Capacidades

Cada bot tem um conjunto de toggles de capacidades que controlam quais ferramentas estão disponíveis. Plugins são carregados dinamicamente com base nesses toggles, alimentado por [Tukuy](https://github.com/jhd3197/Tukuy):

| Capacidade | Ferramentas |
|-----------|-------------|
| Execução de Código | Python em sandbox com análise de risco AST |
| Operações de Arquivo | Ler, escrever, editar, listar, info — limitado ao workspace |
| Operações Git | Status, diff, log, commit, branch |
| Acesso ao Shell | Comandos shell com restrições de segurança |
| Acesso Web | Buscar URLs, pesquisar na web, requisições HTTP |
| Operações de Dados | Consultas SQLite, compressão zip/tar |
| Gestão de Trabalho | Tarefas, todos, jobs, funções, agendamentos |
| Geração de Imagens | DALL-E, Google Imagen, Stability AI, Grok |
| Geração de Áudio | OpenAI TTS, ElevenLabs, transcrição Whisper |
| Agentes de Código | Iniciar Claude Code, OpenAI Codex ou Gemini CLI como sub-agentes |
| Base de Conhecimento | Busca semântica em documentos enviados e notas |
| Instruções Personalizadas | Pacotes de instruções alimentados por LLM (análise, escrita, desenvolvimento) |

### Integrações de Plataforma

Implante bots em **7 plataformas de mensagens** com adaptadores integrados. Conexões são armazenadas criptografadas, reconectadas automaticamente ao reiniciar o servidor e monitoradas:

Telegram · Discord · Slack · Microsoft Teams · WhatsApp · Viber · LINE

### Base de Conhecimento & RAG

- Envie documentos (PDF, TXT, MD, DOCX) — automaticamente fragmentados e incorporados
- Busca por similaridade vetorial com tamanho de fragmento, sobreposição e limiar de relevância configuráveis
- Provedores de embeddings: OpenAI, Ollama ou FastEmbed local (sem necessidade de chave de API)
- Notas de texto livre como fonte de conhecimento adicional
- Armazenamento: SQLite com similaridade de cosseno ou PostgreSQL com pgvector

### Gestão de Trabalho & Automação

- **Itens de Trabalho** — Unidades de nível superior com rastreamento de status (pendente, em progresso, concluído, falhou, cancelado, pausado)
- **Tarefas** — Passos dentro de itens de trabalho com rastreamento de dependências e bloqueio/desbloqueio automático
- **Jobs** — Execuções de agente em segundo plano, gerenciadas por um serviço de execução com progresso em tempo real via WebSocket
- **Todos** — Itens de checklist leves
- **Funções** — Templates de tarefas reutilizáveis com parâmetros tipados e dependências por etapa
- **Agendamentos** — Execução por cron, intervalo, uma vez ou por evento de funções
- **Scripts** — Scripts Python com histórico de versões, editor Monaco e sandbox de execução separado

### Conversas por Voz

Fale com seus bots com speech-to-text e text-to-speech em tempo real através de uma interface de voz dedicada.

### API Compatível com OpenAI

CachiBot expõe endpoints `/v1/chat/completions` e `/v1/models`, para que ferramentas externas como Cursor ou extensões do VS Code possam usar seus bots como se fossem modelos OpenAI. Autenticado com chaves de API `cb-*` do painel de desenvolvedor. Suporta streaming via SSE.

### Segurança e Controle

- **Fluxos de Aprovação Visual** — Aprove ou rejeite operações arriscadas antes que sejam executadas
- **Execução em Sandbox** — Python roda em isolamento com pontuação de risco baseada em AST (SEGURO / MODERADO / PERIGOSO)
- **Isolamento de Workspace** — Todo acesso a arquivos limitado ao espaço de trabalho
- **Credenciais Criptografadas** — Segredos de conexão de plataformas armazenados com criptografia AES
- **Trilha de Auditoria Completa** — Cada ação registrada com temporização, uso de tokens e custo

### Autenticação e Controle de Acesso

- Autenticação baseada em JWT com tokens de acesso e refresh
- Modo auto-hospedado com gestão de usuários local via assistente de configuração
- Papéis de usuário (admin, usuário) com propriedade de bots e controle de acesso baseado em grupos
- Limitação de taxa em endpoints de autenticação

## O Que Você Pode Construir?

- **Bot de Suporte ao Cliente** — Implante no Telegram com uma base de conhecimento dos seus docs, responda FAQs automaticamente
- **Sala de Análise de Dados** — 3 bots (especialista SQL + analista Python + redator de relatórios) colaborando em insights
- **Assistente de Voz** — Fale com um bot com STT/TTS, gerencie tarefas e lembretes sem usar as mãos
- **Pipeline de Conteúdo** — Bot pesquisador + bot escritor + gerador de imagens produzindo posts de blog de ponta a ponta
- **Agente DevOps** — Monitore repos, execute scripts em sandbox, envie alertas para o Slack por agendamento
- **Assistente de Código** — Bot que inicia Claude Code ou Codex para lidar com tarefas complexas de programação

## Provedores Suportados

CachiBot usa [Prompture](https://github.com/jhd3197/Prompture) para gerenciamento de modelos com auto-descoberta — configure uma chave de API e os modelos disponíveis aparecem automaticamente.

| Provedor | Modelos de Exemplo | Variável de Ambiente |
|----------|-------------------|---------------------|
| OpenAI | GPT-4o, GPT-4, o1 | `OPENAI_API_KEY` |
| Anthropic | Claude Sonnet, Opus, Haiku | `ANTHROPIC_API_KEY` |
| Moonshot | Kimi K2.5 | `MOONSHOT_API_KEY` |
| Google | Gemini Pro, Flash | `GOOGLE_API_KEY` |
| Groq | Llama 3, Mixtral | `GROQ_API_KEY` |
| Grok / xAI | Grok-2 | `GROK_API_KEY` |
| OpenRouter | Qualquer modelo no OpenRouter | `OPENROUTER_API_KEY` |
| Azure OpenAI | GPT-4, GPT-4o | `AZURE_OPENAI_API_KEY` |
| ZhipuAI | GLM-4 | `ZHIPUAI_API_KEY` |
| ModelScope | Qwen | `MODELSCOPE_API_KEY` |
| Stability AI | Stable Diffusion (geração de imagens) | `STABILITY_API_KEY` |
| ElevenLabs | Síntese de voz | `ELEVENLABS_API_KEY` |
| Ollama | Qualquer modelo local | *(sem necessidade de chave)* |
| LM Studio | Qualquer modelo local | *(sem necessidade de chave)* |

Todas as chaves também podem ser configuradas pela interface do painel sem tocar em variáveis de ambiente.

## Segurança

CachiBot é construído com segurança como princípio fundamental. **Visibilidade é segurança** — o maior risco com agentes de IA é não saber o que eles estão fazendo.

### Execução em Sandbox

Código Python roda num ambiente restrito:

- **Restrições de Importação** — Apenas módulos seguros permitidos (json, math, datetime, etc.)
- **Restrições de Caminho** — Acesso a arquivos limitado ao workspace via SecurityContext
- **Timeout de Execução** — Código encerrado após timeout (padrão: 30s)
- **Análise de Risco** — Pontuação baseada em AST (SEGURO / MODERADO / PERIGOSO) antes da execução
- **Fluxo de Aprovação** — Operações perigosas requerem aprovação explícita pelo painel

### Sempre Bloqueado

Estes nunca são permitidos independentemente da configuração: `subprocess`, `os.system`, `ctypes`, `socket`, `ssl`, `importlib`, `eval`, `exec`, `pickle`, `marshal`.

## Configuração

CachiBot suporta configuração em camadas: variáveis de ambiente sobrescrevem o TOML do workspace, que sobrescreve o `~/.cachibot.toml` do usuário, que sobrescreve os padrões. Consulte [`cachibot.example.toml`](../cachibot.example.toml) para todas as opções.

Seções chave: `[agent]` (modelo, temperatura, max iterações), `[sandbox]` (imports permitidos, timeout), `[knowledge]` (tamanho de fragmento, modelo de embedding, limiar de similaridade), `[coding_agents]` (agente padrão, timeout, caminhos de CLI), `[database]` (URL de SQLite ou PostgreSQL), `[auth]` (configurações JWT).

## Contribuindo

Contribuições são bem-vindas! Veja [CONTRIBUTING.md](../CONTRIBUTING.md) para o guia completo. Início rápido:

```bash
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot

# Backend
python -m venv venv && source venv/bin/activate  # ou .\venv\Scripts\activate no Windows
pip install -e ".[dev]"

# Frontend
cd frontend && npm install && cd ..

# Desktop (opcional — apenas se estiver trabalhando no shell Electron)
cd desktop && npm install && cd ..

# Executar tudo
bash dev.sh              # ou .\dev.ps1 no Windows
bash dev.sh desktop      # com Electron
bash dev.sh watch-lint   # watcher de lint (ruff + ESLint ao salvar)
```

Veja [CONTRIBUTING.md](../CONTRIBUTING.md) para todos os modos do script de desenvolvimento, estrutura do projeto, testes e guias de estilo de código.

## Comunidade

<p align="center">
  <a href="https://cachibot.ai">
    <img src="https://img.shields.io/badge/Website-cachibot.ai-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Website" />
  </a>
  <a href="https://discord.gg/93QEWZeHRK">
    <img src="https://img.shields.io/badge/Discord-Junte_se_à_comunidade-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" />
  </a>
  <a href="https://github.com/jhd3197/CachiBot/issues">
    <img src="https://img.shields.io/badge/Issues-Reporte_um_bug-red?style=for-the-badge&logo=github&logoColor=white" alt="Issues" />
  </a>
</p>

## Licença

Licença MIT — veja [LICENSE](../LICENSE) para detalhes.

## Créditos

- Construído com [Prompture](https://github.com/jhd3197/Prompture) para interação estruturada com LLM e drivers multimodais
- Sistema de plugins alimentado por [Tukuy](https://github.com/jhd3197/Tukuy)
- Nomeado em homenagem ao *cachicamo* venezuelano (tatu)

---

<p align="center">
  Feito com carinho por <a href="https://juandenis.com">Juan Denis</a>
</p>
