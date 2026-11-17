# Guía de instalación y uso (desde un equipo limpio)

Esta guía te lleva desde un Windows sin herramientas hasta ver Mars Explorer funcionando,
probarlo y entender qué estás viendo. Cada comando indica **dónde** ejecutarlo, **qué hace**,
**qué deberías ver** y **qué hacer si falla**.

> Convención: "la raíz del proyecto" es `C:\Users\<tu-usuario>\Documents\Programacion\mars-explorer`.
> En VS Code abre una terminal con *Terminal → New Terminal* (o `Ctrl+ñ`). Por defecto se abre
> en la raíz del proyecto: verás `PS C:\...\mars-explorer>`.

---

## 1. Herramientas (una sola vez por equipo)

| Programa | Para qué | Comando de instalación |
|---|---|---|
| Git | control de versiones | `winget install --id Git.Git -e --source winget` |
| uv | instala Python 3.13 y las librerías del backend | `winget install --id astral-sh.uv -e` |
| Node.js 26 LTS | ejecuta el frontend (incluye npm) | `winget install --id OpenJS.NodeJS.LTS -e` |

Después de instalarlos, **cierra y vuelve a abrir VS Code** (para que la terminal vea el nuevo PATH).

Comprueba:

```powershell
git --version; uv --version; node --version; npm --version
```

Deberías ver cuatro versiones (p. ej. `git version 2.56…`, `uv 0.13…`, `v26…`, `11…`).
Si alguna dice *"no se reconoce como nombre de un cmdlet"*: reinicia el PC; si persiste, reinstálala.

Instala Python 3.13 gestionado por uv (no toca ningún Python del sistema):

```powershell
uv python install 3.13
```

Configura tu identidad de Git (solo la primera vez):

```powershell
git config --global user.name "Tu Nombre"
git config --global user.email "tu-email@ejemplo.com"
```

**Opcional pero recomendado:** *Configuración de Windows → Aplicaciones → Configuración avanzada
de aplicaciones → Alias de ejecución de aplicaciones* → desactiva `python.exe` y `python3.exe`.
Ese "Python" es un acceso directo vacío de la Microsoft Store. En este proyecto usamos siempre `uv run`.

**Extensiones de VS Code recomendadas** (VS Code te las ofrecerá al abrir el proyecto):
Python, Ruff, Oxc y Vitest.

---

## 2. Preparar el proyecto

📁 **Dónde:** raíz del proyecto.

```powershell
.\scripts\setup.ps1 -Seed
```

**Qué hace:**
1. Comprueba que existen git, uv, node y npm.
2. `backend/`: crea un entorno virtual de Python 3.13 (`backend/.venv`) e instala las
   versiones exactas fijadas en `uv.lock` (`uv sync`).
3. `frontend/`: instala las versiones exactas de `package-lock.json` (`npm ci`).
4. Crea `.env` a partir de `.env.example` (los valores por defecto sirven).
5. Con `-Seed`: descarga de la NASA unas **111 imágenes reales** (unos 13 MB) de 8 sols
   repartidos por toda la misión, más las **708 localizaciones reales** del rover. Tarda
   ~1–2 minutos, porque espera entre peticiones para no saturar a la NASA.

**Qué deberías ver al final:**
```
Summary
  -> seed: success | records seen 111, new 111, ... files downloaded 222 ...
  -> waypoints: success | records seen 708, new 708 ...
Images         : 111 records across 8 sols
...
Setup complete.
```

**Si falla:**
- *"no se puede cargar el archivo … porque la ejecución de scripts está deshabilitada"* →
  ejecuta `powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -Seed`.
- Errores de red durante el seed → vuelve a lanzarlo. Es **idempotente**: no repite lo ya
  descargado.
- `seed: partial` → algunas imágenes no se pudieron bajar (la NASA falló puntualmente). La
  aplicación funciona igual, y un nuevo `uv run mars-ingest seed` (desde `backend/`) completa lo que falte.

---

## 3. Arrancar la aplicación

📁 **Dónde:** raíz del proyecto.

```powershell
.\scripts\dev.ps1
```

