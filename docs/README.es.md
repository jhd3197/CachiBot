<div align="center">
  <img src="../assets/hero.png" alt="CachiBot" width="800" />

  <h1>CachiBot</h1>

  <p><strong>El Agente de IA Blindado</strong></p>
  <p><em>Visual. Transparente. Seguro.</em></p>

  <p>
    <a href="../README.md">English</a> ·
    <a href="https://codewiki.google/github.com/jhd3197/cachibot">CodeWiki</a> ·
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
    <a href="https://react.dev"><img src="https://img.shields.io/badge/React-19-61DAFB.svg" alt="React" /></a>
    <a href="https://github.com/jhd3197/CachiBot/stargazers"><img src="https://img.shields.io/github/stars/jhd3197/CachiBot?style=social" alt="Estrellas" /></a>
    <a href="https://discord.gg/93QEWZeHRK"><img src="https://img.shields.io/discord/1470624345188732992?label=Discord&logo=discord&logoColor=white&color=5865F2" alt="Discord" /></a>
  </p>

  <p>
    Una plataforma de agentes de IA visual con transparencia total. Nombrado en honor al <em>cachicamo</em> venezolano (armadillo) — construido para ser blindado, auditable y bajo tu control.
  </p>

  <p>
    <a href="#instalación">Instalación</a> ·
    <a href="#características">Características</a> ·
    <a href="#proveedores-soportados">Proveedores</a> ·
    <a href="#seguridad">Seguridad</a> ·
    <a href="#contribuir">Contribuir</a> ·
    <a href="https://discord.gg/93QEWZeHRK">Discord</a>
  </p>

</div>

---

## ¿Por qué CachiBot?

La mayoría de las plataformas de IA te obligan a elegir: interfaces de chatbot sin automatización, constructores de workflows sin IA conversacional, o frameworks de desarrollo que toman semanas para producir algo.

**CachiBot te da los tres.** Crea bots especializados, despliégalos en cualquier plataforma de mensajería, ejecútalos en salas colaborativas y automatiza workflows — todo desde un tablero visual con transparencia total sobre lo que tus agentes están haciendo.

