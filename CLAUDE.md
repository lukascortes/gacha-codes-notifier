# Gacha Codes Notifier

Bot de notificaciones automáticas de códigos de canje para juegos gacha (Hoyoverse y Wuthering Waves). Polea fuentes oficiales y community-maintained cada N minutos vía **GitHub Actions** y publica los códigos nuevos en Discord mediante **webhooks**.

No es un bot de Discord tradicional — no hay login, no hay websocket persistente, no hay servidor corriendo. Solo un script Python que se ejecuta por cron en la infraestructura gratuita de GitHub.

---

## Tech Stack

- **Lenguaje:** Python 3.11+
- **Scheduler:** GitHub Actions (cron `*/15 * * * *`)
- **HTTP:** `requests`
- **Scraping:** `beautifulsoup4` + `lxml`
- **Notificación:** Discord Webhooks (no bot)
- **Estado persistente:** `state.json` commiteado al repo por el propio workflow

---

## Filosofía de diseño

- **Sin servidor 24/7.** Toda la lógica vive en un script idempotente que GitHub ejecuta por cron.
- **No es bot.** Solo POSTs a webhooks de Discord. Sin librerías como `discord.py`.
- **Estado en el repo.** El workflow commitea `state.json` actualizado tras cada ejecución.
- **Fail-soft.** Si una fuente cae, los otros juegos siguen funcionando.
- **Una fuente de verdad por juego.** Si hay fallback, se usa solo cuando la primaria falla.
- **No spam en el primer run.** Primera ejecución inicializa `state.json` sin postear nada.

---

## Arquitectura

```
GitHub Actions cron (*/15 * * * *)
        │
        ▼
  check_codes.py (entry point)
        │
        ├─→ fetchers/hoyo.py
        │   GET https://hoyo-codes.seria.moe/codes?game=genshin
        │   GET https://hoyo-codes.seria.moe/codes?game=hkrpg
        │   GET https://hoyo-codes.seria.moe/codes?game=nap
        │
        ├─→ fetchers/wuwa.py
        │   GET https://wuthering.gg/codes (scraping HTML)
        │   (fallback) GET https://game8.co/games/Wuthering-Waves/archives/453149
        │
        ▼
  diff vs state.json
        │
        ▼
  Para cada código nuevo:
    discord_poster.post_embed(webhook_url, code, game, rewards, ...)
        │
        ▼
  Actualizar state.json y commit
```

---

## Estructura del proyecto

```
gacha-codes-notifier/
├── .github/
│   └── workflows/
│       └── check-codes.yml          # GitHub Actions cron
├── fetchers/
│   ├── __init__.py
│   ├── base.py                       # interface BaseFetcher
│   ├── hoyo.py                       # API hoyo-codes.seria.moe
│   └── wuwa.py                       # scraper Wuthering Waves
├── discord_poster.py                 # construye embeds + POST webhook
├── models.py                         # dataclasses Code, Reward
├── check_codes.py                    # entry point ejecutado por cron
├── state.json                        # códigos ya posteados (auto-actualizado)
├── requirements.txt
├── README.md
├── CLAUDE.md                         # este archivo
└── .gitignore
```

---

## Fuentes de datos

### Hoyoverse (API confiable)

API: **hoyo-codes.seria.moe** (por @seriaati)
Repo: https://github.com/seriaati/hoyo-codes

Endpoints:
- Genshin Impact: `https://hoyo-codes.seria.moe/codes?game=genshin`
- Honkai Star Rail: `https://hoyo-codes.seria.moe/codes?game=hkrpg`
- Zenless Zone Zero: `https://hoyo-codes.seria.moe/codes?game=nap`

Formato esperado (JSON):
```json
{
  "codes": [
    {
      "id": 123,
      "code": "GENSHINGIFT",
      "rewards": "50 Primogems, 5 Hero's Wit",
      "status": "OK"
    }
  ]
}
```

Solo postear códigos con `status: "OK"`.

### Wuthering Waves (scraping)

Kuro Games no provee API ni sitio de canje online — los códigos solo se canjean in-game. Por eso scrapeamos webs comunitarias.

- **Fuente primaria:** https://wuthering.gg/codes
- **Fallback:** https://game8.co/games/Wuthering-Waves/archives/453149

Estrategia:
1. Intentar `wuthering.gg` (HTML más limpio).
2. Si falla o devuelve lista vacía, caer a `game8.co`.
3. Si ambos fallan, log warning y continuar (no romper los demás juegos).

