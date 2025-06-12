from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import requests
import time
import json
import os
import re
import pprint
import unicodedata
from pathlib import Path
from bs4 import BeautifulSoup

def main():
    options = Options()
    options.add_argument("user-data-dir=/Users/deflatormaus/.seekbot-profile")  # fresh, isolated profile
    options.add_argument("--no-first-run")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--start-maximized")

    # (Optional) Add this if automation warning appears
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Launch Chrome
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # First time: manually log in
    #driver.get("https://www.seek.co.nz/")
    #time.sleep(10)  # Give yourself time to complete 2FA manually
    #input("Press Enter once logged in...")

    # Next time, the session will persist (cookies stored)
    driver.get("https://www.seek.co.nz/my-activity/saved-jobs")
    time.sleep(5)  # Allow page + session JS to load

    # Extract access token
    # Look for known token-like keys

    # Step 1: Extract all localStorage keys
    keys = driver.execute_script("return Object.keys(localStorage);")

    # Step 2: Loop through and find the relevant auth key

    auth_token = None
    for key in keys:
      if key.startswith("@@auth0spajs@@") and "candidate" in key:
          raw_data = driver.execute_script(f"return localStorage.getItem('{key}')")
          parsed = json.loads(raw_data)
          auth_token = parsed["body"]["access_token"]
          print(f"✅ Token found under key: {key}")
          break

    if not auth_token:
      raise RuntimeError("❌ Auth token not found in localStorage.")

    # print("🔑 Token:", auth_token)

    ## Alternative to loop to extract the token
    def extract_auth_token_from_local_storage(driver):
        raw_token_entry = driver.execute_script("""
            return Object.entries(window.localStorage).find(([k,v]) =>
                k.startsWith('@@auth0spajs@@') && JSON.parse(v).body?.access_token
            )?.[1];
        """)
        if not raw_token_entry:
            raise ValueError("Auth token not found in localStorage.")
        return json.loads(raw_token_entry)["body"]["access_token"]

    access_token = extract_auth_token_from_local_storage(driver)


    # Extract cookies
    selenium_cookies = driver.get_cookies()
    cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in selenium_cookies])

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Referer": "https://www.seek.co.nz/my-activity/saved-jobs",
        "Origin": "https://www.seek.co.nz",
        "Cookie": cookie_header,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15)"
    }

    session = requests.Session()
    session.headers.update(headers)

    ## Build the GraphQL payload
    query = """
    query GetSavedJobs($first: Int, $locale: Locale!, $timezone: Timezone!) {
          viewer {
            id
            savedJobs(first: $first) {
              edges {
                node {
                  id
                  isActive
                  isExternal
                  createdAt {
                    shortAbsoluteLabel(timezone: $timezone, locale: $locale)
                  }
                  job {
                    id
                    title
                    location {
                      label(locale: $locale, type: SHORT)
                    }
                    abstract
                    createdAt {
                      label(context: JOB_POSTED, length: SHORT, timezone: $timezone, locale: $locale)
                    }
                    advertiser {
                      name(locale: $locale)
                    }
                    salary {
                      label
                    }
                  }
                }
              }
            }
          }
        }
    """

    payload = {
          "operationName": "GetSavedJobs",
        "variables": {
            "first": 100,
            "locale": "en-NZ",
            "timezone": "Pacific/Auckland"
        },
        "query": query  # ← this must be a string
    }


    ## Make the GraphQL request
    response = requests.post("https://www.seek.co.nz/graphql", headers=headers, json=payload)

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("❌ HTTP error:", e)
        print("🔻 Full response text:", response.text)
        raise

    data = response.json()

    #print("🔍 Full response preview:")
    #pprint.pprint(data)

    # Print preview
    for edge in data.get("data", {}).get("viewer", {}).get("savedJobs", {}).get("edges", []):
        job = edge["node"]["job"]
        print("🧾", job["title"])
        print("🏢", job["advertiser"]["name"])
        print("📍", job["location"]["label"])
        print("📝", job["abstract"][:100] + "...")
        print("📅", job["createdAt"]["label"])
        print("-" * 40)

    SANDBOX_DIR = Path("jobs")
    SANDBOX_DIR.mkdir(exist_ok=True)

    def get_saved_jobs(session):
        response = session.post("https://www.seek.co.nz/graphql", json=payload)
        response.raise_for_status()
        return response.json()

    saved_jobs_data = get_saved_jobs(session)
    print(saved_jobs_data)

    def extract_job_description(session, job_id):
        """Given a job ID, fetch and parse the job page to return job description text."""
        url = f"https://www.seek.co.nz/job/{job_id}?ref=saved"
        response = session.get(url)
        if response.status_code != 200:
            return f"[Failed to fetch job page: {response.status_code}]"

        soup = BeautifulSoup(response.text, "html.parser")
        desc_div = soup.find("div", {"data-automation": "jobAdDetails"})
        return desc_div.get_text(separator="\n").strip() if desc_div else "[No description found]"

    def sanitize_filename(title: str) -> str:
        title = unicodedata.normalize("NFKD", title)
        title = title.encode("ascii", "ignore").decode("ascii")
        title = re.sub(r"[^\w\s-]", "", title)  # remove non-filename-safe chars
        title = re.sub(r"\s+", "_", title.strip())  # replace spaces with _
        return title[:60]  # truncate long titles if needed

    def process_and_save_jobs(session, jobs):
        """Given a list of job metadata, scrape and save job pages with metadata to disk."""
        for i, job_edge in enumerate(jobs, 1):
            node = job_edge["node"]
            job = node["job"]
            job_id = job["id"]
            title = job["title"]
            company = job["advertiser"]["name"]
            location = job.get("location", {}).get("label", "N/A")
            teaser = job.get("abstract", "")[:150]
            # salary = job.get("salary", {}).get("label", "N/A")
            salary = (job.get("salary") or {}).get("label", "N/A")
            created = job["createdAt"]["label"]

            # Scrape full job description
            description = extract_job_description(session, job_id)

            # Prepare folder + save
            folder_name = f"{sanitize_filename(title[:40])}_{job_id}"
            folder_path = SANDBOX_DIR / folder_name
            folder_path.mkdir(exist_ok=True)

            # Metadata
            metadata = {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "posted": created,
                "teaser": teaser,
            }

            with open(folder_path / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)

            with open(folder_path / "job_description.txt", "w") as f:
                f.write(description)

            print(f"✅ Saved: {title} ({company})")

    jobs = data["data"]["viewer"]["savedJobs"]["edges"]
    process_and_save_jobs(session, jobs)        


    input("Press Enter to quit...")
    driver.quit()

if __name__ == "__main__":
    main()