![arepa-war](https://github.com/user-attachments/assets/5996fc02-0c4c-4a61-a998-f007189494fd)

<p align="center">
  <a href="https://youtu.be/G8JEhkcRxD8">
    <img src="https://img.shields.io/badge/YouTube-Ver_Demo-red?style=for-the-badge&logo=youtube&logoColor=white" alt="Ver en YouTube" />
  </a>
  <a href="https://cachibot.ai/marketplace/rooms/great-arepa-war?utm_source=github&utm_medium=readme&utm_campaign=arepa_war_room">
    <img src="https://img.shields.io/badge/CachiBot-Ver_Sala-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Ver el Chat en CachiBot" />
  </a>
  <a href="https://dev.to/juandenis/ai-settles-the-ultimate-venezuelan-vs-colombian-arepa-debate-2ngm">
    <img src="https://img.shields.io/badge/Dev.to-Leer_Artículo-0A0A0A?style=for-the-badge&logo=devdotto&logoColor=white" alt="Leer en Dev.to" />
  </a>
</p>

## Instalación

### Linux / macOS

```bash
curl -fsSL cachibot.ai/install.sh | bash
```

Configura Python, un entorno virtual y un servicio systemd — todo lo que necesitas en un solo comando.

### Windows

```powershell
irm cachibot.ai/install.ps1 | iex
```

### pip

```bash
pip install cachibot
```

Luego inicia el servidor:

```bash
cachibot server
```

Abre **http://localhost:5870** — el frontend viene empaquetado y se sirve automáticamente. No necesitas un paso de build separado.

### Docker

```bash
docker compose up
```

### App de Escritorio

Descarga el instalador para tu plataforma desde [GitHub Releases](https://github.com/jhd3197/CachiBot/releases). Disponible como instalador NSIS (Windows), DMG (macOS) y AppImage/DEB/RPM (Linux). Incluye actualización automática.

### Configura tus claves API

Puedes configurar las claves API directamente desde la interfaz del tablero — no necesitas variables de entorno. Solo abre el panel de configuración y agrega tus claves ahí.

Si prefieres variables de entorno, también funcionan:

```bash
export OPENAI_API_KEY="tu-clave"       # OpenAI / GPT-4
export ANTHROPIC_API_KEY="tu-clave"    # Claude
export MOONSHOT_API_KEY="tu-clave"     # Kimi
# o usa Ollama localmente (no necesita clave)
```

### Uso de CLI

```bash
cachibot server                    # Inicia el tablero
cachibot "resume este proyecto"    # Ejecuta una tarea única
cachibot                           # Modo interactivo
cachibot --model claude/sonnet     # Sobreescribir modelo
cachibot --workspace ./mi-proyecto # Establecer workspace
cachibot --approve                 # Requerir aprobación para cada acción
cachibot --verbose                 # Mostrar proceso de razonamiento
cachibot diagnose                  # Verificar salud de la instalación
cachibot repair                    # Reparar instalación corrupta
cachi server                       # Alias corto
```

## Características

### Plataforma Multi-Agente

- **Bots Especializados Ilimitados** — Crea bots con prompts de sistema personalizados, enrutamiento de modelos por bot, toggles de capacidades y claves API aisladas por proveedor
- **Salas Colaborativas** — Ejecuta múltiples bots juntos con 9 modos de respuesta: paralelo, secuencial, cadena, router, debate, cascada, relay, consenso y entrevista
- **Marketplace de Bots** — Plantillas pre-construidas de bots y salas para casos de uso comunes, instalables desde el tablero

### Sistema de Plugins por Capacidades

Cada bot tiene un conjunto de toggles de capacidades que controlan qué herramientas están disponibles. Los plugins se cargan dinámicamente según estos toggles, impulsado por [Tukuy](https://github.com/jhd3197/Tukuy):

| Capacidad | Herramientas |
|-----------|-------------|
| Ejecución de Código | Python en sandbox con análisis de riesgo AST |
| Operaciones de Archivos | Leer, escribir, editar, listar, info — limitado al workspace |
| Operaciones Git | Status, diff, log, commit, branch |
| Acceso a Shell | Comandos de shell con restricciones de seguridad |
| Acceso Web | Obtener URLs, buscar en la web, peticiones HTTP |
| Operaciones de Datos | Consultas SQLite, compresión zip/tar |
| Gestión de Trabajo | Tareas, todos, jobs, funciones, programaciones |
| Generación de Imágenes | DALL-E, Google Imagen, Stability AI, Grok |
| Generación de Audio | OpenAI TTS, ElevenLabs, transcripción Whisper |
| Agentes de Código | Lanzar Claude Code, OpenAI Codex o Gemini CLI como sub-agentes |
| Base de Conocimiento | Búsqueda semántica en documentos subidos y notas |
| Instrucciones Personalizadas | Paquetes de instrucciones potenciados por LLM (análisis, escritura, desarrollo) |

### Integraciones de Plataforma

Despliega bots en **7 plataformas de mensajería** con adaptadores integrados. Las conexiones se almacenan encriptadas, se reconectan automáticamente al reiniciar el servidor y se monitorean:

Telegram · Discord · Slack · Microsoft Teams · WhatsApp · Viber · LINE

### Base de Conocimiento & RAG

- Sube documentos (PDF, TXT, MD, DOCX) — automáticamente fragmentados e incrustados
- Búsqueda por similitud vectorial con tamaño de fragmento, solapamiento y umbral de relevancia configurables
- Proveedores de embeddings: OpenAI, Ollama o FastEmbed local (sin clave API)
- Notas de texto libre como fuente de conocimiento adicional
- Almacenamiento: SQLite con similitud coseno o PostgreSQL con pgvector

### Gestión de Trabajo y Automatización

- **Ítems de Trabajo** — Unidades de nivel superior con seguimiento de estado (pendiente, en progreso, completado, fallido, cancelado, pausado)
- **Tareas** — Pasos dentro de ítems de trabajo con seguimiento de dependencias y bloqueo/desbloqueo automático
- **Jobs** — Ejecuciones de agente en segundo plano, gestionadas por un servicio de ejecución con progreso en tiempo real vía WebSocket
- **Todos** — Elementos de checklist livianos
- **Funciones** — Plantillas de tareas reutilizables con parámetros tipados y dependencias a nivel de paso
- **Programaciones** — Ejecución por cron, intervalo, una vez o por evento de funciones
- **Scripts** — Scripts de Python con historial de versiones, editor Monaco y sandbox de ejecución separado

### Conversaciones por Voz

Habla con tus bots con speech-to-text y text-to-speech en tiempo real a través de una interfaz de voz dedicada.

### API Compatible con OpenAI

CachiBot expone endpoints `/v1/chat/completions` y `/v1/models`, para que herramientas externas como Cursor o extensiones de VS Code puedan usar tus bots como si fueran modelos de OpenAI. Autenticado con claves API `cb-*` desde el panel de desarrollador. Soporta streaming vía SSE.

### Seguridad y Control

- **Flujos de Aprobación Visual** — Aprueba o rechaza operaciones riesgosas antes de que se ejecuten
- **Ejecución en Sandbox** — Python se ejecuta en aislamiento con puntuación de riesgo basada en AST (SEGURO / MODERADO / PELIGROSO)
- **Aislamiento de Workspace** — Todo acceso a archivos limitado al espacio de trabajo
- **Credenciales Encriptadas** — Secretos de conexión de plataformas almacenados con encriptación AES
- **Registro de Auditoría Completo** — Cada acción registrada con temporización, uso de tokens y costo

### Autenticación y Control de Acceso

- Autenticación basada en JWT con tokens de acceso y refresco
- Modo auto-hospedado con gestión de usuarios local vía asistente de configuración
- Roles de usuario (admin, usuario) con propiedad de bots y control de acceso basado en grupos
- Limitación de velocidad en endpoints de autenticación

## ¿Qué Puedes Construir?

- **Bot de Soporte al Cliente** — Despliega en Telegram con una base de conocimiento de tus documentos, responde FAQs automáticamente
- **Sala de Análisis de Datos** — 3 bots (especialista SQL + analista Python + redactor de reportes) colaborando en insights
- **Asistente de Voz** — Habla con un bot con STT/TTS, gestiona tareas y recordatorios sin manos
- **Pipeline de Contenido** — Bot investigador + bot escritor + generador de imágenes produciendo posts de blog de principio a fin
- **Agente DevOps** — Monitorea repos, ejecuta scripts en sandbox, envía alertas a Slack programadas
- **Asistente de Código** — Bot que lanza Claude Code o Codex para manejar tareas de programación complejas

## Proveedores Soportados

CachiBot usa [Prompture](https://github.com/jhd3197/Prompture) para gestión de modelos con auto-descubrimiento — configura una clave API y los modelos disponibles aparecen automáticamente.

| Proveedor | Modelos de Ejemplo | Variable de Entorno |
|-----------|-------------------|---------------------|
| OpenAI | GPT-4o, GPT-4, o1 | `OPENAI_API_KEY` |
| Anthropic | Claude Sonnet, Opus, Haiku | `ANTHROPIC_API_KEY` |
| Moonshot | Kimi K2.5 | `MOONSHOT_API_KEY` |
| Google | Gemini Pro, Flash | `GOOGLE_API_KEY` |
| Groq | Llama 3, Mixtral | `GROQ_API_KEY` |
| Grok / xAI | Grok-2 | `GROK_API_KEY` |
| OpenRouter | Cualquier modelo en OpenRouter | `OPENROUTER_API_KEY` |
| Azure OpenAI | GPT-4, GPT-4o | `AZURE_OPENAI_API_KEY` |
| ZhipuAI | GLM-4 | `ZHIPUAI_API_KEY` |
| ModelScope | Qwen | `MODELSCOPE_API_KEY` |
| Stability AI | Stable Diffusion (gen. imágenes) | `STABILITY_API_KEY` |
| ElevenLabs | Síntesis de voz | `ELEVENLABS_API_KEY` |
| Ollama | Cualquier modelo local | *(no necesita clave)* |
| LM Studio | Cualquier modelo local | *(no necesita clave)* |

Todas las claves también se pueden configurar desde la interfaz del tablero sin tocar variables de entorno.

## Seguridad

CachiBot está construido con la seguridad como principio fundamental. **La visibilidad es seguridad** — el mayor riesgo con los agentes de IA es no saber qué están haciendo.

### Ejecución en Sandbox

El código Python se ejecuta en un entorno restringido:

- **Restricciones de Importación** — Solo se permiten módulos seguros (json, math, datetime, etc.)
- **Restricciones de Ruta** — Acceso a archivos limitado al workspace vía SecurityContext
- **Tiempo de Ejecución Límite** — El código se detiene después del timeout (predeterminado: 30s)
- **Análisis de Riesgo** — Puntuación basada en AST (SEGURO / MODERADO / PELIGROSO) antes de la ejecución
- **Flujo de Aprobación** — Operaciones peligrosas requieren aprobación explícita a través del tablero

### Siempre Bloqueado

Estos nunca se permiten independientemente de la configuración: `subprocess`, `os.system`, `ctypes`, `socket`, `ssl`, `importlib`, `eval`, `exec`, `pickle`, `marshal`.

## Configuración

CachiBot soporta configuración por capas: las variables de entorno sobreescriben el TOML del workspace, que sobreescribe el `~/.cachibot.toml` del usuario, que sobreescribe los valores predeterminados. Consulta [`cachibot.example.toml`](../cachibot.example.toml) para todas las opciones.

Secciones clave: `[agent]` (modelo, temperatura, max iteraciones), `[sandbox]` (imports permitidos, timeout), `[knowledge]` (tamaño de fragmento, modelo de embedding, umbral de similitud), `[coding_agents]` (agente por defecto, timeout, rutas de CLI), `[database]` (URL de SQLite o PostgreSQL), `[auth]` (configuración JWT).

## Contribuir

¡Las contribuciones son bienvenidas! Consulta [CONTRIBUTING.md](../CONTRIBUTING.md) para la guía completa. Inicio rápido:

```bash
git clone https://github.com/jhd3197/CachiBot.git
cd CachiBot

# Backend
python -m venv venv && source venv/bin/activate  # o .\venv\Scripts\activate en Windows
pip install -e ".[dev]"

# Frontend
cd frontend && npm install && cd ..

# Desktop (opcional — solo si trabajas en el shell de Electron)
cd desktop && npm install && cd ..

# Ejecutar todo
bash dev.sh              # o .\dev.ps1 en Windows
bash dev.sh desktop      # con Electron
bash dev.sh watch-lint   # watcher de lint (ruff + ESLint al guardar)
```

Consulta [CONTRIBUTING.md](../CONTRIBUTING.md) para todos los modos del script de desarrollo, estructura del proyecto, pruebas y guías de estilo de código.

## Comunidad

<p align="center">
  <a href="https://cachibot.ai">
    <img src="https://img.shields.io/badge/Website-cachibot.ai-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Website" />
  </a>
  <a href="https://discord.gg/93QEWZeHRK">
    <img src="https://img.shields.io/badge/Discord-Únete_a_la_comunidad-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" />
  </a>
  <a href="https://github.com/jhd3197/CachiBot/issues">
    <img src="https://img.shields.io/badge/Issues-Reporta_un_error-red?style=for-the-badge&logo=github&logoColor=white" alt="Issues" />
  </a>
</p>

## Licencia

Licencia MIT — ver [LICENSE](../LICENSE) para más detalles.

## Créditos

- Construido con [Prompture](https://github.com/jhd3197/Prompture) para interacción estructurada con LLM y controladores multimodales
- Sistema de plugins impulsado por [Tukuy](https://github.com/jhd3197/Tukuy)
- Nombrado en honor al *cachicamo* venezolano (armadillo)

---

<p align="center">
  Hecho con cariño por <a href="https://juandenis.com">Juan Denis</a>
</p>