**Qué hace:** abre **dos ventanas nuevas de PowerShell**:
- *Mars Explorer - backend*: el API (FastAPI) en `http://127.0.0.1:8000`.
- *Mars Explorer - frontend*: la interfaz (Vite) en `http://localhost:5173`.

Espera a que ambos respondan y abre el navegador en **http://localhost:5173**.

**Qué deberías ver:** la pantalla **Mission Control**, con una imagen real de Navcam del sol 2022
en el centro, la localización del rover a la derecha, el recorrido real de ~45 km y la tira
de observaciones recientes abajo.

**Para pararlo:** cierra las dos ventanas (o pulsa `Ctrl+C` en cada una).

**Si falla:**
- La interfaz dice *"The Mars Explorer API is not reachable"* → mira la ventana del backend;
  si se cerró o muestra un error, arráncalo a mano:
  `cd backend; uv run uvicorn mars_explorer.api.app:app --reload --port 8000`
- *"Port 5173 is already in use"* → ya tienes otro frontend abierto; ciérralo o úsalo.
- La interfaz dice *"No observations in the local archive yet"* → no hay datos aún:
  `cd backend; uv run mars-ingest seed` y recarga la página.

### Arranque manual (para entender las piezas)

Terminal 1, en `backend/`:
```powershell
uv run uvicorn mars_explorer.api.app:app --reload --port 8000
```
Verás `Uvicorn running on http://127.0.0.1:8000`. `--reload` reinicia el servidor al guardar código.

Terminal 2, en `frontend/`:
```powershell
npm run dev
```
Verás `Local: http://localhost:5173/`. El navegador solo habla con Vite, y Vite reenvía
todo lo que empieza por `/api` al backend (lo configura `frontend/vite.config.ts`).

---

## 4. Qué puedes hacer y mirar

**En Mission Control:**
- Haz clic en las miniaturas de abajo o usa **← / →** para recorrer las observaciones.
- **Selected observation** (izquierda): metadatos reales (hora UTC y hora solar local LMST,
  orientación del mástil, factor de reducción a bordo, secuencia…). El recuadro amarillo
  explica los límites científicos de la imagen.
- **REAL · NASA/JPL-Caltech**: la insignia de procedencia. Cuando haya datos derivados o
  simulados (en fases posteriores), se verán de otra forma, inconfundible.
- **View on NASA**: abre la página oficial de esa imagen, para comprobar que es auténtica.
- **Traverse** (derecha): pasa el ratón por el mapa o por el perfil de elevación y verás el
  sol, la distancia y la altitud de cada localización real. El rover ha subido unos 634 m
  netos desde el fondo del cráter.
- El menú de la izquierda muestra los módulos futuros, con lo que harán en cada fase. No
  contienen nada falso.

**La documentación interactiva del API:** abre **http://127.0.0.1:8000/docs**. Puedes ejecutar
cada endpoint con *Try it out* y ver el JSON real.

**En Explorer** (menú izquierdo → *Explorer*):
- **Filtros** a la izquierda: identificador, rango de sols, fecha terrestre (UTC) y cámaras. Los
  filtros quedan en la URL, así que puedes guardar o compartir una búsqueda y el botón *Atrás* funciona.
- **Mission timeline** (arriba): dónde caen los sols que tienes guardados dentro de toda la misión.
  Haz clic en una barra para filtrar ese sol.
- Haz clic en una imagen para abrir el **visor**: rueda del ratón para hacer zoom (centrado en el
  cursor), arrastrar para moverte, doble clic o `0` para ajustar, `1` para ver a resolución nativa.
  *Full resolution PNG* descarga el original completo de la NASA la primera vez.
- **← / →** (o *Earlier / Later*) recorren las imágenes en orden cronológico dentro del filtro.
- **Inspector** (derecha): todos los metadatos, enlaces a la NASA y *Show original NASA record*,
  que muestra el JSON original sin modificar.
- **Stereo pair**: muchas cámaras toman imágenes izquierda y derecha a la vez. *Fetch from NASA*
  descarga la otra mitad si la NASA la ha publicado (si no, te lo dice). *Compare* abre la
  comparación *Side by side* (zoom sincronizado) o *Swipe* (cortinilla arrastrable).
