# PROJECT_PROTOCOL

## Objetivo

Este documento define el comportamiento operativo de July dentro de un proyecto conectado.

No describe la UX final en terminos de comandos. Describe como debe actuar un agente que usa July como memoria y orquestador por detras.

Principio central:

- July debe ayudar a saber en que punto esta un proyecto, que se hizo, que queda pendiente y que merece reutilizarse.

## Principios base

- El estado real del codigo manda primero; despues mandan `README.md` y `ROADMAP.md`.
- CLI y MCP son infraestructura; la experiencia preferida para el usuario es conversacional.
- July no debe modificar por defecto `README.md`, `AGENTS.md` u otros archivos de un proyecto externo.
- Si July genera contexto derivado, debe preferir persistencia interna en la BD o un archivo propio tipo `JULY_CONTEXT.md`.
- No se deben guardar secretos, tokens, claves anonimas ni valores crudos de `.env` salvo peticion explicita del usuario.
- Toda sesion real debe usar `session-start`, `session-summary` y `session-end`.
- Toda aportacion relevante de un modelo externo debe registrarse con `model-contribution` o `save_model_contribution`.
- Si un tema se repite entre sesiones o proyectos, debe crearse un `topic_key` y enlazar los items relevantes.

## Paso 0: detectar el estado del proyecto

Antes de actuar, el agente debe:

1. Identificar una clave de proyecto estable.
2. Consultar `project-context` y `session-context`.
3. Leer la documentacion real disponible del repo y los archivos tecnicos relevantes para el trabajo.
4. Decidir si July esta ante un proyecto nuevo o ante un proyecto ya conocido.

Criterio operativo:

- `proyecto nuevo`: no existe contexto util suficiente para explicar que es el repo, como esta montado o cual deberia ser el siguiente paso.
- `proyecto conocido`: ya existe contexto reutilizable que permite retomar el trabajo sin releer el repo desde cero.

No basta con que haya un inbox item aislado. El proyecto solo debe tratarse como conocido si el contexto previo sirve de verdad para continuar.

## 1. Comportamiento en proyecto nuevo

Cuando el proyecto es nuevo para July, el agente debe:

1. Decir de forma natural que esta entrando en un proyecto nuevo y proponer onboarding o revision inicial.
2. Leer la documentacion y los entrypoints reales del repo para construir una primera foto fiable.
3. Identificar al menos:
   - objetivo del proyecto;
   - stack y arquitectura visible;
   - comandos o entrypoints utiles;
   - integraciones externas importantes;
   - dudas abiertas o zonas que requieren aclaracion.
4. Guardar un perfil inicial util del proyecto.
5. Abrir una sesion y dejar una primera traza que permita retomar el repo mas tarde sin empezar desde cero.

Resultado minimo esperado:

- el siguiente agente debe poder entender que es el proyecto y por donde continuar sin repetir toda la lectura inicial.

## 2. Comportamiento en proyecto ya conocido

Cuando el proyecto ya es conocido para July, el agente debe:

1. Recuperar contexto previo antes de pedir al usuario que repita informacion.
2. Resumir el estado actual del proyecto de forma util:
   - que es;
   - en que punto esta;
   - que decisiones, errores o pendientes siguen siendo relevantes.
3. Evitar rehacer onboarding si el contexto previo sigue siendo valido.
4. Si el contexto previo es insuficiente o contradictorio, hacer una revision selectiva y explicitar que parte falta por refrescar.
5. Abrir una sesion ligada al objetivo actual del trabajo.

Regla practica:

- proyecto conocido no significa proyecto completo; si falta contexto critico, el agente debe completar solo lo que falta.

## 3. Comportamiento durante la iteracion

Durante la iteracion, el agente debe usar July como memoria de trabajo y anti-regresion.

Debe registrar:

- errores resueltos y como se resolvieron;
- decisiones tecnicas con su razon principal;
- mejoras de flujo de trabajo que ahorren tiempo en la siguiente iteracion;
- hallazgos reutilizables entre proyectos o sesiones;
- referencias externas que merezca recuperar mas adelante;
- cambios en el estado real del proyecto que alteren el siguiente paso.

Debe preguntar antes de guardar cuando la senal sea ambigua:

- ideas no adoptadas;
- notas demasiado tentativas;
- informacion privada o sensible;
- detalles muy locales que no este claro si van a sobrevivir a esta iteracion.

Regla de densidad:

- July no debe convertirse en un volcado de ruido. Debe guardar lo bastante para retomar el proyecto, no todo lo que ocurre minuto a minuto.

## 4. Comportamiento al cierre

Antes de cerrar una iteracion, el agente debe:

1. Guardar `session-summary`.
2. Incluir en ese resumen:
   - que se hizo;
   - descubrimientos relevantes;
   - siguientes pasos;
   - archivos o zonas del repo especialmente relevantes si aporta valor.
3. Ejecutar `session-end`.
4. Dejar claro para la siguiente iteracion:
   - que esta resuelto;
   - que sigue pendiente;
   - que conviene reutilizar o recordar.

Una sesion cerrada debe permitir reanudar el trabajo sin depender de la memoria del chat actual.

## 5. Reglas de que guardar y que no

Guardar de forma directa cuando el dato sea:

- durable;
- reutilizable;
- suficientemente especifico;
- util para futuras iteraciones;
- seguro de almacenar;
- claramente conectado con el proyecto o con un tema reutilizable.

Guardar como candidata o preguntar al usuario cuando el dato sea:

- util pero aun ambiguo;
- potencialmente reutilizable pero no verificado;
- una idea externa aun no adoptada;
- una observacion que necesita contexto adicional.

No guardar automaticamente:

- secretos o credenciales;
- logs efimeros sin conclusion;
- errores sin diagnostico ni resolucion;
- informacion redundante que ya se deduce facilmente del repo y no aporta ahorro real;
- tareas de muy corto alcance que no sobreviviran a la sesion;
- opiniones sin decision ni utilidad practica.

## 6. Encaje de Fase 1 y Fase 2

### Fase 1

- El agente lee el repositorio y usa July como memoria/orquestador.
- July almacena, recupera, resume y enlaza contexto, pero no inspecciona por si solo los archivos del repo.
- La salida derivada debe vivir en la BD de July o en un archivo propio de July si hace falta.
- No se modifican automaticamente documentos del proyecto externo por defecto.

### Fase 2

- Si de verdad hace falta, July podra leer archivos del proyecto de forma controlada, read-only y no invasiva.
- El objetivo de Fase 2 es reducir friccion, no invadir el repo ni reemplazar al agente.
- Aunque July lea el proyecto de forma directa, deben mantenerse las mismas reglas:
  - no sobrescribir documentacion del proyecto externo por defecto;
  - no guardar secretos;
  - seguir dejando trazabilidad clara de lo hecho y lo pendiente.

## Primer caso real: Vocabulario

Aplicacion manual inicial acordada para validar el protocolo:

1. Tratar `Vocabulario` como proyecto conocido pero con contexto incompleto.
2. Recuperar su `project-context`.
3. Leer su documentacion efectiva del repo.
4. Abrir su primera sesion real en July.
5. Dejar una primera foto resumida del proyecto y sus siguientes pasos.

Interpretacion del caso:

- Vocabulario ya no es "proyecto nuevo" porque July ya tiene inbox, tareas y memoria sobre el repo.
- Pero todavia requiere consolidacion porque aun no tenia sesiones que dejen trazado de iteracion reutilizable.
