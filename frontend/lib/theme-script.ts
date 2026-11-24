/** Skrip inline untuk <head>. */
export const THEME_KEY = "theme";

export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="dark")document.documentElement.dataset.theme="dark";}catch(e){}`;
