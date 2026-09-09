# job-hunt: busca empleo, adapta tu CV y practica entrevistas

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

job-hunt es una skill de búsqueda de empleo para Claude Code y Codex. Te ayuda a encontrar ofertas, decidir dónde postularte, preparar el CV y la carta de presentación y practicar entrevistas.

Dale al agente tus objetivos, tu CV o el enlace de una oferta. Comparará los requisitos con tu experiencia y se encargará de editar, maquetar y revisar los documentos. Incluye orientación para perfiles técnicos y de investigación, cambios de carrera, periodos sin empleo, recién graduados y candidaturas internacionales.

## Empieza por el paso que necesitas

| Modo | Cuándo usarlo | Resultado principal |
|---|---|---|
| **discover · Buscar ofertas** | Quieres encontrar puestos en tu área de interés | Lista de ofertas, enlaces originales y orientación inicial |
| **assess · Valorar la candidatura** | Tienes una oferta y quieres decidir si merece dedicarle tiempo | Requisitos vinculados a evidencias, condiciones excluyentes, carencias y orientación |
| **apply · Preparar documentos** | Has elegido un puesto y necesitas materiales adaptados | CV, carta de presentación opcional, registros de revisión y guía de preparación para la entrevista |
| **interview · Practicar** | Tienes una oferta y un CV y quieres ensayar tus respuestas | Una ronda de entrevista, transcripción, dos evaluaciones independientes y cuestiones pendientes |

Puedes usar cada modo por separado. Al terminar una ronda, el agente propone los siguientes pasos y tú decides si continúas. Tú presentas la candidatura con los documentos terminados.

Después de instalarlo, prueba estas peticiones:

```text
Usa job-hunt para buscar puestos de reconstrucción de imágenes por resonancia magnética en los Países Bajos.
Usa job-hunt. Aquí tienes una oferta y mi CV. ¿Merece la pena postularme?
Usa job-hunt para adaptar mi CV a este puesto y redactar una carta de presentación.
Usa job-hunt para hacer una entrevista técnica simulada a partir de esta oferta y mi CV.
```

El agente confirma primero la tarea y el mercado de destino, y después pide los materiales y las preferencias que falten.

## Cómo prepara tu candidatura

Antes de editar el CV, el agente comprueba tu experiencia en el perfil, tus respuestas, artículos y proyectos. Ajusta el orden y la redacción, y enumera los puntos que necesitan más información. Trabaja sobre una copia y conserva el perfil original.

Para valorar una oferta, compara cada requisito con tu experiencia e indica cuáles cumples, cuáles cumples en parte y cuáles necesitan más evidencia. Los permisos de trabajo, las licencias y otras condiciones de acceso aparecen primero, seguidos de consejos para la candidatura y la información que debes añadir.

Un CV convencional pasa por tres revisiones independientes de IA. El revisor ATS comprueba las palabras clave y la lectura del archivo; el de selección, la claridad y los requisitos básicos; y el responsable de contratación, la experiencia y las funciones. El agente corrige y vuelve a revisar hasta un máximo de tres rondas, y señala los puntos que requieren más experiencia o documentación.

Después de una entrevista simulada, dos evaluaciones independientes revisan la calidad de las respuestas y su respaldo factual. La devolución indica qué detalles conviene añadir y qué frases del CV necesitan cambios.

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

### Primer uso: deja la configuración al agente

Tras la instalación, dile al agente: «Configura job-hunt y empieza mi tarea con mi navegador habitual».