- **Add data from NASA** (abajo a la izquierda): elige sol y cámaras, pulsa *Check NASA* para ver
  cuántas imágenes existen y *Download* para descargarlas en segundo plano con barra de progreso.

**En Perception** (menú izquierdo → *Vision*):
- Elige una imagen (o pulsa *Analyze in Perception* desde el Explorer).
- A la izquierda, los **métodos**: candidatos a roca (dos detectores distintos), realce CLAHE,
  bordes, clases de textura (experimental) y puntos ORB. Cada uno se ejecuta al seleccionarlo.
- A la derecha, los **parámetros** (con su explicación) y *Run*; debajo, resultados, tiempos,
  la **definición de la puntuación** (no es una probabilidad) y las **limitaciones**.
- Abajo, **Layers**: activa/desactiva capas y ajusta su opacidad.
- **Evaluar un detector**: pulsa *Mark rocks* y haz clic en el centro de cada roca que
  consideres obstáculo (marca todas las de la zona). Verás precisión, recall y F1 frente a
  *tu* interpretación. *Undo last* / *Clear all* para corregir.
- **Stereo match** (arriba): si la pareja estéreo está guardada (*Fetch from NASA* en Explorer),
  empareja rasgos entre los dos ojos y mide la disparidad en píxeles.
- En la página inicial de Perception, *Run benchmark* compara los dos detectores en 40 imágenes.
  Desde la terminal: `cd backend; uv run mars-vision benchmark` (escribe el informe en
  `docs/benchmarks/perception-benchmark.md`).

**En Terrain** (menú izquierdo → *Terrain*). La primera vez descarga el DEM orbital real
(unos 325 MB): `cd backend; uv run mars-terrain fetch` (se puede reanudar si se corta).
- **Mapa general** (arriba a la izquierda): todo el DEM con el recorrido real del rover; haz clic
  para mover el mapa de trabajo y elige el tamaño (400 m – 3 km).
- **Replan a real drive**: elige un rango de conducciones reales y pulsa *Load these drives*;
  el inicio y el destino son los extremos reales y la ruta del rover se compara con cada plan.
- O pulsa **Set start (A)** y **Set goal (B)** y haz clic en el mapa.
- Capas: *Relief* (relieve), *Risk* (clases de riesgo), *Slope* (pendiente), *Roughness* (rugosidad).
- A la derecha, el **modelo de costes** (supuestos ajustables), los **planificadores** y *Plan routes*.
  Verás la tabla comparativa, el perfil de elevación (pasa el ratón) y *Why this route*.
- *Assumptions and limitations*: qué supone el modelo y qué no puede ver (rocas < 1 m).

**En Replay** (menú izquierdo → *Replay*):
- **Mission timeline** (arriba): distancia real conducida en cada sol (barras) y, debajo, una
  marca por cada sol con imágenes guardadas. Pasa el ratón para ver detalles; haz clic para abrir ese sol.
- **Sol timeline**: cada punto es una imagen, colocada en su hora solar local (LMST); la barra
  naranja es la conducción real de ese sol. Clic en un punto → abre su secuencia (o la imagen en Explorer).
- **Reconstructed sequence**: reproduce los fotogramas reales en orden. Siempre lleva el sello
  *RECONSTRUCTED · not a NASA video*. *Real timing* respeta el tiempo real entre exposiciones
  (acelerado ×1–×30); *Fixed rate* va a fotogramas por segundo fijos. El tipo de secuencia te dice
  si lo que ves es cambio en el tiempo (*Fixed pointing*) o un barrido de cámara (*Pointing sweep*).
- **Featured sequences** (derecha): pulsa *Download … frames from NASA* (aterrizaje LCAM, 87
  fotogramas; horizonte del sol 2024, 21) y luego *Play reconstruction*.
- **Official NASA videos**: vídeos oficiales (aterrizaje, vuelos de Ingenuity), con su crédito,
  servidos directamente desde la NASA.

