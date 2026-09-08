# job-hunt: candidaturas respaldadas por experiencia real

<p align="center">
  <a href="README.md">简体中文</a> ·
  <a href="README_EN.md">English</a> ·
  <a href="README_JA.md">日本語</a> ·
  <a href="README_KO.md">한국어</a> ·
  <a href="README_ES.md"><strong>Español</strong></a>
</p>

<p align="center">
  <a href="LICENSE"><img alt="Licencia: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
  <img alt="Para Claude Code y Codex" src="https://img.shields.io/badge/agents-Claude_Code_·_Codex-5b5bd6">
  <a href="https://github.com/addsumtech/job-hunt/releases"><img alt="Versión: v1.0.0" src="https://img.shields.io/badge/release-v1.0.0-1f883d"></a>
</p>

<p align="center">
  <img src="docs/assets/hero.jpg" alt="Afirmaciones de un CV conectadas con sus fuentes: un artículo, notas, certificados y proyectos">
</p>

**Busca ofertas, decide dónde postularte, adapta tus documentos y practica la entrevista. Explica con claridad tu experiencia y los requisitos que aún no cumples.**

job-hunt es una skill de búsqueda de empleo para Claude Code y Codex. Tú aportas un objetivo, un CV o una oferta. El agente lee los materiales, comprueba las evidencias, adapta el texto, lo maqueta y lo revisa; los scripts de Python verifican las fuentes, la coherencia entre archivos y las condiciones de entrega. Incluye orientación para perfiles técnicos, de investigación y de otras áreas, así como para cambios de carrera, periodos sin empleo, recién graduados y candidaturas internacionales.

El objetivo es que puedas explicar cada línea del CV en una entrevista a partir de tu experiencia.

## Empieza por el paso que necesitas

| Modo | Cuándo usarlo | Resultado principal |
|---|---|---|
| **discover · Buscar ofertas** | Tienes una dirección y quieres encontrar puestos que explorar | Lista de ofertas con fuentes reales, estado de consulta y valoraciones provisionales |
| **assess · Valorar la candidatura** | Tienes una oferta y quieres decidir si merece dedicarle tiempo | Requisitos vinculados a evidencias, condiciones excluyentes, carencias y orientación |
| **apply · Preparar documentos** | Has elegido un puesto y necesitas materiales adaptados | CV, carta de presentación opcional, registros de revisión y guía de preparación para la entrevista |
| **interview · Practicar** | Tienes una oferta y un CV y quieres ensayar tus respuestas | Una ronda de entrevista, transcripción, dos evaluaciones independientes y cuestiones pendientes |

Puedes usar cada modo por separado. Al terminar una ronda, tú eliges si continúas con alguno de los siguientes pasos sugeridos. Una lista de ofertas no se convierte automáticamente en un lote de CV. Tú decides si envías los documentos terminados y realizas el envío.

Después de instalarlo, prueba estas peticiones:

```text
Usa job-hunt para buscar puestos de reconstrucción de imágenes por resonancia magnética en los Países Bajos.
Usa job-hunt. Aquí tienes una oferta y mi CV. ¿Merece la pena postularme?
Usa job-hunt para adaptar mi CV a este puesto y redactar una carta de presentación.
Usa job-hunt para hacer una entrevista técnica simulada a partir de esta oferta y mi CV.
```

El agente confirma primero el modo y el mercado de destino, y después solicita las preferencias y los materiales necesarios. Tú confirmas el mercado; no se deduce de tus antiguos lugares de trabajo ni del idioma de la conversación.

## Cómo se convierte la experiencia en una candidatura

**Las afirmaciones tienen una fuente.** Cada habilidad, herramienta, responsabilidad o resultado nuevo debe proceder de una parte concreta de tu perfil original, de una respuesta que hayas dado durante la sesión o de un artículo o proyecto tuyo que el agente haya leído. La experiencia existente se puede reorganizar, destacar y reformular. Lo que carece de respaldo permanece en la lista de carencias. `claims.yaml` registra esas relaciones y la adaptación se hace sobre una copia del perfil, conservando el original.

