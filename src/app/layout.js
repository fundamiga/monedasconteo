import "./globals.css";

export const metadata = {
  title: "Recaudo CC358 — Control Móvil",
  description: "Sistema móvil de captura de monedas CC358 con cámara y guardado en Google Sheets"
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased selection:bg-blue-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}
