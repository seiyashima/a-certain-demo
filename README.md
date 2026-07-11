# a-certain-demo

Simple Flask demo app for connector/model integration experiments.

## Features

- Health check endpoint: `/healthz`
- Demo chat endpoint: `POST /api/chat`
- Browser UI for manual checks
- Request-scoped logging with `X-Request-Id`

## Project Structure

```
.
├── app.py
├── notion/
│   ├── __main__.py
│   ├── cli.py
│   ├── client.py
│   ├── blocks.py
│   ├── actions/
│   │   └── publish_design.py
│   ├── content/
│   │   ├── design.py
│   │   └── design_outline.md
├── requirements.txt
├── Dockerfile
├── Procfile
├── templates/
│   └── index.html
├── static/
│   ├── app.js
│   └── styles.css
└── tests/
		└── test_app.py
```

## Local Setup

1. Create a virtual environment.
2. Install dependencies.
3. Run the app.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open `http://127.0.0.1:8080`.

## Environment Variables

- `APP_ENV` (`development` or `production`)
- `PORT` (default: `8080`)
- `LOG_LEVEL` (default: `INFO`)
- `DEMO_MODE` (default: `echo`)
- `NOTION_API_TOKEN` (Notion API integration token)
- `NOTION_PAGE_ID` (target Notion page ID)
- `NOTION_ACTION` (`title` or `publish_design`)

## API

### Health Check

```sh
curl -s http://127.0.0.1:8080/healthz
```

Expected response:

```json
{"status": "ok"}
```

### Chat Endpoint

```sh
curl -s -X POST http://127.0.0.1:8080/api/chat \
	-H 'Content-Type: application/json' \
	-H 'X-Request-Id: demo-001' \
	-d '{"message":"hello"}'
```

## Tests

```sh
pytest
```

## Docker

```sh
docker build -t a-certain-demo .
docker run --rm -p 8080:8080 a-certain-demo
```

## Notion Integration

Create a local `.env` file from `.env.example` and set the Notion variables.

```sh
cp .env.example .env
```

To verify the configured page title:

```sh
python3 -m notion
```

To append the design outline blocks to the target page:

```sh
NOTION_ACTION=publish_design python3 -m notion
```

The design memo itself lives in `notion/content/design_outline.md` and is converted to Notion blocks at runtime.

Do not commit `.env` or any real token values.

## Deployment Notes

- `Procfile` is included for PaaS platforms using process types.
- Production serving should use `gunicorn` (already configured).
- Do not commit secrets; keep them in environment variables.
