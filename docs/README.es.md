<div align="center">
  <img src="../assets/hero.png" alt="CachiBot" width="800" />

  <h1>CachiBot</h1>

  <p><strong>El Agente de IA Blindado</strong></p>
  <p><em>Visual. Transparente. Seguro.</em></p>

  <p>
    <a href="../README.md">English</a> ·
    Español ·
    <a href="README.zh-CN.md">中文版</a> ·
    <a href="README.pt.md">Português</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows" />
    <img src="https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white" alt="macOS" />
    <img src="https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" />
  </p>

  <p>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/v/cachibot.svg" alt="PyPI" /></a>
    <a href="https://pypi.org/project/cachibot"><img src="https://img.shields.io/pypi/dm/cachibot.svg" alt="Descargas" /></a>
    <a href="https://github.com/jhd3197/CachiBot/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="Licencia" /></a>
    <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python" /></a>
    <a href="https://react.dev"><img src="https://img.shields.io/badge/React-18+-61DAFB.svg" alt="React" /></a>
    <a href="https://github.com/jhd3197/CachiBot/stargazers"><img src="https://img.shields.io/github/stars/jhd3197/CachiBot?style=social" alt="Estrellas" /></a>
    <a href="https://discord.gg/V9bKwYVJ"><img src="https://img.shields.io/discord/1470624345188732992?label=Discord&logo=discord&logoColor=white&color=5865F2" alt="Discord" /></a>
  </p>

  <p>
    Una plataforma de agentes de IA visual con transparencia total. Nombrado en honor al <em>cachicamo</em> venezolano (armadillo) — construido para ser blindado, auditable y bajo tu control.
  </p>

  <p>
    <a href="#-inicio-rápido">Inicio Rápido</a> ·
    <a href="#-características">Características</a> ·
    <a href="#-arquitectura">Arquitectura</a> ·
    <a href="#-seguridad">Seguridad</a> ·
    <a href="#-contribuir">Contribuir</a> ·
    <a href="https://discord.gg/V9bKwYVJ">Discord</a>
  </p>

</div>

---

## ¿Por qué Visual?

La mayoría de los agentes de IA se ejecutan en terminales donde no puedes ver lo que está sucediendo. Eso es una pesadilla de seguridad.

Los agentes basados en CLI operan en una caja negra — sin visibilidad de las tareas en ejecución, sin forma de monitorear múltiples bots, sin información en tiempo real de lo que el agente está haciendo.

**CachiBot te da visibilidad completa.** Observa cómo trabajan tus bots a través de un tablero, ve cada tarea y trabajo en una interfaz limpia, aprueba o rechaza acciones antes de que se ejecuten, y mantén un registro de auditoría completo de todo lo que hacen tus bots.

<p align="center">
  <img src="../assets/dashboard.jpeg" alt="Tablero" width="800" />
</p>

<p align="center">
  <img src="../assets/chat.png" alt="Interfaz de Chat" width="800" />
</p>

## Características

- **Tablero Visual** — Ve todos tus bots, su estado y actividad de un vistazo
- **Monitoreo en Tiempo Real** — Observa la ejecución de tareas y trabajos con actualizaciones en vivo por WebSocket
- **Gestión Multi-Bot** — Crea y gestiona múltiples bots especializados
- **Conexiones de Plataforma** — Conecta bots a Telegram, Discord y más
- **Base de Conocimiento** — Sube documentos para dar conocimiento especializado a los bots
- **Sandbox Seguro** — El código se ejecuta aislado con análisis de riesgo basado en AST
- **Flujo de Aprobación** — Aprobación visual para operaciones riesgosas antes de ejecutarse
- **Multi-Proveedor** — Kimi K2.5, Claude, OpenAI, Ollama, Groq y más

## Inicio Rápido

### 1. Instalar

```bash
pip install cachibot
```

### 2. Configura tu clave API

```bash
# Moonshot/Kimi (predeterminado)
export MOONSHOT_API_KEY="tu-clave"

# O Claude
export ANTHROPIC_API_KEY="tu-clave"

# O OpenAI
export OPENAI_API_KEY="tu-clave"
```

### 3. Lanzar

```bash
cachibot server
```

