# 🚀 Guía de Despliegue en Vercel (Para usar en el Celular)

Esta aplicación te permite usar tu **celular** para:
1. 📸 **Tomarle una foto a la pantalla de la CC358**.
2. 🤖 La Inteligencia Artificial lee los 8 números de monedas automáticamente.
3. 💵 Agregar los billetes manualmente.
4. 💾 **Guardar directo en tu Google Sheet** desde cualquier lugar.

---

## Paso 1: Importar en Vercel

1. Entra a [vercel.com](https://vercel.com) e inicia sesión con tu cuenta de GitHub (`fundamiga`).
2. Haz clic en **"Add New..."** ➔ **"Project"**.
3. En la lista de repositorios, busca **`monedasconteo`** y haz clic en **"Import"**.

---

## Paso 2: Configurar las Variables de Entorno en Vercel

Antes de darle "Deploy", abre la sección **"Environment Variables"** y agrega estas 2 variables:

### Variable 1: Credenciales de Google Sheets
* **Key (Nombre):** `GOOGLE_SERVICE_ACCOUNT_KEY`
* **Value (Valor):** Abre tu archivo `config/credentials.json` en tu computador, copia **todo el texto** y pégalo aquí.

### Variable 2: Clave de Google Gemini (Para leer la foto con IA)
* **Key (Nombre):** `GEMINI_API_KEY`
* **Value (Valor):** Tu clave gratuita de Google AI Studio. Si aún no la tienes, se saca en 1 clic gratis en [aistudio.google.com](https://aistudio.google.com/). *(También puedes escribirla directamente en los ajustes dentro de la app en el celular).*

---

## Paso 3: Desplegar

1. Haz clic en el botón azul **"Deploy"**.
2. Espera 1 minuto a que termine.
3. ¡Listo! Vercel te dará un link público (ejemplo: `https://monedasconteo.vercel.app`).

---

## Paso 4: Abrir en tu Celular

1. Abre ese link en el navegador de tu celular (Chrome o Safari).
2. *(Opcional)* En el menú de tu navegador del celular, dale **"Agregar a la pantalla principal"** para que te quede como una app instalada con su propio icono.
3. ¡Toca **"Tomar Foto a la Pantalla"**, apunta a la pantalla azul de la CC358, y listo! 📱🎉
