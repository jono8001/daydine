"""Menu & Dish Intelligence section builder.

Extracts dish mentions from review text, maps venue to a national
category trend set, and surfaces gaps between what guests praise
and what's visible in the venue's public listing.
"""

import re
from collections import defaultdict

# ---------------------------------------------------------------------------
# Dish extraction patterns and word lists
# ---------------------------------------------------------------------------

FOOD_CONTEXT_PATTERNS = [
    r'(?:had|ordered|tried|ate|tasted|enjoyed|loved|hated|recommend(?:ed)?)\s+the\s+([\w\s]{2,30}?)(?:\s+which|\s+was|\s+were|[,.]|$)',
    r'the\s+([\w\s]{2,25}?)\s+(?:was|were|is)\s+(?:amazing|excellent|delicious|lovely|great|disappointing|awful|cold|overcooked|undercooked|perfect|outstanding)',
    r'([\w\s]{2,20}?)\s+(?:dish|course|plate|starter|main|dessert|pudding)',
]

POSITIVE_WORDS = {
    'amazing', 'excellent', 'delicious', 'lovely', 'great', 'outstanding',
    'perfect', 'superb', 'fantastic', 'wonderful', 'enjoyed', 'loved',
    'recommend',
}
NEGATIVE_WORDS = {
    'disappointing', 'awful', 'cold', 'overcooked', 'undercooked',
    'terrible', 'poor', 'bland', 'tasteless', 'dry', 'bad', 'mediocre',
}
STOP_WORDS = {
    'the', 'a', 'an', 'this', 'that', 'my', 'our', 'their', 'your',
    'his', 'her', 'its', 'we', 'they', 'i', 'it', 'is', 'was', 'were',
    'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
    'will', 'would', 'could', 'should', 'can', 'may', 'might',
    'not', 'no', 'but', 'and', 'or', 'so', 'if', 'then', 'there',
    'here', 'very', 'really', 'just', 'also', 'too', 'only',
    'some', 'any', 'all', 'each', 'every', 'both', 'few', 'more',
    'most', 'other', 'what', 'which', 'who', 'whom', 'how', 'when',
    'where', 'why', 'much', 'many', 'well', 'good', 'nice', 'food',
    'meal', 'place', 'restaurant', 'cafe', 'pub', 'bar', 'menu',
    'table', 'staff', 'time', 'day', 'night', 'evening', 'lunch',
    'dinner', 'breakfast', 'brunch', 'service', 'experience',
}


# ---------------------------------------------------------------------------
# National category trends (UK, 2026)
# ---------------------------------------------------------------------------

CATEGORY_TRENDS_2026 = {
    "wine_bar": [
        "Natural wine lists are a strong differentiator — growing fast in UK wine bar reviews",
        "Small plates and sharing formats outperforming traditional starters in wine-led venues",
        "Non-alcoholic premium options: a growing proportion of guests actively look for them",
        "Dog-friendly seating is a recurring positive mention in UK wine bar reviews",
    ],
    "pub_dining": [
        "Sunday roast premium positioning: venues at \u00a322+ outperforming \u00a314-16 tier on review sentiment",
        "Smash burgers growing strongly on UK pub menus",
        "Whole-vegetable plant-based dishes outperforming meat alternatives in pub settings",
        "Pre-theatre and early-bird set menus showing strong conversion in town-centre pubs",
    ],
    "pizzeria": [
        "Sourdough and long-ferment bases commanding a premium with strong positive review sentiment",
        "Burrata as a starter: one of the fastest-growing items on UK pizza menus",
        "Natural wine pairings listed alongside pizza driving strong differentiation",
    ],
    "casual_dining": [
        "Quality-led menus outperforming novelty: guests reward consistency and ingredient quality",
        "Customisation growing: guided personalisation (hero base + controlled swaps) preferred over unlimited choice",
        "Experiential elements (limited-time menus, collaborations) increasingly drive visit decisions among under-40s",
        "72% of UK diners say they will pay more for fresh and seasonal produce",
    ],
    "cafe": [
        "Specialty coffee knowledge is a positive review driver — guests notice and mention it",
        "Brunch menus with dietary flexibility (vegan, GF options clearly labelled) reduce decision friction",
        "Dog-friendly outdoor seating is among the most commonly praised attributes in UK cafe reviews",
    ],
    "default": [
        "Value perception is multi-dimensional in 2026: freshness, quality and provenance now outweigh headline price",
        "72% of UK diners say they will pay more for freshness and seasonal produce",
        "Experiential dining growing: events, pop-ups and limited-time menus increasingly drive visit decisions",
        "Response to reviews is now a decision factor: 89% of diners read owner responses before booking",
    ],
}


