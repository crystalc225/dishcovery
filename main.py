"""FastAPI app: 4 API endpoints + serves the mobile web page.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Public phone link:  ngrok http 8000
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import vlm

app = FastAPI(title="Dishcovery")

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic"}


@app.post("/api/menu")
async def scan_menu(image: UploadFile = File(...), target_lang: str = Form("English")):
    """Batch pass: menu photo -> tier-1 cards for every dish."""
    if image.content_type not in ALLOWED_MIME:
        raise HTTPException(415, f"Unsupported image type: {image.content_type}")
    data = await image.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 10 MB)")
    try:
        result = vlm.read_menu(data, image.content_type, target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")
    if not result.dishes:
        raise HTTPException(422, "No dishes found - try a clearer photo")
    return result


class DishRequest(BaseModel):
    name: str
    language: str = "unknown"
    target_lang: str = "English"


@app.post("/api/dish")
async def dish_detail(req: DishRequest):
    """Lazy pass: one dish name -> tier-2 detail."""
    try:
        return vlm.explain_dish(req.name, req.language, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class RegionRequest(BaseModel):
    region: str
    target_lang: str = "English"


@app.post("/api/region")
async def region_detail(req: RegionRequest):
    """Food culture of a region, fetched when the user taps Explore."""
    try:
        return vlm.region_info(req.region, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class CityRequest(BaseModel):
    city: str
    target_lang: str = "English"


@app.post("/api/city")
async def city_detail(req: CityRequest):
    """Must-try dish guide for a travel destination."""
    if not req.city.strip():
        raise HTTPException(422, "City name is empty")
    try:
        return vlm.city_guide(req.city.strip(), req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class StoryRequest(BaseModel):
    name: str
    canonical: str = ""
    target_lang: str = "English"


@app.post("/api/story")
async def story_detail(req: StoryRequest):
    """Deeper heritage story, fetched when the user taps Tell me more."""
    try:
        return vlm.story_deep(req.name, req.canonical or req.name, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


class DishImagesRequest(BaseModel):
    dish_name: str
    canonical: str = ""
    max_images: int = 6
    verify_urls: list = []   # when set: skip search, just verify these urls -> {"results": [bool]}


IMAGE_CACHE: dict = {}  # name -> {"images": [...], "label": str}; instant repeat views


@app.post("/api/dish_images")
async def dish_images(req: DishImagesRequest):
    """Search Wikipedia + Commons + Openverse for candidates IN PARALLEL,
    then vision-verify them in parallel. Cached per dish."""
    import asyncio, os, re
    import httpx

    name = (req.canonical or req.dish_name).strip()

    # verification mode: caller already has urls on screen, wants verdicts
    if req.verify_urls:
        from openai import AsyncOpenAI
        import asyncio as _a
        client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

        async def _check(url):
            try:
                resp = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": f'Does this image clearly show "{req.dish_name}" ({name}) as a cooked, prepared dish ready to eat? Not raw ingredients, not live animals, not people as the subject, not a different dish, not a logo/map. Answer only YES or NO.'},
                        {"type": "image_url", "image_url": {"url": url, "detail": "low"}},
                    ]}],
                    max_tokens=3,
                )
                return resp.choices[0].message.content.strip().upper().startswith("YES")
            except Exception:
                return True   # on verify error keep the image (it already passed heuristics)
        verdicts = await _a.gather(*(_check(u) for u in req.verify_urls[:8]))
        # cache the verified survivors so future views are instant AND verified
        IMAGE_CACHE[name.lower()] = {
            "images": [u for u, ok in zip(req.verify_urls, verdicts) if ok][:req.max_images],
            "label": req.dish_name, "verified": True}
        return {"results": list(verdicts)}

    if name.lower() in IMAGE_CACHE:
        return IMAGE_CACHE[name.lower()]

    FOODY = re.compile(r"(food|dish|cuisine|appetizer|dessert|soup|bread|pasta|noodle|rice|meat|seafood|fish|drink|cake|snack|sauce|stew|salad|dumpling|sandwich|pizza|burger|delicac|fried|grilled|braised|curry|tofu|pork|beef|chicken)", re.I)
    BLOCKED = re.compile(r"(restaurant chain|fast.?food chain|company|corporation|brand|franchise|footballer|singer|actor|album|film|tv series|band|club|^list of|^cuisine of|^dishes of)", re.I)
    JUNK = re.compile(r"(flag|map|logo|icon|coat|seal|montage|locator|banner|symbol|wordmark|emblem|\.svg)", re.I)

    label = name

    async def wiki_candidates(hx) -> list[str]:
        nonlocal label
        out = []
        try:
            art = None
            for q in (name, name + " dish"):
                r = await hx.get("https://en.wikipedia.org/w/api.php", params={
                    "action": "query", "generator": "search", "gsrsearch": q, "gsrlimit": 5,
                    "prop": "pageimages|description", "piprop": "thumbnail", "pithumbsize": 900,
                    "format": "json"})
                pages = sorted((r.json().get("query", {}).get("pages", {}) or {}).values(),
                               key=lambda p: p.get("index", 99))
                for p in pages:
                    meta = (p.get("description") or "") + " " + p.get("title", "")
                    if FOODY.search(meta) and not BLOCKED.search(meta):
                        art = p
                        break
                if art:
                    break
            if not art:
                return out
            label = art["title"]
            thumb = (art.get("thumbnail") or {}).get("source")
            if thumb and not JUNK.search(thumb):
                out.append(thumb)
            r2 = await hx.get("https://en.wikipedia.org/w/api.php", params={
                "action": "query", "pageids": art["pageid"], "prop": "images",
                "imlimit": 20, "format": "json"})
            page = list((r2.json().get("query", {}).get("pages", {}) or {}).values())
            files = [f["title"] for f in (page[0].get("images", []) if page else [])
                     if re.search(r"\.(jpe?g|png)$", f["title"], re.I) and not JUNK.search(f["title"])][:8]
            if files:
                r3 = await hx.get("https://en.wikipedia.org/w/api.php", params={
                    "action": "query", "titles": "|".join(files), "prop": "imageinfo",
                    "iiprop": "url", "iiurlwidth": 900, "format": "json"})
                for p in (r3.json().get("query", {}).get("pages", {}) or {}).values():
                    u = (p.get("imageinfo") or [{}])[0].get("thumburl")
                    if u:
                        out.append(u)
        except Exception:
            pass
        return out

    async def commons_candidates(hx) -> list[str]:
        out = []
        try:
            r = await hx.get("https://commons.wikimedia.org/w/api.php", params={
                "action": "query", "generator": "search", "gsrnamespace": 6,
                "gsrsearch": name, "gsrlimit": 8, "prop": "imageinfo",
                "iiprop": "url", "iiurlwidth": 900, "format": "json"})
            for p in sorted((r.json().get("query", {}).get("pages", {}) or {}).values(),
                            key=lambda p: p.get("index", 99)):
                t = p.get("title", "")
                if re.search(r"\.(jpe?g|png)$", t, re.I) and not JUNK.search(t):
                    u = (p.get("imageinfo") or [{}])[0].get("thumburl")
                    if u:
                        out.append(u)
        except Exception:
            pass
        return out

    async def openverse_candidates(hx) -> list[str]:
        """Openverse aggregates CC-licensed photos (Flickr etc.) - far more
        appetizing food photography than encyclopedic Wikipedia shots."""
        out = []
        try:
            r = await hx.get("https://api.openverse.org/v1/images/", params={
                "q": name + " food", "page_size": 8})
            for item in r.json().get("results", []):
                u = item.get("thumbnail") or item.get("url")
                if u:
                    out.append(u)
        except Exception:
            pass
        return out

    async with httpx.AsyncClient(timeout=8) as hx:
        wiki, commons, openverse = await asyncio.gather(
            wiki_candidates(hx), commons_candidates(hx), openverse_candidates(hx))

    # interleave sources so verification budget samples all of them
    candidates, seen = [], set()
    for group in (openverse, wiki, commons):   # openverse first: best-looking photos
        for u in group:
            if u not in seen:
                seen.add(u)
                candidates.append(u)
    candidates = candidates[:8]
    result = {"images": candidates[:req.max_images], "label": label, "verified": False}
    # NOTE: not cached here - the follow-up verify call caches the verified set
    return result


class CardThumbsRequest(BaseModel):
    dishes: list  # [{"name": display name, "query": image_query}]


THUMB_CACHE: dict = {}


@app.post("/api/card_thumbs")
async def card_thumbs(req: CardThumbsRequest):
    """One AI-verified thumbnail per dish, all dishes checked in parallel.
    Per dish: 1 quick Wikipedia article search -> 1 cheap vision check on the
    lead image. Obscure dishes (no food article) return null with no vision cost,
    so the card keeps its emoji. Cached per query for instant repeats."""
    import asyncio, os, re
    import httpx
    from openai import AsyncOpenAI

    FOODY = re.compile(r"(food|dish|cuisine|appetizer|dessert|soup|bread|pasta|noodle|rice|meat|seafood|fish|drink|cake|snack|sauce|stew|salad|dumpling|sandwich|pizza|burger|delicac|fried|grilled|braised|curry|tofu|pork|beef|chicken)", re.I)
    BLOCKED = re.compile(r"(restaurant chain|fast.?food chain|company|corporation|brand|franchise|footballer|singer|actor|album|film|tv series|band|club|^list of|^cuisine of|^dishes of)", re.I)
    JUNK = re.compile(r"(flag|map|logo|icon|coat|seal|montage|locator|banner|symbol|wordmark|emblem|\.svg)", re.I)

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])

    async def one(hx, d):
        name = (d.get("name") or "").strip()
        query = (d.get("query") or name).strip()
        key = query.lower()
        if key in THUMB_CACHE:
            return THUMB_CACHE[key]
        url = None
        try:
            r = await asyncio.wait_for(hx.get("https://en.wikipedia.org/w/api.php", params={
                "action": "query", "generator": "search", "gsrsearch": query, "gsrlimit": 3,
                "prop": "pageimages|description", "piprop": "thumbnail", "pithumbsize": 320,
                "format": "json"}), timeout=3.0)
            pages = sorted((r.json().get("query", {}).get("pages", {}) or {}).values(),
                           key=lambda p: p.get("index", 99))
            for p in pages:
                meta = (p.get("description") or "") + " " + p.get("title", "")
                t = (p.get("thumbnail") or {}).get("source")
                if t and FOODY.search(meta) and not BLOCKED.search(meta) and not JUNK.search(t):
                    url = t
                    break
        except Exception:
            pass
        if not url:
            THUMB_CACHE[key] = None
            return None
        try:
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": f'Does this image show "{name}" (or {query}) as prepared food? Not a person, animal, logo, storefront, map, or unrelated dish. Answer only YES or NO.'},
                    {"type": "image_url", "image_url": {"url": url, "detail": "low"}},
                ]}],
                max_tokens=3,
            )
            ok = resp.choices[0].message.content.strip().upper().startswith("YES")
        except Exception:
            ok = False
        result = url if ok else None
        THUMB_CACHE[key] = result
        return result

    async with httpx.AsyncClient(timeout=4) as hx:
        thumbs = await asyncio.gather(*(one(hx, d) for d in req.dishes[:30]))
    return {"thumbs": list(thumbs)}


class IngredientRequest(BaseModel):
    name: str
    target_lang: str = "English"


@app.post("/api/ingredient")
async def ingredient_detail(req: IngredientRequest):
    """Quick ingredient primer, fetched when a chip is tapped."""
    try:
        return vlm.ingredient_info(req.name, req.target_lang)
    except Exception as e:
        raise HTTPException(502, f"Model error: {e}")


app.mount("/", StaticFiles(directory="static", html=True), name="static")
