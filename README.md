# LLM Analysis Quiz Solver

An automated quiz-solving system built with FastAPI and Playwright that handles various quiz types including data analysis, calculations, and embedded JSON tasks.

## Features

- 🚀 **Fast API endpoint** for receiving quiz tasks
- 🤖 **Headless browser automation** using Playwright
- 📊 **Data analysis** support (CSV, Excel files)
- 🔄 **Chained task handling** for multi-step quizzes
- ⏱️ **3-minute timeout** per task as required
- 🛡️ **No LLM dependency** - uses deterministic parsing for reliability

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   Client    │─────▶│  FastAPI     │─────▶│  Playwright │
│  (POST)     │      │  /task       │      │   Runner    │
└─────────────┘      └──────────────┘      └─────────────┘
                            │                      │
                            │                      ▼
                            │              ┌─────────────┐
                            │              │  Handlers   │
                            │              │  - JSON     │
                            │              │  - CSV/XLS  │
                            │              │  - Calc     │
                            │              └─────────────┘
                            ▼
                     ┌──────────────┐
                     │  Background  │
                     │   Worker     │
                     └──────────────┘
```

## Installation

### Local Development

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd llm-quiz-solver
```

2. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
playwright install chromium
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env and set your QUIZ_SECRET
```

5. **Run the application**
```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

### Docker Deployment

1. **Build the image**
```bash
docker build -t quiz-solver .
```

2. **Run the container**
```bash
docker run -d \
  -p 8000:8000 \
  -e QUIZ_SECRET=your-secret-here \
  --name quiz-solver \
  quiz-solver
```

## API Usage

### Submit a Task

```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "secret": "your-secret",
    "url": "https://example.com/quiz"
  }'
```

**Response:**
```json
{
  "status": "accepted",
  "message": "Task queued for processing"
}
```

### Health Check

```bash
curl http://localhost:8000/health
```

## How It Works

### 1. Task Reception
- Client POSTs task details to `/task` endpoint
- Server validates the secret
- Task is queued as a background job
- HTTP 200 response returned immediately

### 2. Browser Automation
- Playwright launches headless Chromium
- Navigates to the quiz URL
- Extracts HTML, text content, and embedded JSON

### 3. Quiz Solving
The system uses multiple strategies to solve different quiz types:

#### Strategy 1: JSON Quizzes
```python
# Detects embedded JSON with quiz data
if 'answer' in extracted_json:
    answer = extracted_json['answer']
```

#### Strategy 2: Data Analysis
```python
# Downloads CSV/Excel files
# Parses instructions like "sum column X on page Y"
df = pd.read_csv(file_url)
answer = df['column'].sum()
```

#### Strategy 3: Calculations
```python
# Extracts numbers and performs operations
numbers = extract_numbers(text)
if 'sum' in instruction:
    answer = sum(numbers)
```

### 4. Answer Submission
- Locates submit URL in the page
- POSTs answer with email, secret, url
- Handles chained tasks if response contains new URL

## Project Structure

```
llm-quiz-solver/
├── app/
│   ├── __init__.py       # Package initialization
│   ├── main.py           # FastAPI application
│   ├── runner.py         # Playwright orchestration
│   └── handlers.py       # Quiz-solving logic
├── Dockerfile            # Container configuration
├── requirements.txt      # Python dependencies
├── .env.example         # Environment template
└── README.md            # This file
```

## Supported Quiz Types

| Quiz Type | Detection | Solution Method |
|-----------|-----------|-----------------|
| JSON Embedded | JSON object in page | Direct extraction |
| CSV Analysis | Keywords + .csv link | Pandas operations |
| Excel Analysis | Keywords + .xlsx link | Pandas operations |
| Simple Calculation | "calculate" + numbers | Regex + math |
| Chained Tasks | Response contains URL | Recursive solving |

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QUIZ_SECRET` | Yes | `dev-secret` | Authentication secret |
| `PORT` | No | `8000` | Server port |
| `HOST` | No | `0.0.0.0` | Server host |

### Timeout Settings

- **Per-task timeout**: 180 seconds (3 minutes)
- **Network timeout**: 30 seconds
- **Playwright timeout**: 30 seconds

## Extending the System

### Adding New Quiz Types

1. Create a new handler in `app/handlers.py`:

```python
async def handle_new_quiz_type(email, secret, url, body_text, html):
    # Your parsing logic
    answer = parse_and_solve(body_text)
    submit_url = find_submit_url(html)
    
    return {
        'email': email,
        'secret': secret,
        'url': url,
        'answer': answer,
        'submit_url': submit_url
    }
```

2. Add detection logic in `solve_from_page_content()`:

```python
if 'your-keyword' in body_text.lower():
    result = await handle_new_quiz_type(...)
    if result:
        return result
```

## Troubleshooting

### Common Issues

**Issue**: Playwright fails to launch
```bash
# Reinstall browsers
playwright install chromium --with-deps
```

**Issue**: Task times out
- Check if quiz requires user interaction
- Verify network connectivity
- Increase timeout if legitimate complexity

**Issue**: Answer submission fails
- Verify submit URL detection logic
- Check response format matches expected payload
- Add logging to see exact submission data

### Debugging

Enable verbose logging:
```python
# In app/runner.py
print(f"Body text: {body_text}")
print(f"Extracted JSON: {extracted_json}")
print(f"Answer payload: {answer_payload}")
```

## Testing

```bash
# Run basic tests
pytest

# Test specific quiz type
pytest tests/test_handlers.py::test_csv_quiz

# Test with demo URL
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "secret": "dev-secret",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

## Performance Considerations

- **Memory**: Each Playwright instance uses ~100-200MB
- **CPU**: Minimal, mostly I/O bound
- **Network**: Download speeds affect CSV/Excel tasks
- **Concurrency**: Background tasks run independently

## Security Notes

- Always use HTTPS URLs
- Store secrets in environment variables
- Validate all user inputs
- Run container as non-root user
- Set resource limits in production

## Why No LLM?

This system intentionally **avoids LLM usage** because:

1. **Accuracy**: Deterministic parsing is more reliable for structured data
2. **Speed**: No API calls means faster response times
3. **Cost**: No per-request LLM charges
4. **Reliability**: No hallucination or rate limiting issues
5. **Simplicity**: Easier to debug and maintain

Quiz tasks typically have predictable patterns that regex, pandas, and BeautifulSoup handle excellently.

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Open a GitHub issue
- Check existing issues for solutions
- Review logs for error messages