# ---------------------------------------------------------------------------
# Dish extraction
# ---------------------------------------------------------------------------

def _normalise_dish(raw):
    """Clean and normalise a dish mention string."""
    dish = raw.strip().lower()
    # Remove leading articles
    # Remove leading articles and connectors (longest match first)
    dish = re.sub(r'^(and the|and an|and a|the|an|a|my|our|their|and|with|some|two|three|four)\s+', '', dish)
    # Second pass in case of chained articles ("and a sticky" → "a sticky" → "sticky")
    dish = re.sub(r'^(the|an|a)\s+', '', dish)
    # Remove trailing whitespace/punctuation
    dish = dish.strip(' ,.')
    # Collapse internal whitespace
    dish = re.sub(r'\s+', ' ', dish)
    return dish


# Words that indicate the match is likely a real food/dish item
FOOD_INDICATOR_WORDS = {
    # Proteins
    'chicken', 'beef', 'steak', 'lamb', 'pork', 'fish', 'salmon', 'cod',
    'prawn', 'prawns', 'shrimp', 'scallop', 'scallops', 'lobster', 'crab',
    'duck', 'venison', 'turkey', 'sausage', 'bacon', 'ham', 'chorizo',
    # Dishes
    'risotto', 'pasta', 'pizza', 'burger', 'pie', 'soup', 'salad', 'stew',
    'curry', 'tagine', 'paella', 'lasagne', 'lasagna', 'gnocchi', 'ragu',
    'ravioli', 'linguine', 'tagliatelle', 'penne', 'spaghetti', 'fettuccine',
    'casserole', 'hotpot', 'wellington', 'tartare', 'carpaccio',
    # Starters / sides
    'bruschetta', 'hummus', 'olives', 'bread', 'focaccia', 'fries', 'chips',
    'onion rings', 'coleslaw', 'halloumi', 'calamari', 'arancini',
    'burrata', 'mozzarella', 'prosciutto', 'antipasti',
    # Desserts
    'cake', 'brownie', 'cheesecake', 'mousse', 'tart', 'crumble',
    'pudding', 'tiramisu', 'panna cotta', 'ice cream', 'sorbet',
    'profiteroles', 'flapjack', 'toffee', 'chocolate', 'meringue',
    'pavlova', 'sundae', 'affogato',
    # Breakfast / brunch
    'eggs', 'egg', 'benedict', 'omelette', 'pancake', 'pancakes',
    'porridge', 'granola', 'toast', 'croissant', 'waffle', 'waffles',
    # Drinks that might be "ordered"
    'coffee', 'latte', 'cappuccino', 'espresso', 'cocktail', 'wine',
    'prosecco', 'gin', 'ale', 'beer', 'cider',
    # Cooking styles / adjectives that indicate food
    'roast', 'roasted', 'grilled', 'fried', 'baked', 'smoked', 'braised',
    'pan-fried', 'chargrilled', 'glazed', 'stuffed', 'wrapped',
    # Vegetables / ingredients
    'mushroom', 'mushrooms', 'truffle', 'asparagus', 'beetroot',
    'cauliflower', 'aubergine', 'courgette', 'spinach', 'kale',
    'avocado', 'tomato', 'potato', 'potatoes', 'sweet potato',
    # Misc
    'vegan', 'vegetarian', 'gluten', 'starter', 'main', 'dessert',
    'cocktail', 'sharing', 'platter', 'board', 'mezze',
    'sunday roast', 'fish and chips', 'full english',
}