**La valoración muestra sus evidencias.** Cada requisito imprescindible se clasifica como suficientemente respaldado, parcialmente respaldado o sin respaldo. Las condiciones excluyentes, como los permisos de trabajo o las licencias, aparecen primero. Si los materiales son insuficientes, devuelve `insufficient_evidence` y explica qué falta. El proyecto prohíbe inventar probabilidades de entrevista o contratación y puntuaciones arbitrarias de adecuación de 0–100; la comprobación de expresiones predictivas detecta frases predefinidas en los nueve idiomas del CV. La cobertura de palabras clave del ATS describe el texto, no las posibilidades de contratación.

**Un CV convencional pasa por tres revisiones independientes de IA.** El revisor ATS comprueba las palabras clave y la facilidad de análisis; el revisor de selección, la legibilidad y los requisitos básicos; y el responsable de contratación, la experiencia, el alcance de las funciones y la credibilidad. Cada uno trabaja en un contexto nuevo. Los tres deben emitir `PASS` para superar esta revisión interna. Los problemas corregibles dan lugar a cambios y una nueva revisión, hasta un máximo de tres rondas. Si solo quedan carencias que ninguna reformulación veraz puede resolver, el proceso termina antes y explica el motivo.

**La entrevista se evalúa a partir de lo que realmente dijiste.** Una evaluación examina las respuestas y otra verifica las fuentes de los hechos. La skill ayuda a organizar experiencias existentes y aclarar detalles inciertos. Las afirmaciones del CV que no puedas respaldar pasan a una lista de correcciones.

## Instalación

Necesitas un entorno de agente capaz de ejecutar comandos locales y leer y escribir archivos, además de **Python 3.10+**. Para instalar con `npx` también necesitas Node.js/npm. Elige una de estas tres opciones.

### Opción 1: instalar con `npx skills`

```bash
npx skills add addsumtech/job-hunt
```

Selecciona el agente y el ámbito de instalación cuando se solicite. Usa `-g` para instalar a nivel de usuario, `-a claude-code` o `-a codex` para elegir el agente y `-y` para omitir las confirmaciones. La raíz del repositorio es la skill; los scripts y los archivos de referencia deben instalarse junto con ella.

### Opción 2: instalar como plugin de Claude Code

Ejecuta dentro de Claude Code:

```text
/plugin marketplace add addsumtech/job-hunt
/plugin install job-hunt@job-hunt
/reload-plugins
```

Se invoca con `/job-hunt:job-hunt`. Para actualizar el marketplace, ejecuta `/plugin marketplace update job-hunt`. Si mantienes tanto una copia manual como el plugin, la misma skill puede aparecer dos veces.

### Opción 3: clonar y crear un enlace simbólico

Útil para leer o modificar el código. Este ejemplo registra la skill en Claude Code:

```bash
git clone https://github.com/addsumtech/job-hunt.git
cd job-hunt
mkdir -p ~/.claude/skills
ln -s "$PWD" ~/.claude/skills/job-hunt
```

Para Codex, sustituye `~/.claude/skills` por `~/.codex/skills` en las dos últimas líneas. Si el destino ya existe, revisa primero la instalación existente.

### Instalar dependencias y comprobar el entorno

Entra en el **directorio raíz de job-hunt instalado**, donde están `SKILL.md` y `requirements.txt`, y ejecuta lo siguiente con Python 3.10+:

```bash
python3 -m venv ~/.venvs/job-hunt
source ~/.venvs/job-hunt/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/doctor.py
```

El comando de activación anterior es para macOS/Linux; en Windows, utiliza el script de activación del directorio `Scripts` del entorno. Haz que el agente utilice este mismo entorno de Python para ejecutar los scripts del proyecto. Los paquetes básicos son `PyYAML` y `python-docx`. `doctor.py --install` puede añadir los paquetes que falten en el entorno de Python actual.