Abre **http://localhost:6392** — el frontend viene empaquetado y se sirve automáticamente.

### Uso de CLI

```bash
cachibot server                              # Inicia el tablero
cachibot "listar todos los archivos Python"  # Ejecuta una tarea única
cachibot                                     # Modo interactivo
cachibot --model anthropic/claude-sonnet-4-20250514 "explica esto"  # Modelo específico
cachi server                                 # Alias corto
```

## Arquitectura

```mermaid
graph TB
    subgraph Frontend["React Dashboard"]
        Bots[Bots]
        Chats[Chats]
        Jobs[Jobs & Tasks]
        KB[Knowledge Base]
        Conn[Connections]
    end

    subgraph Backend["FastAPI Backend"]
        Agent["Prompture Agent"]
        Tools["Tool Registry"]
        Sandbox["Sandbox Executor"]
    end

    subgraph Providers["LLM Providers"]
        Moonshot[Moonshot/Kimi]
        Claude[Claude]
        OpenAI[OpenAI]
        Ollama[Ollama]
        Groq[Groq]
    end

    subgraph Platforms["Platform Connections"]
        Telegram[Telegram]
        Discord[Discord]
    end

    Frontend -- "WebSocket / REST" --> Backend
    Backend --> Providers
    Backend --> Platforms
```

## Modelos Soportados

| Proveedor | Modelo | Variable de Entorno |
|----------|-------|---------------------|
| Moonshot | `moonshot/kimi-k2.5` | `MOONSHOT_API_KEY` |
| Claude | `anthropic/claude-sonnet-4-20250514` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Ollama | `ollama/llama3.1:8b` | (local, sin clave necesaria) |
| Groq | `groq/llama-3.1-70b` | `GROQ_API_KEY` |

## Seguridad

CachiBot está construido con la seguridad como principio fundamental. **La visibilidad es seguridad** — el mayor riesgo con los agentes de IA es no saber qué están haciendo.

### Ejecución en Sandbox

El código Python se ejecuta en un entorno restringido:

- **Restricciones de Importación** — Solo se permiten módulos seguros (json, math, datetime, etc.)
- **Restricciones de Ruta** — Acceso a archivos limitado al espacio de trabajo
- **Tiempo de Ejecución Límite** — El código se detiene después del tiempo límite (predeterminado: 30s)
- **Análisis de Riesgo** — Detección basada en AST de operaciones peligrosas

### Siempre Bloqueado

Estos nunca se permiten independientemente de la configuración: `subprocess`, `os.system`, `ctypes`, `socket`, `ssl`, `importlib`, `eval`, `exec`, `pickle`, `marshal`.

## Hoja de Ruta

- [x] Tablero visual con monitoreo en tiempo real
- [x] Gestión multi-bot
- [x] Ejecución de Python en sandbox
- [x] Soporte multi-proveedor de LLM
- [x] Base de conocimiento con carga de documentos
- [x] Integración con Telegram
- [x] Integración con Discord
- [ ] Mercado de plugins
- [ ] Interfaz de voz
- [ ] Aplicación móvil complementaria

## Contribuir

¡Las contribuciones son bienvenidas!

```bash
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot

# Backend
pip install -e ".[dev]"
cachibot server --reload

# Frontend (en otra terminal)
cd frontend && npm install && npm run dev

# Pruebas y linting
pytest
ruff check src/
cd frontend && npm run lint
```

## Comunidad

<p align="center">
  <a href="https://discord.gg/V9bKwYVJ">
    <img src="https://img.shields.io/badge/Discord-Únete_a_la_comunidad-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" />
  </a>
  <a href="https://github.com/jhd3197/CachiBot/issues">
    <img src="https://img.shields.io/badge/Issues-Reporta_un_error-red?style=for-the-badge&logo=github&logoColor=white" alt="Issues" />
  </a>
</p>

## Licencia

Licencia MIT — ver [LICENSE](LICENSE) para más detalles.

## Créditos

- Construido con [Prompture](https://github.com/jhd3197/Prompture) para interacción estructurada con LLM
- Nombrado en honor al *cachicamo* venezolano (armadillo)

---

<p align="center">
  Hecho con cariño por <a href="https://juandenis.com">Juan Denis</a>
</p>
