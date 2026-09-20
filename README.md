# Decision Diary

Decision Diary is a simple AI-ready web application that helps users compare their predictions with actual outcomes and understand their decision-making patterns.

## Features

- Create and save decisions
- Record expected outcome
- Set confidence level
- Record actual outcome
- Compare expected vs actual time
- Calculate prediction error
- Track success rate
- Confidence and decision insights
- Dashboard with charts
- SQLite database
- Responsive UI

## Run the project

### 1. Create virtual environment

```bash
python -m venv venv
```

### 2. Activate it on Windows

```bash
venv\Scripts\activate
```

### 3. Install requirements

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python app.py
```

### 5. Open in browser

http://127.0.0.1:5000

The database file `database.db` is created automatically.

## Optional real AI insights

The app can use the OpenAI Responses API for personalized decision insights.

Windows Command Prompt:

```bash
setx OPENAI_API_KEY "YOUR_API_KEY_HERE"
```

Close and reopen the terminal after `setx`, then run:

```bash
python app.py
```

Never put your real API key in GitHub or frontend JavaScript. If the key is not configured, the app automatically uses its local insight system.
