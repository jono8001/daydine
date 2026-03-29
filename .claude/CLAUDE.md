# DayDine Project State

## What It Is
UK restaurant tracking and ranking platform. MVP shows 264,791 FSA establishments searchable by local authority, business type, rating, and name. Phase 2 will add Google Places, TripAdvisor, editorial data, and composite Evidtrace scoring (RCS 0-10).

## Architecture
- Frontend: Single index.html (static) on Vercel at daydine.vercel.app
- Database: Firebase RTDB at https://recursive-research-eu-default-rtdb.europe-west1.firebasedatabase.app under /daydine path
- Firebase project: recursive-research-eu (Spark plan, europe-west1)
- GitHub: jono8001/daydine (auto-deploys to Vercel on push to main)

## What's Built & Deployed
- index.html: Consumer-facing frontend with warm cream (#F5F0E8) theme, amber (#D4942A) accents, Inter font, DayDine branding with amber dot on 'i'
- firebase-rules.json: Public read on /daydine, no public write, indexes on la/rating/type/postcode. Evidtrace rules preserved.
- vercel.json: Static site config with SPA fallback
- Firebase web app registered as 'DayDine' with config values injected into index.html
- 264,791 FSA establishments uploaded to Firebase via firebase_upload.py (on local machine)

## Data Schema (per record in /daydine)
name, address, postcode, la (local authority), type (business type), rating (FSA 0-5), scores (hygiene/structural/management sub-scores), lastInspection (date)

## Local Files (C:\Users\Jon Swaby\Projects\Daydine)
- fsa_agent.py: Pulls FSA data from api.ratings.food.gov.uk
- consolidate_fsa.py: Merges FSA JSON files into daydine-data.json (61MB)
- firebase_upload.py: Uploads daydine-data.json to Firebase RTDB
- daydine-data.json: 264,791 consolidated records
- fsa_data/: Raw FSA API responses

## Reference Documents (in evidtrace-agents folder)
- UK-Restaurant-Tracker-Plan.docx: Feasibility plan with data sources, scoring weights, architecture, MVP scope, timeline
- UK-Restaurant-Tracker-Methodology-Spec.docx: Formal mathematical model for RCS scoring (weighted aggregation, convergence adjustment, temporal decay, penalty rules, calibration)

## What's Next (Phase 2)
1. Google Places enrichment (ratings, review counts) - start with London
2. Composite scoring engine (restaurant_confidence.py) implementing RCS methodology
3. TripAdvisor integration
4. Editorial scanning via Brave Search API
5. Expandable detail rows with score breakdown
6. Tier assignment (Exceptional/Recommended/Acceptable/Caution/Avoid)

## Environment
- Windows 11, Python 3.x
- Firebase credentials: C:\Users\Jon Swaby\OneDrive\Documents\evidtrace-agents\firebase_credentials.json
- Database URL env var: FIREBASE_DATABASE_URL
