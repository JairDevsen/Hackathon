# Design system "cristal" · paleta Citadel IA

> **Atualização:** o app passou a ser **escuro por padrão** (como nas telas de referência), com alternância para o tema claro (ícone sol/lua no topo; preferência só neste navegador), e a navegação é um **menu lateral com rótulos** (não mais a barra de pílula só com ícones). Landing e login são sempre escuros. Os tokens abaixo descrevem o tema claro; `[data-theme='dark']` em `theme.css` inverte os mesmos tokens (as classes dos componentes não mudam) e acrescenta `surface`, `surface-2` e as variáveis de vidro (`--glass-*`, `--field-bg`, `--modal-bg`, `--sidebar-bg`).

Fonte: seção 9 do prompt de migração (o guia `layout-menu-cristal` original **não estava no repositório**; as medidas abaixo seguem a seção 9 e o comportamento descrito no prompt). Implementação: [`frontend/src/styles/theme.css`](frontend/src/styles/theme.css) (tokens em `@theme` + utilitários `@utility`) e [`frontend/src/components/`](frontend/src/components/).

## Tokens
| Token | Hex | Uso | Contraste |
|---|---|---|---|
| `brand-50` / `brand-lighter` | `#f7f3fd` / `#ede4fb` | hover / item ativo, trilhas | – |
| `brand-light` | `#c8aef0` | bordas em hover/foco, scrollbar | 9,7:1 sobre `night` |
| `brand-default` | `#8a52d4` | ícone, borda, gradiente, texto ≥ 24 px | 4,9:1 sobre branco (**só texto grande**) |
| `brand` | `#6020b8` | botões, links, ícone ativo | 8,8:1 ✔ |
| `brand-dark` / `brand-darker` | `#4b1a96` / `#2e1463` | hover, títulos, texto ativo | 11,1:1 / 15:1 |
| `night` | `#140b28` | hero, rodapé, login | – |
| `canvas` `border` `muted` `foreground` `muted-foreground` | `#f7f5fb` `#e6e1f0` `#f2eff8` `#1f1a2e` `#6b6383` | fundo, bordas, texto | 16,9:1 / 5,6:1 ✔ |
| `success` `warning` `danger` (+`-bg`) | `#16a34a` `#b45309` `#dc2626` | **só** status | – |

Sombras sempre tingidas de índigo (`rgba(36,19,66,…)`), nunca cinza. Gradiente da marca `135deg #8a52d4 → #6020b8 55% → #2e1463` (CTA, avatar). Tipografia: Inter (corpo), Playfair Display (títulos de página, `font-display`).

## Regras obrigatórias
- O shell é `h-dvh overflow-hidden`; **só a superfície rola**.
- **Nunca** `backdrop-filter`, `transform` ou `filter` na superfície ou em contêineres que envolvem modais `fixed` (`glass-surface` não usa blur; o `Modal` usa portal).
- ~~Item inativo da barra só com ícone~~ **Substituído:** o menu lateral mostra ícone + rótulo em todos os itens (a versão só com ícones era difícil de entender); grupos abrem como sanfona; no celular o menu vira gaveta.
- Navegação é dado (`NavEntry[]`) **filtrado por perfil e permissão antes** do `AppShell`; grupo com 1 filho vira link, grupo vazio some (`components/shell/nav.ts`, testado).
- Um dropdown por vez; fecha ao clicar fora, `Esc` e ao mudar de rota (ajuste de estado no render).
- Breakpoints: 900 (menu lateral vira gaveta; submenu do dossiê vira faixa de chips).
- Texto em `brand` ou mais escuro; `brand-default` só em ícone/borda/gradiente. Badge vermelho só para contagem; vermelho só em ação destrutiva.
- `prefers-reduced-motion` desliga animações (hero, órbita, shimmer).

## Utilitários de vidro
`glass-bar` (pílula, blur 18) · `glass-surface` (sem blur, raio 1.75rem) · `glass-panel` (blur 14) · `glass-dropdown` (animação `pop`) · `nav-track` `nav-btn` `nav-btn-active` `icon-circle` `badge-count` `segmented` `segmented-tab(-active)` `side-item(-active)` (barra de 3 px) `btn-primary-gradient` `field-cristal` `skeleton`.

## Componentes
| Componente | Variantes / props | Estados | Acessibilidade |
|---|---|---|---|
| `Button` | `primary` (gradiente) · `soft` · `ghost` · `danger`; `size` sm/md; `loading` | default, hover, focus (anel 3 px), disabled, loading (spinner) | `<button>` nativo; foco visível |
| `Field` + `Input/Select/Textarea` | label, `error`, `hint` | default, focus, `aria-invalid` | `label for`; erro com `role="alert"` |
| `Modal` | `eyebrow`, `title` (Playfair), `footer`, `wide` | aberto/fechado | `role="dialog" aria-modal`, nome acessível, `Esc`, foco restaurado, portal |
| `Segmented` | `options`, `value` | ativo/inativo | `role="tablist"`/`tab`, `aria-selected` |
| `StatusPill` | OK · A_VENCER · PENDENTE · VENCIDO · DISPENSADO … (tabela 9.4) | – | texto + cor (nunca só cor) |
| `KpiCard` | `label`, `value`, `hint`, `tone`, `to` | link/estático | rótulo textual |
| `ComplianceRing` | `pct`, `size` | verde ≥ 90 · violeta ≥ 70 · vermelho | `role="img"` + `aria-label` "Conformidade N%" |
| `DataTable` | `cols[]`, `rows`, `onRow`, `empty`, `loading` | carregando (skeleton), vazio, erro (`ErrorState`) | `<th scope>`, linhas clicáveis com `Enter` |
| `EmptyState` `ErrorState` `Skeleton` | – | – | `role="alert"`/`status` |
| `AppShell` · `SectionLayout` · `SectionHeading` | `nav`, `groups`, `back`, `action` | – | `nav aria-label`, "pular para o conteúdo" |
| `DocumentViewer` | páginas, `highlights` (caixas do OCR) | zoom 50–300 %, girar, navegar | botões com `aria-label`, `alt` por página |
| Gráficos (Recharts) | escala `brand-lighter → brand-darker`; semânticas só para status | tooltip `glass-dropdown` | contêiner `role="img"` com descrição |

## Landing
Pública em `/` (chunk próprio, sem Recharts). Hero sobre `night` com órbita SVG lenta e lote que se organiza em pastas (páginas fictícias do gerador, marca "AMOSTRA"). Conteúdo sem números inventados: onde falta prova há o marcador `[[métrica do piloto]]`; preço "sob consulta".