| Función | Dependencia adicional | Qué ocurre si falta |
|---|---|---|
| PDF del CV y de la carta | Un motor LaTeX; se recomienda `tectonic` | Se pueden generar Markdown, Word y `.tex` para compilar después |
| Informes Markdown en PDF | `pandoc` y un motor LaTeX | Los informes entregados pueden quedar solo en Markdown |
| Extracción y comprobación del texto del PDF | `pdftotext`, de Poppler | No se puede verificar por completo la integridad del texto del PDF |
| Búsqueda de ofertas actuales | `opencli` y su entorno de navegador | Se puede evaluar, preparar documentos y practicar con una oferta pegada como texto |
| PDF en chino, japonés y coreano | Fuentes del idioma de salida | Hay que instalar fuentes adecuadas para una composición fiable |

`doctor.py` intenta generar un PDF real e informa de las capacidades que faltan. Su opción `--install` solo instala paquetes de Python; sigue las indicaciones del informe para instalar herramientas del sistema.

## Mercados, plataformas e idiomas

La búsqueda obtiene ofertas mediante adaptadores de `opencli`. El catálogo del repositorio incluye 51job, Indeed, LinkedIn y BOSS Zhipin, y distingue entre requisitos de acceso, ofertas de empleo y fuentes de experiencias de entrevistas. La disponibilidad se comprueba al ejecutar la búsqueda. El adaptador de Indeed documentado actualmente está orientado al sitio estadounidense; cambiar solo la ciudad no garantiza una búsqueda correcta en otro mercado. Consulta el [catálogo de fuentes](references/discovery-sources.md) y la [política de uso](references/source-policy.md), en inglés.

Para China, la skill también pregunta por preferencias de empresa: grandes empresas privadas, pequeñas y medianas empresas privadas, empresas estatales y empresas extranjeras. Estas preferencias afectan al orden sin excluir otras categorías de forma silenciosa. Nowcoder y 1point3acres aportan experiencias de entrevistas y contexto sobre el proceso; los hilos de foro no se convierten en ofertas.

Tú realizas cualquier inicio de sesión necesario. Si aparece un CAPTCHA, un límite de solicitudes o una negativa de la plataforma, se detiene la consulta de ese sitio durante la ronda y se informa de ello. Si no se pueden obtener ofertas reales, el resultado se identifica como una propuesta de líneas de búsqueda. La exploración es de solo lectura: no envía mensajes, no modifica perfiles en línea ni presenta candidaturas.

**Las reglas del mercado y el idioma de salida se tratan por separado.** El generador de CV incluye títulos de sección y etiquetas de datos personales en inglés, neerlandés, alemán, francés, español, italiano, chino, japonés y coreano. `discover` y `assess` generan y verifican las fichas de recuento, los títulos obligatorios y las aclaraciones en chino, inglés, japonés, coreano y español mediante las [plantillas de idioma del informe](references/report-localization.md). Algunos documentos internos, diagnósticos y fichas de convenciones con fuentes siguen sin traducir; los PDF también necesitan fuentes adecuadas para el idioma de salida.

El proyecto incluye **5 tablas de convenciones de mercado con 38 entradas** para Estados Unidos, Reino Unido, Alemania, Países Bajos y China, con fuentes y fechas de revisión. Señala las entradas cuya fecha de revisión ha vencido e informa cuando no hay datos para un mercado. Son información de contexto que debe leerse dentro del ámbito indicado en cada entrada.

<p align="center">
  <img src="docs/assets/personal-data.jpg" alt="Ejemplos del repositorio: un CV para Estados Unidos omite datos personales y otro para Alemania conserva una foto y una fecha de nacimiento aportadas">
</p>

Los datos personales siguen las reglas del mercado de destino. En los CV convencionales para Estados Unidos, Canadá, Reino Unido, Irlanda, Australia o Nueva Zelanda, el generador omite la foto y los campos de `contact.personal`, y el flujo explica el cambio. Los mercados no reconocidos también aplican la omisión por defecto. Otros mercados reconocidos pueden mostrar la información proporcionada según sus reglas. La imagen ilustra el comportamiento del generador; no significa que todas las empresas de un país exijan el mismo formato.

## Qué recibes

