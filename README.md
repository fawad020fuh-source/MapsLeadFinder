# MapsLeadFinder

MapsLeadFinder is a Python desktop/CLI tool that searches Google Maps using the Places API (New), collects businesses across multiple pages and deep-search regions, visits each company website, extracts publicly listed business contact emails, and exports everything to CSV/XLSX.

## Features

- Google Places API text search and business metadata collection
- Deep search mode with grid-based zoning for broader area coverage
- Pagination through all available result pages
- Deduplication by Google place_id
- Public business email extraction from official site pages and contact links
- CSV + XLSX export
- Streamlit GUI and command-line mode
- Resume support using SQLite cache
- Basic validation, rate limiting, and robots.txt checks

## Installation

1. Clone this repo.
2. Create a virtual environment.
3. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and add your Google API key.

```bash
cp .env.example .env
```

## Getting a Google API Key

1. Go to https://console.cloud.google.com/
2. Create or select a project.
3. Enable the Google Places API (New) and Geocoding API.
4. Create an API key.
5. Restrict it to your needs and add the key to `.env`:

```dotenv
GOOGLE_API_KEY=your_google_places_api_key_here
```

## Usage

CLI mode:

```bash
python main.py --keyword "dentist" --location "Lahore, Pakistan" --max-results 40 --radius-km 15 --deep-search
```

Keyword variations:

```bash
python main.py --keyword "dentist" --location "Lahore, Pakistan" --max-results 50 --variation "family dentist" --variation "cosmetic dentist"
```

GUI mode:

```bash
python main.py
```

This starts the Streamlit interface.

## Output

The tool writes:

- `output/businesses.csv`
- `output/businesses.xlsx`

## Deep Search and Pagination

Google text search limits a single query to roughly 60 results. MapsLeadFinder adds a deep-search mode that splits the search area into a grid and runs queries in multiple smaller zones, combining the results and deduplicating by `place_id`.

## Legal Notice and Safety

MapsLeadFinder is intended for lawful, publicly available business contact discovery. Users are required to follow Google API terms, local laws, and email compliance requirements, including but not limited to CAN-SPAM, GDPR, and any applicable anti-spam laws. When emailing results, include a valid unsubscribe option, honest sender information, and only use publicly listed business contact addresses.

## Limitations

- Google Places API quotas and usage caps apply.
- Some business websites block bots or hide contact details behind forms.
- The tool only collects publicly listed contact emails from a business's own website.
- Websites may change frequently, so results should be revalidated before outreach.

## Screenshots

![UI screenshot placeholder](docs/screenshots/example.png)

> Add screenshot images under `docs/screenshots/` if you want to publish the project with examples.

## License

MIT License.

## Project Structure

```text
MapsLeadFinder/
├── src/
│   ├── api_client.py
│   ├── crawler.py
│   ├── email_extractor.py
│   ├── exporter.py
│   ├── grid.py
│   ├── app.py
│   └── __init__.py
├── tests/
│   ├── test_email_extractor.py
│   └── test_pagination.py
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── main.py
├── requirements.txt
└── output/
```