User-Agent debe simular un browser real para evitar bloqueos:
```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:120.0) "
                  "Gecko/20100101 Firefox/120.0"
}
```

---

## Modelos de datos

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Reward:
    item: str          # "Astrite", "Primogem", "Shell Credit"
    quantity: int      # 50, 10000

@dataclass
class Code:
    code: str                       # "WUTHERINGGIFT"
    game: str                       # "wuwa" | "genshin" | "hkrpg" | "nap"
    rewards: list[Reward]
    source: str                     # URL de origen
    discovered_at: str              # ISO timestamp
    expires_at: Optional[str]       # ISO timestamp si se sabe
```

---

## state.json

Formato:
```json
{
  "genshin": ["GENSHINGIFT", "OLDCODE1"],
  "hkrpg": ["STARRAIL"],
  "nap": [],
  "wuwa": ["WUTHERINGGIFT"]
}
```

Reglas:
- Solo se guardan códigos ya posteados.
- Limitar a últimos **100 códigos por juego** (FIFO) para evitar crecimiento infinito.
- Si `state.json` no existe en la primera ejecución, se crea con los códigos actuales sin postear nada.

---

## Discord embeds

Cada juego tiene color y emoji distintivos:

| Juego | Color (hex) | Emoji |
|---|---|---|
| Genshin Impact | `#4A90E2` (azul) | 🌸 |
| Honkai Star Rail | `#8B5CF6` (morado) | 🚂 |
| Zenless Zone Zero | `#EAB308` (amarillo) | ⚡ |
| Wuthering Waves | `#06B6D4` (cyan) | 🌊 |

Estructura del embed:
```python
{
  "title": "🌊 New Wuthering Waves Code!",
  "color": 0x06B6D4,
  "fields": [
    {"name": "Code", "value": "`WUTHERINGGIFT`", "inline": False},
    {"name": "Rewards",
     "value": "• 50 Astrite\n• 2 Premium Resonance Potion\n• 15000 Shell Credits",
     "inline": False},
    {"name": "How to redeem",
     "value": "Terminal → Settings → Other Settings → Redemption Code",
     "inline": False}
  ],
  "footer": {"text": "Source: wuthering.gg"},
  "timestamp": "<iso>"
}
```

Para Hoyoverse, agregar un campo "Redeem" con link directo:
- Genshin: `https://genshin.hoyoverse.com/en/gift?code=CODE`
- HSR: `https://hsr.hoyoverse.com/gift?code=CODE`
- ZZZ: `https://zenless.hoyoverse.com/redemption?code=CODE`

---

## Webhooks de Discord (secrets)

Variables de entorno requeridas (configuradas como **GitHub Secrets** en Settings → Secrets and variables → Actions):

- `DISCORD_WEBHOOK_GENSHIN`
- `DISCORD_WEBHOOK_HSR`
- `DISCORD_WEBHOOK_ZZZ`
- `DISCORD_WEBHOOK_WUWA`

Pueden apuntar al mismo canal o a canales separados. Si una variable falta, ese juego se omite silenciosamente (no es error).

Cómo crear un webhook en Discord: canal → Editar canal → Integraciones → Webhooks → Crear webhook → Copiar URL.

---

## GitHub Actions workflow

`.github/workflows/check-codes.yml`:

```yaml
name: Check Gacha Codes

on:
  schedule:
    - cron: '*/15 * * * *'   # cada 15 minutos
  workflow_dispatch:          # permite ejecución manual

permissions:
  contents: write             # necesario para commitear state.json

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python check_codes.py
        env:
          DISCORD_WEBHOOK_GENSHIN: ${{ secrets.DISCORD_WEBHOOK_GENSHIN }}
          DISCORD_WEBHOOK_HSR: ${{ secrets.DISCORD_WEBHOOK_HSR }}
          DISCORD_WEBHOOK_ZZZ: ${{ secrets.DISCORD_WEBHOOK_ZZZ }}
          DISCORD_WEBHOOK_WUWA: ${{ secrets.DISCORD_WEBHOOK_WUWA }}
      - name: Commit updated state
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add state.json
          git diff --staged --quiet || git commit -m "chore: update state [skip ci]"
          git push
```

Notas:
- `[skip ci]` en el mensaje de commit evita que el push dispare otra ejecución.
- GitHub Actions puede retrasar crons en periodos de alta carga; `*/15` es realista, `*/5` puede tener jitter de varios minutos.

---

## Convenciones de código