| Material | Formatos y detalles |
|---|---|
| CV adaptado | Markdown, Word (`.docx`) y PDF; la composición en PDF también conserva `.tex` |
| Carta de presentación o motivación | Opcional; Markdown, Word y PDF |
| Rirekisho japonés (履歴書) | Un generador de formularios independiente crea una vista previa Markdown y un `.docx` editable; el formulario se exporta a PDF desde Word o LibreOffice |
| Declaración estructurada de competencias | Evidencias organizadas por criterio y comprobación de límites de palabras para solicitudes como las del NHS y la función pública británica |
| Material de evaluación y entrevista | Listas de ofertas, valoraciones de adecuación, guías de entrevista, transcripciones y análisis posterior |

Las solicitudes estructuradas revisan el supporting statement según los criterios de la empresa. Si también se exige un CV convencional, se le aplica por separado la revisión de los tres evaluadores. El rirekisho japonés se comprueba como formulario completo; el documento de trayectoria profesional que lo acompaña sigue el proceso de revisión del CV.

Los materiales legibles de cada ronda se entregan por defecto en `~/Downloads`, por ejemplo `<company>-<role>-<date>-cv.md` y su PDF. La generación y verificación del PDF dependen de las herramientas disponibles; el informe de entrega identifica archivos ausentes y comprobaciones incompletas.

## Dónde se guardan los archivos

Los perfiles originales, los espacios de trabajo de cada candidatura y los registros de comprobación se guardan por defecto en `~/.claude/job-profiles/`, también al usar Codex. Puedes indicar otro directorio raíz con `JOBHUNT_PROFILES_ROOT`.

Cada persona puede conservar perfiles originales por idioma, como `profile.zh.yaml` y `profile.en.yaml`; el archivo anterior `profile.yaml` sigue siendo compatible. Las candidaturas tienen espacios de trabajo separados, y los registros de fuentes junto con `journal.jsonl` conservan el historial de comprobaciones. Consulta la estructura completa en [REFERENCE.md](REFERENCE.md), en inglés.

Los archivos se almacenan localmente. Las llamadas al modelo y el acceso web dependen del agente elegido y de la configuración de sus servicios.

## Verificación y documentación

Las comprobaciones automáticas cubren las referencias a evidencias, la conservación del perfil original, la lectura de los veredictos, los datos personales, la composición y los cambios de modo:

```bash
python3 -m pip install pytest
make check
make eval-lint
```

`make check` ejecuta las pruebas de Python, la comprobación de conservación del contenido migrado y las comprobaciones de las tablas de mercado. Algunas pruebas inspeccionan la instalación local de la skill y las herramientas externas; sus resultados deben interpretarse según ese entorno. **Superar las comprobaciones no garantiza que el resultado sea correcto** ni demuestra resultados de búsqueda de empleo.

[`evals/`](evals/README.md) contiene 20 escenarios de evaluación del comportamiento. La segunda iteración registrada, del 2026-09-05/06, emparejó 15 escenarios con y sin la skill. Diez comprobaciones diseñadas para distinguir los grupos pasaron de `FAIL` en la referencia a `PASS` con la skill. **Solo hubo una ejecución por escenario y grupo, n = 1**. No es una tasa de éxito estable ni una predicción de contratación. El registro completo incluye comprobaciones no ejercitadas y un resultado de escenario invalidado: consulta el [registro de evaluación](evals/iterations/iteration-2-with-skill.md).

El repositorio también documenta una verificación del 2026-09-06 de los tres revisores de CV mediante `codex exec`. Consulta [portabilidad entre agentes](references/portability.md) para conocer los mecanismos y el alcance de la verificación. Los entornos no probados no se presentan como integraciones verificadas.

- [SKILL.md](SKILL.md): selección de modos y reglas principales.
- [REFERENCE.md](REFERENCE.md): arquitectura, espacios de trabajo, estructuras de datos y uso de scripts.
- [Perfil de ejemplo](assets/profile.example.yaml) y [ejemplo de fuentes de afirmaciones](assets/claims.example.yaml): formatos de datos estructurados.
- [Guía de evaluación](evals/README.md): métodos y limitaciones.

Estas referencias técnicas están redactadas principalmente en inglés. Distribuido bajo la [licencia MIT](LICENSE).
