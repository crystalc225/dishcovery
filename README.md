# Dishcovery

Point your phone at a menu in any language and it tells you what each dish actually is. Not a word for word translation, but what it tastes like, how it's eaten, whether it's spicy or has offal in it, and where it's from. There's also an Explore tab where you type in a city and get its must try dishes and local eating customs.

I made this because menu translation apps give you nonsense for food. "螞蟻上樹" literally translates to "ants climbing a tree" but it's actually glass noodles with minced pork. A dictionary can't know that but a language model can.

## Why I built it

I travel a lot and I'll eat pretty much anything, and not being able to read a menu is genuinely stressful, especially when the literal translation is more confusing than just not knowing. I wanted something that explains a dish the way a local friend would. It ended up being a really fun project because a lot of the hard parts weren't what I expected. Getting the AI to be reliable and getting the images to actually match the dish took way more work than the translation itself.

## How it works

The main flow is split into two steps so it stays fast and cheap:

1. **Scan the menu** and the photo goes to a vision language model that reads it in any language and returns each dish with a name, a quick "what it actually is" line, and a category. This is one API call for the whole menu.
2. **Tap a dish** and only then does it load the detailed stuff (spice level, texture, the history, where it's from, ingredients). Loading this only when you tap means a 40 dish menu is one API call instead of forty.

Some of the harder problems I ran into:

- **Dish names don't translate literally.** So the prompt is written to interpret what the dish actually is instead of translating the words, and to say when it's not sure instead of making something up that sounds convincing.
- **Getting the right images.** This was the biggest headache. Basic image search gives you garbage. Searching "Bruschetta" gave me a photo of a person named Bruschetta, and menu names like "American Dream Burger" pulled up the Burger King logo. What I ended up doing is having the model turn each dish into a generic searchable name first, searching a few free image sources at once, then running each image through a vision check that asks "does this actually show this dish as prepared food" before showing it. Images show up right away and the wrong ones get removed in the background, and results are cached so opening the same dish again is instant. If nothing passes the check it just shows an emoji instead of a wrong photo, because I'd rather show no image than a misleading one.
- **Not making up restaurants.** The Explore feature suggests dishes and types of places to find them (night markets, breakfast shops) but never specific restaurant names, because the model will confidently invent restaurants that don't exist. Instead each dish links to a real Google Maps search so the actual reviews and prices come from somewhere trustworthy.

## Tech stack

- **Backend:** Python, FastAPI, Pydantic for validating the data shapes
- **AI:** OpenAI GPT-4o-mini (handles both vision and text)
- **Frontend:** plain HTML/CSS/JS in a single file, no framework, built mobile first
- **Free APIs:** Wikipedia + Wikimedia Commons + Openverse for images, Google Maps for maps, BigDataCloud for turning coordinates into a city name

I skipped a frontend framework on purpose since it's just one page and I wanted it to load fast on a phone over restaurant wifi.

## Changes I made throughout building

This didn't come out clean on the first try. Rough order of what I built, broke, and changed:

- Started on Google Gemini, then hit regional free tier limits in Taiwan (quota was literally set to 0), so I migrated the whole model layer to OpenAI. Only one file changed because I'd kept all the model calls in `vlm.py`.
- First image attempt searched Wikimedia Commons by raw dish name. Got faces of people who happened to share the name, brand logos, and completely unrelated dishes.
- Tried filtering by Wikipedia article descriptions (keep it only if the description says "food", "dish", etc). Better, but "list of noodle dishes" style pages slipped through and returned random noodle photos.
- Tried scoring image filenames (prefer "grilled_milkfish.jpg" over "Chanos_chanos.jpg"). Still just guessing from text, so it kept being wrong in context.
- Finally moved to actually looking at the images: send each candidate to the vision model and ask if it shows the dish as prepared food. This is the only thing that reliably worked.
- That was accurate but slow (sequential verification blocked the whole UI for ~6s). Reworked it to render images immediately and verify in the background, dropping rejected ones after, plus a cache so repeat views are instant.
- Card thumbnails: tried per dish thumbnails too, but for obscure dishes there's just no correct image in free sources, so I dropped them in favor of a category emoji. Decided a clean emoji beats a wrong photo.
- UI went through a few directions (a dark "night market" theme first, which was hard to read) before landing on the warm paper / editorial look. Also had to cap the detail sheet width once I tested on a laptop, it was stretching edge to edge.
- Maps started on OpenStreetMap embeds, switched to Google Maps embeds so the labels could follow the selected language.

The throughline for a lot of these: with free data, the honest move is often to show less. Verify what you can, and fall back to nothing rather than guessing.

## Running it locally

You need Python 3.10+ and an OpenAI API key (you can get one from the OpenAI website).

```bash
git clone https://github.com/YOUR_USERNAME/dishcovery.git
cd dishcovery

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# put your API key in a .env file
echo "OPENAI_API_KEY=your-key-here" > .env

uvicorn main:app --reload --port 8000
```

Then open `http://localhost:8000`. To try it on your phone, run `ngrok http 8000` in another terminal and open the https link it gives you (the camera and location stuff needs https to work).

## Project structure

```
dishcovery/
├── main.py            # FastAPI routes + the image checking pipeline
├── vlm.py             # all the OpenAI calls and prompts
├── schema.py          # Pydantic models (the data shapes)
├── static/
│   └── index.html     # the whole frontend
└── requirements.txt
```

I kept all the model calls in `vlm.py` on purpose. The app actually started on Google Gemini and I switched to OpenAI later, and because everything AI related was in one file that switch only touched one file.

## Stuff I'd add next

- Use a proper food image API instead of the free sources, which don't have great coverage for more regional dishes
- Let you tap the actual dish on the menu photo instead of matching by number
- Cache dishes across users so popular ones load instantly and cost less

## Note

The dish suggestions and prices are AI generated so treat them as a starting point. Always double check specific restaurants and prices on a maps app before going.