- **Tipado:** type hints en todo (`Code`, `Reward`, `list[Code]`, `Optional[str]`).
- **Logging:** módulo `logging` estándar, formato `[timestamp] [LEVEL] [module] message`. Nivel `INFO` por defecto.
- **Errores por fetcher:** cada fetcher captura sus excepciones internamente y retorna lista vacía si falla. NO propagar errores que rompan los demás juegos.
- **Testabilidad:** cada fetcher debe ser ejecutable standalone: `python -m fetchers.wuwa` debe imprimir los códigos encontrados sin postear a Discord.
- **Sin dependencias pesadas:** prohibido `playwright`, `selenium`, `discord.py`. Solo `requests` + `beautifulsoup4` + `lxml`.
- **Idempotencia:** ejecutar el script dos veces seguidas sin códigos nuevos no debe postear nada ni cambiar `state.json`.

---

## Plan de implementación (fases)

### Fase 1 — MVP Hoyoverse
- [ ] `requirements.txt` con `requests`, `beautifulsoup4`, `lxml`
- [ ] `models.py` con dataclasses `Code` y `Reward`
- [ ] `fetchers/base.py` con interface `BaseFetcher`
- [ ] `fetchers/hoyo.py` consumiendo la API hoyo-codes para los 3 juegos
- [ ] `discord_poster.py` con embed básico funcional
- [ ] `check_codes.py` entry point con diff vs `state.json`
- [ ] Workflow GitHub Actions
- [ ] Crear webhooks de Discord y configurar secrets
- [ ] Probar manualmente con `workflow_dispatch`

### Fase 2 — Wuthering Waves
- [ ] `fetchers/wuwa.py` scraper de `wuthering.gg/codes`
- [ ] Fallback a `game8.co`
- [ ] Parser de rewards: texto bruto ("50 Astrite, 2 Potions") → `list[Reward]`

### Fase 3 — Polish
- [ ] Colores y emojis por juego en los embeds
- [ ] Links directos de canje (Hoyoverse)
- [ ] Mention de role opcional (configurable por env var `DISCORD_PING_ROLE_ID`)
- [ ] Truncado FIFO de `state.json` a 100 por juego
- [ ] README.md con badges y screenshot

### Fase 4 — Mejoras opcionales
- [ ] Notificación de códigos próximos a expirar (cuando se conoce expiry)
- [ ] Soporte para más juegos (Infinity Nikki, etc.)
- [ ] Dashboard estático con códigos activos (vía GitHub Pages)
- [ ] Slash command `/codes` (requeriría bot real con `discord.py`, fuera de scope inicial)

---

## Setup local para desarrollo

```bash
# Clonar
git clone <repo>
cd gacha-codes-notifier

# Virtualenv
python -m venv .venv
source .venv/bin/activate

# Dependencias
pip install -r requirements.txt

# Variables de entorno (NO commitear)
export DISCORD_WEBHOOK_WUWA="https://discord.com/api/webhooks/..."
export DISCORD_WEBHOOK_GENSHIN="https://discord.com/api/webhooks/..."

# Ejecutar un solo fetcher (sin postear)
python -m fetchers.wuwa

# Ejecutar el flujo completo
python check_codes.py
```

Para forzar un post de prueba, eliminar el código de prueba de `state.json` antes de ejecutar.

---

## Anti-patrones a evitar

- ❌ NO usar `discord.py` ni bibliotecas de bots. Solo webhooks vía `requests`.
- ❌ NO usar Playwright/Selenium. `requests` + `bs4` es suficiente para estas webs.
- ❌ NO almacenar webhooks en código. Solo en secrets/env.
- ❌ NO hacer el script async/multi-thread sin necesidad. Secuencial es suficiente a esta frecuencia.
- ❌ NO crashear el script si una fuente falla. Cada fetcher es independiente.
- ❌ NO postear todos los códigos en el primer run. Primera ejecución debe inicializar `state.json` silenciosamente.
- ❌ NO commitear `.env` ni archivos con webhooks. `.gitignore` debe excluirlos.
- ❌ NO hacer scraping agresivo. 15 minutos es un intervalo respetuoso; no bajarlo sin necesidad.

---

## Referencias

- Hoyo Codes API: https://github.com/seriaati/hoyo-codes
- Hoyo Code Sender (bot público de referencia): https://github.com/chiraitori/HoYo_Code_Sender_Discord_Bot
- Wuthering Waves codes (fuente primaria): https://wuthering.gg/codes
- Discord Webhook docs: https://discord.com/developers/docs/resources/webhook
- GitHub Actions cron: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule
- Discord Embed structure: https://discord.com/developers/docs/resources/channel#embed-object
