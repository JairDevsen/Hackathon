import { useCallback, useEffect, useState } from 'react'

export type Theme = 'dark' | 'light'
const KEY = 'citadel_theme'
const read = (): Theme => { try { return localStorage.getItem(KEY) === 'light' ? 'light' : 'dark' } catch { return 'dark' } }
const apply = (t: Theme) => { document.documentElement.dataset.theme = t }

/** Tema do app (padrão escuro). A preferência fica só neste navegador. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(read)
  useEffect(() => apply(theme), [theme])
  const toggle = useCallback(() => setTheme((t) => { const n = t === 'dark' ? 'light' : 'dark'; try { localStorage.setItem(KEY, n) } catch { /* sem armazenamento */ } return n }), [])
  return { theme, toggle }
}

/** A landing e o login são sempre escuros: força o tema enquanto montados e devolve a preferência ao sair. */
export function useForceDark() {
  useEffect(() => { apply('dark'); return () => apply(read()) }, [])
}