def _edit_distance(a, b):
    """Simple Levenshtein distance for short strings."""
    if len(a) > len(b):
        a, b = b, a
    dists = list(range(len(a) + 1))
    for j, cb in enumerate(b):
        new_dists = [j + 1]
        for i, ca in enumerate(a):
            cost = 0 if ca == cb else 1
            new_dists.append(min(new_dists[i] + 1, dists[i + 1] + 1, dists[i] + cost))
        dists = new_dists
    return dists[-1]


def _determine_sentiment(text, match_start, match_end):
    """Determine sentiment from words surrounding a dish mention."""
    # Look at a window around the match
    window_start = max(0, match_start - 80)
    window_end = min(len(text), match_end + 80)
    window = text[window_start:window_end].lower()
    words = set(re.findall(r'\b\w+\b', window))

    pos_count = len(words & POSITIVE_WORDS)
    neg_count = len(words & NEGATIVE_WORDS)

    if pos_count > 0 and neg_count > 0:
        return "Mixed"
    elif pos_count > 0:
        return "Positive"
    elif neg_count > 0:
        return "Negative"
    return "Neutral"


def extract_dish_mentions(reviews):
    """Extract dish mentions from review text.

    Args:
        reviews: list of dicts, each with a "text" field.

    Returns:
        list of {"dish": str, "mentions": int, "sentiment": str} dicts,
        sorted by mention count descending.
    """
    dish_hits = defaultdict(lambda: {"count": 0, "pos": 0, "neg": 0, "mixed": 0, "neutral": 0})

    compiled = [re.compile(p, re.IGNORECASE) for p in FOOD_CONTEXT_PATTERNS]

    for review in reviews:
        text = review.get("text", "")
        if not text:
            continue

        for pattern in compiled:
            for match in pattern.finditer(text):
                raw = match.group(1)
                dish = _normalise_dish(raw)

                # Filter noise
                if len(dish) < 3:
                    continue
                # Reject if more than 5 words (likely a sentence fragment)
                dish_words = dish.split()
                if len(dish_words) > 5:
                    continue
                # Check if it's just stop words
                dish_word_set = set(dish_words)
                if dish_word_set.issubset(STOP_WORDS):
                    continue
                # Require at least one word that looks like food
                has_food_word = any(
                    w in FOOD_INDICATOR_WORDS for w in dish_words
                ) or any(
                    indicator in dish for indicator in FOOD_INDICATOR_WORDS
                    if len(indicator) > 3
                )
                if not has_food_word:
                    continue

                sentiment = _determine_sentiment(text, match.start(), match.end())
                dish_hits[dish]["count"] += 1
                if sentiment == "Positive":
                    dish_hits[dish]["pos"] += 1
                elif sentiment == "Negative":
                    dish_hits[dish]["neg"] += 1
                elif sentiment == "Mixed":
                    dish_hits[dish]["mixed"] += 1
                else:
                    dish_hits[dish]["neutral"] += 1

    if not dish_hits:
        return []

    # Deduplicate similar dishes (edit distance <= 2)
    dishes = sorted(dish_hits.keys())
    merged = {}
    skip = set()
    for i, d1 in enumerate(dishes):
        if d1 in skip:
            continue
        merged[d1] = dict(dish_hits[d1])
        for j in range(i + 1, len(dishes)):
            d2 = dishes[j]
            if d2 in skip:
                continue
            if _edit_distance(d1, d2) <= 2:
                # Merge into the one with more mentions
                merged[d1]["count"] += dish_hits[d2]["count"]
                merged[d1]["pos"] += dish_hits[d2]["pos"]
                merged[d1]["neg"] += dish_hits[d2]["neg"]
                merged[d1]["mixed"] += dish_hits[d2]["mixed"]
                merged[d1]["neutral"] += dish_hits[d2]["neutral"]
                skip.add(d2)

    # Build result
    result = []
    for dish, data in merged.items():
        pos = data["pos"]
        neg = data["neg"]
        mixed = data["mixed"]
        if pos > 0 and neg > 0:
            sentiment = "Mixed"
        elif pos > 0:
            sentiment = "Positive"
        elif neg > 0:
            sentiment = "Negative"
        elif mixed > 0:
            sentiment = "Mixed"
        else:
            sentiment = "Neutral"

        result.append({
            "dish": dish,
            "mentions": data["count"],
            "sentiment": sentiment,
        })

    result.sort(key=lambda x: (-x["mentions"], x["dish"]))
    return result


