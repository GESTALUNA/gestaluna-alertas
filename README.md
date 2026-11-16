# Gestaluna · Robot de alertas AESAN

Dos veces al día, este robot revisa las alertas alimentarias de AESAN, se queda con las que afectan al embarazo y las guarda en `alertas.json`. La app lee ese archivo cada vez que se abre.

No hace falta servidor ni ordenador encendido, y es gratis. No guarda ningún dato de pacientes.

## Qué hay en esta carpeta

| Archivo | Para qué sirve |
|---|---|
| `.github/workflows/alertas-aesan.yml` | Programa del robot: cuándo se ejecuta |
| `robot/aesan_alertas.py` | Lee AESAN, filtra y escribe `alertas.json` |
| `alertas.json` | Resultado; empieza vacío |
| `app/alertas-aesan.js` | Código que va dentro de la app y muestra las alertas |
| `app/demo.html` + `app/demo-alertas.json` | Demo con datos de ejemplo |

## Activación paso a paso (unos 15 minutos)

### 1. Crear la cuenta de GitHub
1. Entra en https://github.com/signup y crea una cuenta gratuita. Puedes usar tu correo profesional.
2. Apunta tu **nombre de usuario**. Lo necesitarás en el paso 5.

### 2. Crear el repositorio
1. Arriba a la derecha, pulsa **+** y luego **New repository**.
2. En **Repository name**, escribe `gestaluna-alertas`.
3. Marca **Public**. Debe ser público para que la app pueda leer el archivo. Solo contiene alertas públicas de AESAN.
4. Pulsa **Create repository**.

### 3. Subir los archivos
1. En el repositorio vacío, pulsa **uploading an existing file**.
2. Arrastra `alertas.json`, `README.md` y las carpetas `robot` y `app`.
3. Pulsa **Commit changes**.
4. Crea el archivo del robot a mano. La carpeta `.github` es oculta en el Mac y no se puede arrastrar:
   - Pulsa **Add file** y luego **Create new file**.
   - En el nombre, escribe exactamente `.github/workflows/alertas-aesan.yml`.
   - Copia y pega el contenido del archivo `alertas-aesan.yml` incluido aquí.
   - Pulsa **Commit changes**.

### 4. Dar permiso al robot para guardar
1. En el repositorio, ve a **Settings**, luego **Actions** y luego **General**.
2. Baja a **Workflow permissions**, marca **Read and write permissions** y pulsa **Save**.

### 5. Primera ejecución
1. Abre la pestaña **Actions**. Si te lo pide, pulsa el botón verde para activarlas.
2. Pulsa **Alertas AESAN** y luego **Run workflow**.
3. Al cabo de un minuto aparecerá un círculo verde ✅. Si pulsas en él, verás en el registro qué alertas ha marcado como `NUEVA` y cuáles ha descartado.
4. Comprueba el resultado abriendo esta dirección, sustituyendo `USUARIO` por tu nombre de usuario:
   `https://raw.githubusercontent.com/USUARIO/gestaluna-alertas/main/alertas.json`

A partir de aquí el robot funciona solo, a las 07:17 y a las 17:17 (hora de España en invierno).

### 6. Conectarlo con la app
En `app/alertas-aesan.js`, cambia `USUARIO` por tu nombre de usuario en la línea `url:`. Claude puede integrarlo en Gestaluna.

## Si algo falla
- Si un día AESAN cambia el diseño de su web y el robot no encuentra alertas, la ejecución falla y **GitHub te envía un correo**. En ese caso, el archivo de alertas no se modifica y la app sigue mostrando las últimas alertas.
- Si la página de AESAN no responde un día concreto, el robot lo vuelve a intentar en la siguiente ejecución.

## Qué alertas se muestran
Se muestran las alertas cuyo título menciona alguno de estos riesgos: Listeria, Toxoplasma, botulismo, Salmonella, E. coli, hepatitis A o norovirus, otras bacterias o contaminantes químicos (mercurio, plomo, micotoxinas…).

Se descartan las alertas que afectan solo a alérgicos, las de cuerpos extraños y las de complementos alimenticios con fármacos.

La app muestra solo el aviso de AESAN (motivo, título y fecha) y el enlace oficial, sin consejos añadidos. La lista de riesgos que se filtran está en `robot/aesan_alertas.py`, dentro de `PELIGROS`.