**En Assistant** (menú izquierdo → *Assist*): sin clave verás *AI assistant · not configured* con
los pasos, qué datos se enviarían y el coste. Para activarlo:
1. Crea una clave de API en <https://platform.claude.com> (*Settings → API keys*). Se paga por uso,
   aparte de cualquier suscripción a Claude.ai. Puedes poner un límite de gasto en la consola.
2. Abre el archivo `.env` de la raíz del proyecto y rellena la línea `ANTHROPIC_API_KEY=` con tu clave
   (sin comillas ni espacios). Opcional: `MARS_ASSISTANT_MODEL=claude-haiku-5-5` para gastar mucho menos.
3. Cierra las ventanas del backend y vuelve a ejecutar `.\scripts\dev.ps1`. En la ventana del
   backend verás `AI assistant: enabled (...)`.
4. En *Assist*, prueba una de las preguntas sugeridas. Cada respuesta lleva la etiqueta
   *AI-GENERATED*, las herramientas que usó, los tokens y el coste estimado.
El asistente solo **lee** datos de la app: no planifica rutas, no descarga nada y no cambia nada.

**Ampliar el archivo de imágenes desde la terminal** (en `backend/`):
```powershell
uv run mars-ingest images --sol 1201 --camera NAVCAM_LEFT --limit 20
uv run mars-ingest images --sol 900 --sol-max 905 --camera MCZ_LEFT --camera MCZ_RIGHT
uv run mars-ingest status
```
Lista de cámaras válidas: `NAVCAM_LEFT`, `NAVCAM_RIGHT`, `FRONT_HAZCAM_LEFT_A`, `REAR_HAZCAM_LEFT`,
`MCZ_LEFT`, `MCZ_RIGHT`, `SKYCAM`, `SUPERCAM_RMI`, `SHERLOC_WATSON`, `LCAM`, … (si escribes una
inválida, el comando te muestra todas). Ten en cuenta que no todos los sols tienen imágenes
de todas las cámaras: las Hazcams, por ejemplo, se usan sobre todo en sols de conducción.

**Inspeccionar los datos guardados:** `data/images/m2020/sol_02022/<id>/metadata.json` contiene
el registro original de la NASA, sin modificar.

---

## 5. Ejecutar las pruebas

📁 **Dónde:** raíz del proyecto.

```powershell
.\scripts\check.ps1        # todo, sin red: lint, tipos, tests y build
.\scripts\check.ps1 -Live  # además, 4 tests contra los servidores reales de la NASA
```

**Qué deberías ver:** `All checks passed.` (backend: 175 tests; frontend: 79 tests).

Por separado:
```powershell
cd backend;  uv run pytest -v          # tests del backend, con detalle
cd frontend; npm test                  # tests del frontend
```

Los tests del backend no usan la red: sustituyen a la NASA por un servidor simulado que
responde con **respuestas reales capturadas** (`backend/tests/fixtures/`). Los tests marcados
`live` sí consultan la NASA, para detectar si cambia el formato de sus datos.

**Si falla un test del frontend con *"Vitest failed to find the current suite"*:** ejecútalo
desde PowerShell (no desde Git Bash/MSYS). En Windows, una ruta con `c:` en minúscula hace que
Vitest se cargue dos veces.

---

## 6. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `uv`/`node` no se reconoce | PATH no actualizado | cierra y vuelve a abrir VS Code, o reinicia |
| Avisos de uv sobre `C:\msys64\...python.exe` | tienes MSYS2; uv lo ignora | inofensivo |
| Imagen "unavailable" en el visor | el backend no pudo descargarla de la NASA | revisa la conexión y vuelve a seleccionarla |
| `seed` tarda | pausas deliberadas entre peticiones | normal (~1–2 min) |
| Quiero empezar de cero | — | borra la carpeta `data/` y vuelve a ejecutar el seed |
| "Address already in use" en el puerto 8000 al arrancar | quedó vivo un proceso del backend (pasa si se cierra la ventana a la fuerza en vez de usar `Ctrl+C`) | `Get-NetTCPConnection -LocalPort 8000 -State Listen` muestra su PID (`OwningProcess`); ciérralo con `Stop-Process -Id <PID>`. Si el PID ya no existe, busca su proceso hijo de Python en el Administrador de tareas, o reinicia |
