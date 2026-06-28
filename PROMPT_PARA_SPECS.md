# Prompt reutilizable para generar el SPECS.md de cualquier proyecto

> Copia todo lo de abajo y pégamelo (ajustando los datos entre corchetes) en
> cualquier sesión futura, cuando ya hayamos construido —o estemos construyendo—
> un aplicativo. Genero un `SPECS.md` con el mismo estándar que el de Money Chwats.

---

Genérame un archivo **`SPECS.md`** que documente este proyecto. Sigue EXACTAMENTE
estas reglas y estructura.

**Datos del proyecto (lléname esto):**
- Nombre del aplicativo: [nombre]
- Qué hace en una frase: [propósito]
- Equipo/hardware destino: [ej. PC de 4 GB sin GPU / Mac M1 8 GB / servidor]
- Presupuesto: [ej. solo gratis/local / máximo un VPS de $5 / hay presupuesto nube]
- ¿Maneja datos personales o sensibles?: [sí/no, cuáles]

**Estilo de escritura (obligatorio):**
- Lenguaje **sencillo y no técnico**: que lo entienda alguien que no programa.
- **Conciso**: nada de relleno. Tablas y viñetas antes que párrafos largos.
- A cada componente y a cada requisito, dile **para qué sirve** en una línea.
- En español, con la moneda/idioma del proyecto.

**Estructura que debe tener el SPECS.md:**

1. **En una frase** — qué hace la app, de punta a punta.
2. **Las piezas (servicios)** — lista cada microservicio con un **apodo claro**
   (ej. "el fotógrafo", "el coordinador", "los ojos"). Por cada uno: qué hace,
   qué tecnología usa, cuánta RAM/recursos necesita, y si requiere internet.
3. **Qué necesita el computador** — tabla de requisitos mínimos por escenario
   (todo local / con nube / IA local), aclarando qué corre dónde.
4. **Flujo del proceso (base para BPMN)** — pensado para dibujar un BPMN después:
   lista los **participantes (carriles)**, los **pasos numerados**, los **puntos
   de decisión** (compuertas) y los **eventos de error** posibles.
5. **Estado actual** — qué funciona ya (✅) y qué falta (🔜).
6. **Fricciones, límites y aprendizajes** — la parte más valiosa. Revisa TODO lo
   que nos costó avanzar y agrúpalo en tablas (fricción → qué pasó → aprendizaje),
   cubriendo como mínimo estas dimensiones:
   - **Hardware/capacidad** (RAM, GPU, swap, equipos antiguos, topes físicos).
   - **Tecnologías de IA/OCR/modelos** (requisitos de GPU, compatibilidad,
     instalaciones difíciles, modelos demasiado pesados).
   - **Costos** (presupuesto limitado, costo por uso de la nube, qué NO sirve).
   - **Privacidad/nube** (datos que salen del equipo, blindaje, opt-in, planes
     gratis que registran datos).
   - **Calidad de datos** (errores de lectura, límites de las reglas vs IA).
   - **Proceso/desarrollo** (permisos antes de operaciones pesadas, sobre-
     ingeniería, límites del entorno, expectativas app-vs-IA).
   Cierra con un **checklist accionable** para prever estas objeciones en futuros
   proyectos similares.
7. **Para replicar el proyecto desde cero** — 10 puntos. Cada punto tiene:
   (a) el título + una línea de **para qué sirve**, y
   (b) un bloque **"Lo que usamos"** que funcione como **plano de construcción**:
   detallado y reproducible, pero en lenguaje llano. Debe incluir, como mínimo:
   1. Herramientas y versiones exactas (y para qué sirve cada una).
   2. Mapa de carpetas y archivos (qué hace cada uno).
   3. **Definición exacta de las tablas/datos** (columnas, estados posibles, y la
      fórmula del ID que conecta las tablas). *Marca esto como lo más importante.*
   4. Las "órdenes"/conexiones entre piezas (qué recibe y devuelve cada una).
   5. **El texto exacto que se le da a la IA** (las instrucciones/prompts).
   6. Los pasos de las partes "inteligentes" (con los números/parámetros reales).
   7. La hoja de configuración (qué se ajusta sin tocar código).
   8. Instalación y arranque (paso a paso).
   9. Las reglas que no se deben romper (seguridad, privacidad, no-objetivos).
   10. Cómo saber que quedó bien (criterios de aceptación medibles).

**Principios que SIEMPRE debes reflejar (lecciones de Money Chwats):**
- Antes de proponer IA/OCR local, **verifica que el hardware destino lo aguante**
  (RAM real, GPU). Si no, propón nube con blindaje, o un modelo liviano.
- Si hay datos personales, **diseña blindaje + nube opt-in desde el día 1**.
- **Confirma el presupuesto** antes de proponer algo de pago.
- **Empieza simple**, sin fricción para el usuario.
- **Distingue claramente** lo que hace la app por sí sola de lo que hace la IA.
- Sé honesto sobre límites y costos; no prometas más de lo que el equipo puede.

Cuando termines, dime qué le faltaría a este `SPECS.md` para que otra persona
(u otra sesión) reproduzca el proyecto al 100%.
