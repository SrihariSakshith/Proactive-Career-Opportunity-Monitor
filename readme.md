# 🤖 Proactive Career Opportunity Monitor

An autonomous AI agent that scrapes multiple job websites, intelligently filters opportunities based on your personal preferences, and sends real-time alerts for new, relevant jobs directly to your Telegram.

---

## 🌟 Overview

This project automates the tedious process of searching for internships and entry-level jobs.  
It scrapes job postings, structures the data, filters opportunities based on your preferences, and notifies you instantly on Telegram.

Key ideas:
- **Dumb Scraper, Smart AI:**  
  Scrapers collect raw data; Gemini AI handles structuring & filtering.
- **Single AI Call Optimization:**  
  Extracts and filters jobs in one API call to save on quota and reduce latency.

---

## ✨ Core Features
- **Autonomous Operation:** End-to-end automation in a single run.
- **Multi-Website Scraping:** Currently supports Internshala, Unstop, and RemoteOK.
- **AI-Powered Filtering:** Uses Google Gemini to analyze and match jobs to your preferences.
- **Duplicate Prevention:** Tracks jobs already sent to you via `sent_jobs.json`.
- **Telegram Alerts:** Sends notifications directly to your Telegram.
- **Customizable:** Control everything via `user_preferences.json`.

---

## 🏗️ How It Works: Agentic Workflow

The agent is built as a **state machine using LangGraph**, running sequentially through these nodes:

1. **Planner:** Loads user preferences and previously sent jobs.  
2. **Scraper:** Uses Playwright to scrape job listings.  
3. **Structure & Filter:** Uses Gemini AI to extract & match relevant jobs.  
4. **Deduplicator:** Finds only new opportunities.  
5. **Alerter:** Sends alerts to your Telegram.

---

## 🛠️ Technology Stack
- **Orchestration:** LangGraph  
- **AI Model:** Google Gemini 1.5 Flash  
- **Web Scraping:** Playwright  
- **Language:** Python  
- **APIs:** Requests  
- **Environment Management:** python-dotenv  

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+
- Git

---

### 2. Installation

**1. Clone the repository:**
```bash
git clone https://github.com/your-username/proactive-career-monitor.git
cd proactive-career-monitor
````

**2. Create and activate a virtual environment:**

Windows:

```bash
python -m venv myenv
myenv\Scripts\activate
```

macOS / Linux:

```bash
python3 -m venv myenv
source myenv/bin/activate
```

**3. Install dependencies:**

```bash
pip install -r requirements.txt
```

**4. Create a `.env` file in the root folder and add:**

```env
# Get yours from Google AI Studio or Google Cloud Console
GOOGLE_API_KEY="YOUR_GOOGLE_API_KEY_HERE"

# Get from Telegram by talking to @BotFather
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN_HERE"

# Get from a bot like @userinfobot
TELEGRAM_CHAT_ID="YOUR_TELEGRAM_CHAT_ID_HERE"
```

---

### 3. Configure Preferences

Edit `user_preferences.json`:

```json
{
  "role": "Software Developer Intern",
  "keywords": [
    "python",
    "backend",
    "web developer",
    "software engineer",
    "full stack",
    "devops",
    "API",
    "django",
    "data science"
  ],
  "graduation_year": 2026,
  "experience_level": "Internship or Entry-Level"
}
```

---

### 4. Run the Agent

```bash
python career_agent_gemini.py
```

Check your Telegram for alerts! 🎉

---

## 📂 Project Structure

```
.
├── career_agent_gemini.py  # Main script with the agent workflow
├── requirements.txt        # Python dependencies
├── .env                    # Your API keys (not tracked by Git)
├── user_preferences.json   # Your job search preferences
├── sent_jobs.json          # (Auto-generated) Tracks already sent jobs
├── scraped_jobs_raw.json   # (Auto-generated) Raw scraped data
└── README.md               # This file
```

---

## 📈 Future Improvements

* Add more job boards (LinkedIn, Indeed, Y Combinator, etc.)
* Replace `sent_jobs.json` with a database (SQLite/PostgreSQL)
* Add a Streamlit/Flask dashboard
* Automate runs with a scheduler (cron, APScheduler)

