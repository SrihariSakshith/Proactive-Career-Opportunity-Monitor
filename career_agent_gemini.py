import os
import json
import time
import requests
from typing import TypedDict, List, Dict, Annotated
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

# --- Load Environment Variables ---
load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY not found in .env file. Please add it.")

# --- 1. Agent State ---
class AgentState(TypedDict):
    user_preferences: Dict
    websites_to_scan: List[Dict]
    raw_scraped_data: List[Dict]
    relevant_opportunities: List[Dict]
    new_opportunities: List[Dict]
    sent_job_ids: List[str]
    run_log: Annotated[list, add_messages]

# --- 2. Pydantic Models ---
class FilteredJob(BaseModel):
    title: str = Field(description="The extracted job title.")
    company: str = Field(description="The extracted company name.")
    reason_for_match: str = Field(description="A concise reason why this job matches the user's preferences.")
    url: str = Field(description="The URL for the job posting.")
    id: str = Field(description="The unique ID for the job, which is its URL.")

class JobFilterBatch(BaseModel):
    matched_jobs: List[FilteredJob] = Field(description="A list of job opportunities that match the user's criteria.")

# --- 3. SCRAPING FUNCTIONS (WITH DETAILED LOGGING) ---
def scrape_internshala(page, query: str) -> List[Dict]:
    print(f"   > Scraping Internshala for '{query}'...")
    url = f"https://internshala.com/internships/keywords-{query.replace(' ', '%20')}"
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    if page.is_visible("#no_thanks", timeout=2000): 
        page.locator("#no_thanks").click()
    
    container_selector = 'div.individual_internship'
    try:
        page.wait_for_selector(container_selector, timeout=15000)
    except PlaywrightTimeoutError:
        print("     - No job containers found on Internshala. Skipping.")
        return []
        
    job_containers = page.locator(container_selector).all()
    print(f"     - Found {len(job_containers)} potential job containers. Extracting raw data...")
    raw_data = []
    for i, container in enumerate(job_containers[:25]):
        print(f"       - Processing container {i+1}...", end='\r')
        try:
            link_element = container.locator('h3.job-internship-name a').first
            link = "https://internshala.com" + link_element.get_attribute('href')
            raw_text = container.inner_text()
            raw_data.append({"raw_text": raw_text, "url": link})
        except (PlaywrightTimeoutError, AttributeError):
            continue
    print(f"\n     - Successfully extracted {len(raw_data)} raw data blocks from Internshala.")
    return raw_data

def scrape_unstop(page, query: str) -> List[Dict]:
    print(f"   > Scraping Unstop for '{query}'...")
    url = f"https://unstop.com/internships?searchTerm={query.replace(' ', '%20')}"
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    time.sleep(3)

    container_selector = 'app-competition-listing > div'
    try:
        page.wait_for_selector(container_selector, timeout=15000)
    except PlaywrightTimeoutError:
        print("     - No job listings found on Unstop. Skipping.")
        return []

    job_cards = page.locator(container_selector).all()
    print(f"     - Found {len(job_cards)} potential job cards. Extracting raw data...")
    raw_data = []
    for i, card in enumerate(job_cards[:25]):
        print(f"       - Processing card {i+1}...", end='\r')
        try:
            container_id = card.get_attribute('id')
            if not container_id or len(container_id.split('_')) < 2:
                continue
            job_id = container_id.split('_')[1]
            link = f"https://unstop.com/o/i/{job_id}"
            raw_text = card.inner_text()
            raw_data.append({"raw_text": raw_text, "url": link})
        except (PlaywrightTimeoutError, AttributeError):
            continue
    print(f"\n     - Successfully extracted {len(raw_data)} raw data blocks from Unstop.")
    return raw_data

def scrape_remoteok(page, query: str) -> List[Dict]:
    print(f"   > Scraping RemoteOK for '{query}'...")
    url = f"https://remoteok.com/remote-{query}-jobs"
    page.goto(url, wait_until="domcontentloaded", timeout=90000)

    container_selector = 'tr.job:not(.placeholder)'
    try:
        page.wait_for_selector(container_selector, timeout=20000)
    except PlaywrightTimeoutError:
        print("     - No job rows found on RemoteOK after waiting. Skipping.")
        return []

    job_rows = page.locator(container_selector).all()
    print(f"     - Found {len(job_rows)} potential job rows. Extracting raw data...")
    raw_data = []
    for i, row in enumerate(job_rows[:25]):
        print(f"       - Processing row {i+1}...", end='\r')
        try:
            link_suffix = row.get_attribute('data-url')
            if link_suffix:
                link = "https://remoteok.com" + link_suffix
                raw_text = row.inner_text()
                raw_data.append({"raw_text": raw_text, "url": link})
        except (PlaywrightTimeoutError, AttributeError):
            continue
    print(f"\n     - Successfully extracted {len(raw_data)} raw data blocks from RemoteOK.")
    return raw_data