# ---------------------------------------------------------------------------
# Category resolution
# ---------------------------------------------------------------------------

def _resolve_category(venue_rec):
    """Map a venue to a trend category using category_resolved or Google types."""
    # Check explicit category first
    cat = (venue_rec.get("category_resolved") or "").lower()
    if "wine" in cat and "bar" in cat:
        return "wine_bar"
    if "pizza" in cat:
        return "pizzeria"
    if "pub" in cat or ("bar" in cat and "wine" not in cat):
        return "pub_dining"
    if "cafe" in cat or "coffee" in cat:
        return "cafe"

    # Fall back to Google types
    types = venue_rec.get("gty", [])
    types_str = " ".join(t.lower() for t in types) if types else ""
    name_lower = (venue_rec.get("n") or "").lower()

    if "wine_bar" in types_str or ("wine" in name_lower and "bar" in name_lower):
        return "wine_bar"
    if "pizza" in types_str or "pizza" in name_lower:
        return "pizzeria"
    if "pub" in types_str or "bar" in types_str:
        return "pub_dining"
    if "cafe" in types_str or "coffee" in types_str:
        return "cafe"

    return "casual_dining"


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def _detect_gaps(dish_mentions, category, venue_rec, reviews):
    """Detect gaps between guest praise and public listing visibility."""
    gaps = []
    gdesc = (venue_rec.get("gdesc") or "").lower()
    gty_str = " ".join(t.lower() for t in venue_rec.get("gty", []))

    # Gap 1: praised dishes not in Google description
    for item in dish_mentions:
        if item["sentiment"] == "Positive" and item["mentions"] >= 2:
            dish_lower = item["dish"].lower()
            # Check if any significant word from the dish appears in the listing
            dish_words = [w for w in dish_lower.split() if w not in STOP_WORDS and len(w) > 2]
            visible = any(w in gdesc or w in gty_str for w in dish_words)
            if not visible and dish_words:
                gaps.append({
                    "type": "dish_not_in_listing",
                    "dish": item["dish"],
                    "mentions": item["mentions"],
                    "message": (
                        f'"{item["dish"].title()}" appears {item["mentions"]} times '
                        f'with strong positive sentiment but your Google listing '
                        f'makes no mention of it. Guests are discovering this as a '
                        f'pleasant surprise \u2014 it should be a selling point, not a secret.'
                    ),
                })

    # Gap 2: category trend opportunities not reflected in reviews
    trends = CATEGORY_TRENDS_2026.get(category, CATEGORY_TRENDS_2026["default"])
    review_text_lower = " ".join(
        (r.get("text") or "").lower() for r in reviews
    )

    trend_keywords = {
        "natural wine": ["natural wine", "natural wines", "nat wine"],
        "small plates": ["small plates", "sharing", "tapas"],
        "non-alcoholic": ["non-alcoholic", "non alcoholic", "alcohol-free", "alcohol free", "mocktail"],
        "dog-friendly": ["dog friendly", "dog-friendly", "dogs welcome", "pet friendly"],
        "sunday roast": ["sunday roast", "roast dinner", "carvery"],
        "smash burger": ["smash burger", "smashburger"],
        "plant-based": ["plant-based", "plant based", "vegan", "vegetarian"],
        "pre-theatre": ["pre-theatre", "pre theatre", "pre-theater", "early bird"],
        "sourdough": ["sourdough", "long ferment"],
        "burrata": ["burrata"],
        "specialty coffee": ["specialty coffee", "speciality coffee", "single origin"],
        "brunch": ["brunch"],
        "seasonal": ["seasonal", "local produce", "locally sourced"],
    }

    for trend_text in trends:
        # Find which keyword group this trend relates to
        for label, keywords in trend_keywords.items():
            if any(kw in trend_text.lower() for kw in keywords):
                # Check if any of those keywords appear in review text
                mentioned = any(kw in review_text_lower for kw in keywords)
                if not mentioned:
                    gaps.append({
                        "type": "trend_opportunity",
                        "trend": trend_text,
                        "label": label,
                        "message": (
                            f"Category trend \u2014 {label}: {trend_text}. "
                            f"No guest mentions detected in current reviews. "
                            f"Worth exploring if this aligns with your offering."
                        ),
                    })
                break  # Only match first keyword group per trend

    return gaps


