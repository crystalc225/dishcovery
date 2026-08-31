# Menu Decoder (VLM MVP)

Point your phone at a menu in any language → get English (or 中文/日本語) dish cards.
Tap a dish → spice level, texture, offal warning, how to eat it, cultural context.

## Architecture

```
photo ──► POST /api/menu ──► Gemini (vision) ──► tier-1 cards   (once per menu)
tap   ──► POST /api/dish ──► Gemini (text)   ──► tier-2 detail  (lazy, per dish)
```

| File                | Role |
|---------------------|------|
| `schema.py`         | Pydantic models — the data contract |
| `vlm.py`            | All Gemini calls + prompts (swap this file for the OCR version later) |
| `main.py`           | FastAPI: `/api/menu`, `/api/dish`, serves the frontend |
| `static/index.html` | Mobile web UI (camera capture, cards, detail sheet) |

## Setup

1. Free API key (no credit card): https://aistudio.google.com → "Get API key"
2. ```bash
   pip install -r requirements.txt
   export GEMINI_API_KEY=your_key_here
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
3. On your phone (same wifi as your laptop): open `http://<laptop-LAN-ip>:8000`
   - Find your LAN IP: `ipconfig getifaddr en0` (Mac) or `hostname -I` (Linux)
   - The camera works over plain http because we use `<input capture>`, not getUserMedia

## Free tier limits (gemini-2.0-flash)

~15 requests/min, ~1500/day. One menu scan = 1 request; each dish tap = 1 request.
The lazy tier-2 design exists so a 40-dish menu costs 1 call, not 40.

## Notes

- Gemini's `response_schema` enforces valid JSON — no regex/fence-stripping.
- Dishes the model doesn't recognize come back with `confidence: "unsure"` and
  render with a warning chip/banner instead of invented facts.
- Next step (resume version): replace `vlm.py` internals with
  language detection → PaddleOCR → text-only LLM. The interface stays the same.