# --- 4. AGENT NODES ---
def plan_scraping_run(state: AgentState) -> dict:
    print("--- 📝 Planning Run ---")
    with open('user_preferences.json', 'r') as f: 
        user_preferences = json.load(f)
    try:
        with open('sent_jobs.json', 'r') as f: 
            sent_job_ids = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("   > sent_jobs.json not found or is empty. Starting fresh.")
        sent_job_ids = []
    
    keywords = user_preferences.get("keywords", ["developer"])
    long_query = " ".join(keywords[:3]) 
    simple_query = keywords[0]

    websites_to_scan = [
        {"name": "Internshala", "function": scrape_internshala, "query": long_query},
        {"name": "Unstop", "function": scrape_unstop, "query": long_query},
        {"name": "RemoteOK", "function": scrape_remoteok, "query": simple_query},
    ]
    return {
        "user_preferences": user_preferences, "sent_job_ids": sent_job_ids,
        "websites_to_scan": websites_to_scan, "run_log": [SystemMessage(content="Starting run with enhanced logging.")]
    }

def scrape_websites_node(state: AgentState) -> dict:
    print("--- 🌐 Scraping Raw Text from Websites ---")
    all_raw_data = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent='Mozilla/5.0')
        page = context.new_page()
        for site in state['websites_to_scan']:
            try:
                raw_data = site["function"](page, site["query"])
                all_raw_data.extend(raw_data)
            except Exception as e:
                print(f"   > FAILED to scrape {site['name']}. Error: {e}")
            time.sleep(1)
        browser.close()

    print(f"\n   > Found a total of {len(all_raw_data)} raw data blocks across all sites.")
    print("--- 💾 Saving all scraped raw data for review ---")
    with open('scraped_jobs_raw.json', 'w', encoding='utf-8') as f:
        json.dump(all_raw_data, f, indent=2, ensure_ascii=False)
    print(f"   > Successfully saved {len(all_raw_data)} raw items to scraped_jobs_raw.json")
    return {"raw_scraped_data": all_raw_data, "run_log": [SystemMessage(content=f"Scraped {len(all_raw_data)} raw data blocks.")]}

def structure_and_filter_node(state: AgentState) -> dict:
    print("--- 🤖🧠 Structuring and Filtering Data with Gemini (Single Call) ---")
    if not state['raw_scraped_data']:
        return {"relevant_opportunities": []}

    user_prefs = state['user_preferences']
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    structured_llm = llm.with_structured_output(JobFilterBatch)

    prompt = f"""You are a highly efficient career advisor and data processor. 
From the raw text blocks, extract Job Title, Company, and URLs. 
Filter only jobs that match these user preferences: {json.dumps(user_prefs, indent=2)}"""

    try:
        result = structured_llm.invoke(prompt)
        relevant_opportunities = [job.model_dump() for job in result.matched_jobs]
        print(f"   > Gemini found and filtered {len(relevant_opportunities)} relevant opportunities in a single step.")
    except Exception as e:
        print(f"   > An error occurred during Gemini call: {e}")
        relevant_opportunities = []
    
    return {"relevant_opportunities": relevant_opportunities, "run_log": [SystemMessage(content=f"Filtered {len(relevant_opportunities)} jobs.")]}

def deduplicate_node(state: AgentState) -> dict:
    print("--- 🗑️ De-duplicating Opportunities ---")
    sent_ids = set(state['sent_job_ids'])
    new_opportunities = [job for job in state['relevant_opportunities'] if job['id'] not in sent_ids]
    print(f" > Found {len(new_opportunities)} new jobs to alert.")
    return {"new_opportunities": new_opportunities, "run_log": [SystemMessage(content=f"Found {len(new_opportunities)} new jobs.")]}

def send_alert_node(state: AgentState) -> dict:
    print("--- 📧 Sending Alert via Telegram ---")
    new_jobs = state['new_opportunities']
    bot_token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not all([bot_token, chat_id]): return {}
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for job in new_jobs:
        message = (f"🚀 New Career Opportunity!\n\nTitle: {job['title']}\nCompany: {job['company']}\nReason: {job['reason_for_match']}\n\nApply Here: {job['url']}")
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
        try: 
            requests.post(api_url, data=payload)
        except Exception as e: 
            print(f" > An error occurred: {e}")
    updated_sent_ids = state['sent_job_ids'] + [job['id'] for job in new_jobs]
    with open('sent_jobs.json', 'w') as f: 
        json.dump(updated_sent_ids, f, indent=2)
    print(" > Updated sent_jobs.json.")
    return {"run_log": [SystemMessage(content=f"Sent alerts for {len(new_jobs)} jobs.")]}

def should_send_alert(state: AgentState) -> str:
    return "send_alert" if len(state['new_opportunities']) > 0 else "end_run"

# --- 5. Graph Definition ---
workflow = StateGraph(AgentState)
workflow.add_node("planner", plan_scraping_run)
workflow.add_node("scraper", scrape_websites_node)
workflow.add_node("structure_and_filter", structure_and_filter_node)
workflow.add_node("deduplicator", deduplicate_node)
workflow.add_node("alerter", send_alert_node)
workflow.set_entry_point("planner")
workflow.add_edge("planner", "scraper")
workflow.add_edge("scraper", "structure_and_filter")
workflow.add_edge("structure_and_filter", "deduplicator")
workflow.add_conditional_edges("deduplicator", should_send_alert, {"send_alert": "alerter", "end_run": END})
workflow.add_edge("alerter", END)
app = workflow.compile()

# --- 6. Run Agent ---
if __name__ == "__main__":
    print("🚀 Starting Proactive Career Opportunity Monitor (Transparent Version)...")
    final_state = app.invoke({})
    print("\n--- ✅ Agent Run Complete ---")
    print("Final Log:")
    for message in final_state.get('run_log', []):
        print(f"- {message.type.upper().replace('MESSAGE', '')}: {message.content}")