# ---------------------------------------------------------------------------
# Section builder (public API)
# ---------------------------------------------------------------------------

def build_menu_intelligence(w, venue_rec, review_intel, benchmarks):
    """Build the Menu & Dish Intelligence section.

    Args:
        w: line appender function
        venue_rec: venue record dict (from establishments JSON)
        review_intel: review intelligence dict (from review_analysis)
        benchmarks: peer benchmark dict
    """
    venue_rec = venue_rec or {}

    # Collect all review texts
    reviews = []
    for field in ["g_reviews", "ta_reviews"]:
        for r in venue_rec.get(field, []):
            text = r.get("text", "")
            if text:
                reviews.append(r)

    total_reviews = len(reviews)

    # Extract dish mentions
    dish_mentions = extract_dish_mentions(reviews)

    # Resolve category and get trends
    category = _resolve_category(venue_rec)
    trends = CATEGORY_TRENDS_2026.get(category, CATEGORY_TRENDS_2026["default"])

    # Detect gaps
    gaps = _detect_gaps(dish_mentions, category, venue_rec, reviews)

    # --- Render section ---
    w("## Menu & Dish Intelligence\n")

    # Part A: dish table
    w("### What Guests Are Ordering and Mentioning\n")

    if dish_mentions:
        w("| Dish / Item | Mentions | Sentiment |")
        w("|---|---|---|")
        for item in dish_mentions:
            sentiment_icon = {
                "Positive": "\u2705 Positive",
                "Negative": "\u274c Negative",
                "Mixed": "\u26a0\ufe0f Mixed",
                "Neutral": "\u2796 Neutral",
            }.get(item["sentiment"], item["sentiment"])
            w(f"| {item['dish'].title()} | {item['mentions']} | {sentiment_icon} |")
        w("")

        if total_reviews < 15:
            w(f"*Extracted from {total_reviews} reviews mentioning specific dishes. "
              f"Small sample \u2014 treat as directional.*\n")
        else:
            w(f"*Extracted from {total_reviews} reviews mentioning specific dishes.*\n")

        # Key signal from gap detection (dish not in listing)
        dish_gaps = [g for g in gaps if g["type"] == "dish_not_in_listing"]
        if dish_gaps:
            w(f"**Key signal:** {dish_gaps[0]['message']}\n")
    elif total_reviews < 3:
        w("No specific dish mentions detected in current review sample.\n")
    else:
        w("No specific dish mentions detected in current review sample. "
          "This may indicate reviews focus on service and atmosphere rather "
          "than individual dishes, or that the review volume is too low for "
          "dish-level extraction.\n")

    # Part B: category trends
    category_label = {
        "wine_bar": "Wine Bars",
        "pub_dining": "Pub Dining",
        "pizzeria": "Pizzerias",
        "casual_dining": "Casual Dining",
        "cafe": "Cafes",
    }.get(category, "UK Restaurants")

    w(f"### What's Trending in Your Category ({category_label}, UK, 2026)\n")
    for trend in trends:
        w(f"- {trend}")
    w("")

    # Opportunity gap from trend analysis
    trend_gaps = [g for g in gaps if g["type"] == "trend_opportunity"]
    if trend_gaps:
        # Pick the most relevant one (first)
        w(f"**Opportunity gap:** {trend_gaps[0]['message']}\n")
