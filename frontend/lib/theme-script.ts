/**
 * Skrip inline untuk <head> (layout.tsx, server component): memasang tema
 * tersimpan sebelum halaman dilukis agar tidak berkedip. Bawaan terang.
 * Dipisah dari lib/theme.ts karena modul itu memakai hook (khusus klien).
 */
export const THEME_KEY = "theme";

export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="dark")document.documentElement.dataset.theme="dark";}catch(e){}`;
