# 🔑 Guía para Activar Google Sheets API (una sola vez)

Esta guía te permite que el programa pueda leer y escribir en tu Google Sheet automáticamente.
Solo tienes que hacerlo **una vez**. Después funciona solo.

---

## Paso 1: Ir a Google Cloud Console

1. Abre este link: **https://console.cloud.google.com/**
2. Inicia sesión con tu cuenta de Google (la misma del Drive donde está el Sheet).

---

## Paso 2: Crear un Proyecto

1. Haz clic en el menú desplegable de proyectos (arriba a la izquierda).
2. Haz clic en **"Nuevo Proyecto"**.
3. Escribe un nombre: `recaudo-cc358` → haz clic en **Crear**.
4. Espera unos segundos y selecciona el proyecto recién creado.

---

## Paso 3: Activar las APIs necesarias

1. En el menú de la izquierda ve a **"APIs y Servicios" → "Biblioteca"**.
2. Busca **"Google Sheets API"** → haz clic → **Habilitar**.
3. Vuelve a la biblioteca, busca **"Google Drive API"** → haz clic → **Habilitar**.

---

## Paso 4: Crear las Credenciales OAuth

1. Ve a **"APIs y Servicios" → "Credenciales"**.
2. Haz clic en **"+ Crear credenciales" → "ID de cliente de OAuth"**.
3. Si te pide configurar la "Pantalla de consentimiento":
   - Selecciona **"Externo"** → **Crear**.
   - En "Nombre de la aplicación" escribe: `Recaudo CC358`.
   - En "Correo de asistencia" pon tu correo → **Guardar y continuar**.
   - En las siguientes pantallas haz clic en **Continuar** hasta terminar.
4. Ahora sí crea el ID de cliente:
   - Tipo de aplicación: **"Aplicación de escritorio"**.
   - Nombre: `recaudo-cc358`.
   - Haz clic en **Crear**.

---

## Paso 5: Descargar el archivo de credenciales

1. Aparecerá un cuadro con tus credenciales → haz clic en **"Descargar JSON"**.
2. Se descarga un archivo con nombre largo como `client_secret_xxx.json`.
3. **Renómbralo exactamente a:** `credentials.json`
4. **Muévelo a la carpeta:** `c:\Users\kevin17\Documents\planmaquinamonedas\config\`

---

## Paso 6: Ejecutar el programa por primera vez

1. Abre la terminal y ejecuta:
   ```
   python app_gui.py
   ```
2. La primera vez que hagas clic en **"Guardar en Google Sheets"**, se abrirá el navegador.
3. Inicia sesión con tu cuenta Google → haz clic en **"Permitir"**.
4. Listo. El programa guarda un `token.pickle` para no pedirte login de nuevo.

---

## ✅ Después de esto

El programa funcionará automáticamente sin necesidad de volver a autenticarse.

> [!NOTE]
> Si en algún momento el programa dice "Error de autenticación", borra el archivo
> `config/token.pickle` y vuelve a ejecutar. Te pedirá el login una vez más.