El agente comprueba el entorno e instala lo necesario: dependencias de Python, Node.js, OpenCLI, [AnySearch](https://github.com/anysearch-ai/anysearch-skill), [web-access](https://github.com/eze-is/web-access) y herramientas de documentos. Después continúa la tarea. **La conexión del navegador usa CDP por defecto y no requiere extensiones.**

Cuando el entorno lo permite, el agente conecta con tu navegador habitual y aprovecha la sesión abierta. La primera vez puede que tengas que activar la depuración remota en `chrome://inspect/#remote-debugging` y aceptar la solicitud de Chrome. El agente comprueba la compatibilidad y te explica los pasos necesarios.

AnySearch permite acceso anónimo sin clave API. Las fuentes independientes se consultan a la vez cuando es posible para reducir la espera. Tú completas los inicios de sesión, las verificaciones y los permisos del navegador.

Consulta la [configuración del entorno](references/agent-setup.md) y las [conexiones del navegador y búsquedas paralelas](references/daily-browser.md) para más detalles.

### Si un portal de empleo no se puede leer

El agente comprueba los problemas conocidos de Indeed y 51job y aplica la corrección adecuada. Los parches actuales son para OpenCLI 1.8.7; las demás versiones se comprueban por separado.

También puedes pedirle que busque directamente en el buscador del portal. Para revisar un problema, di «comprueba los parches de compatibilidad» o «revierte los parches de compatibilidad». Consulta las [instrucciones de comprobación y reversión](references/opencli-compat.md).

## Mercados, plataformas e idiomas

El agente elige fuentes para tu mercado de destino y las lee desde el navegador o un adaptador de OpenCLI disponible. Incluyen 51job, Indeed, LinkedIn y BOSS Zhipin. El adaptador de Indeed conecta actualmente con Estados Unidos; para otros mercados se priorizan las fuentes locales. El [catálogo de fuentes](references/discovery-sources.md) explica los requisitos de acceso y los usos; la [política de fuentes](references/source-policy.md) detalla las reglas de consulta.

Para China, el agente pregunta si prefieres grandes empresas privadas, pequeñas y medianas empresas privadas, empresas estatales o extranjeras, y usa la respuesta para ordenar las ofertas. Nowcoder y 1point3acres aportan experiencias de entrevistas y contexto sobre los procesos de selección.

Si un sitio exige iniciar sesión o completar una verificación, el agente pausa esa fuente y te indica qué hacer. Responde «listo, continúa» para reanudar la comprobación. Si sigue sin haber acceso, puedes probar más tarde, pegar el texto de la oferta o revisar los resultados ya recogidos.

Los títulos y las etiquetas de datos personales del CV están disponibles en inglés, neerlandés, alemán, francés, español, italiano, chino, japonés y coreano. Los informes de búsqueda y valoración usan [plantillas](references/report-localization.md) en chino, inglés, japonés, coreano y español. Algunos documentos internos están en inglés. El agente comprueba las fuentes del PDF durante la configuración.

El proyecto incluye 5 tablas de convenciones de mercado con 38 entradas para Estados Unidos, Reino Unido, Alemania, Países Bajos y China. Cada entrada tiene fuente, ámbito de aplicación y fecha de revisión. El agente señala la información desactualizada o ausente; los requisitos de la empresa guían cada candidatura.

<p align="center">
  <img src="docs/assets/personal-data.jpg" alt="Ejemplos del repositorio: un CV para Estados Unidos omite datos personales y otro para Alemania conserva una foto y una fecha de nacimiento aportadas">
</p>

Las fotos y los datos personales se adaptan al mercado de destino. Los CV convencionales para Estados Unidos, Canadá, Reino Unido, Irlanda, Australia y Nueva Zelanda los omiten por defecto. Los demás mercados reconocidos siguen sus reglas con los datos que aportes. Si el mercado está sin confirmar, esos campos se omiten.

## Qué recibes

| Material | Formatos y detalles |
|---|---|
| CV adaptado | Markdown, Word (`.docx`) y PDF; la composición en PDF también conserva `.tex` |
| Carta de presentación o motivación | Opcional; Markdown, Word y PDF |
| Rirekisho japonés (履歴書) | Un generador de formularios independiente crea una vista previa Markdown y un `.docx` editable; el formulario se exporta a PDF desde Word o LibreOffice |
| Declaración estructurada de competencias | Evidencias organizadas por criterio y comprobación de límites de palabras para solicitudes como las del NHS y la función pública británica |
| Material de evaluación y entrevista | Listas de ofertas, valoraciones de adecuación, guías de entrevista, transcripciones y análisis posterior |

Las solicitudes estructuradas revisan el supporting statement según los criterios de la empresa. Si también se exige un CV convencional, se le aplica por separado la revisión de los tres evaluadores. El rirekisho japonés se comprueba como formulario completo; el documento de trayectoria profesional que lo acompaña sigue el proceso de revisión del CV.

Cada consulta genera un informe PDF con el análisis profesional, las fuentes y las cuestiones pendientes. Se guarda en `~/Downloads/<workspace-name>/` junto con el CV y los demás documentos solicitados. Las siguientes etapas usan la misma carpeta. Puedes pedir cartas de presentación y entrevistas simuladas cuando las necesites.

La entrega usa las subcarpetas `简历/` (CV) y `报告/` (informe), con nombres como `简历.docx`, `简历.pdf` y `求职建议报告.pdf`.

Para investigar empresas o sectores, el agente también puede consultar sitios oficiales, noticias, cuentas públicas de WeChat y proyectos relevantes de GitHub mediante las [fuentes complementarias](references/supplementary-sources.md).

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

`make check` ejecuta las pruebas de Python, las comprobaciones del contenido migrado y las tablas de mercado. Las pruebas que usan herramientas externas necesitan tenerlas instaladas; las comprobaciones de la instalación local de la skill son opcionales.

[`evals/`](evals/README.md) contiene 20 escenarios de comportamiento. La segunda iteración (2026-09-05/06) ejecutó 15 escenarios con y sin la skill, una vez por grupo (n = 1). Diez comprobaciones pasaron de `FAIL` en la referencia a `PASS` con la skill. El [registro de evaluación](evals/iterations/iteration-2-with-skill.md) recoge los resultados, las comprobaciones pendientes y el escenario invalidado.

Los tres revisores de CV se probaron mediante `codex exec` el 2026-09-06. Consulta [portabilidad entre agentes](references/portability.md) para configurar otros entornos y conocer el alcance de las pruebas.

- [SKILL.md](SKILL.md): selección de modos y reglas principales.
- [REFERENCE.md](REFERENCE.md): arquitectura, espacios de trabajo, estructuras de datos y uso de scripts.
- [Perfil de ejemplo](assets/profile.example.yaml) y [ejemplo de fuentes de afirmaciones](assets/claims.example.yaml): formatos de datos estructurados.
- [Guía de evaluación](evals/README.md): métodos y limitaciones.

Estas referencias técnicas están redactadas principalmente en inglés. Distribuido bajo la [licencia MIT](LICENSE).
