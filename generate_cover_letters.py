import os
import json
from openai import OpenAI
from pathlib import Path
from jinja2 import Template
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Paths
ROOT_DIR = Path("jobs")  # or wherever your saved job folders are
PROMPT_PATH = Path("prompts/prompt_template.txt")
CV_PATH = Path("prompts/cv_full.txt")  # or use summary version if preferred (prompt/cv_summary.txt)

def render_prompt(job_metadata, job_description, cv_text, prompt_template):
    template = Template(prompt_template)
    return template.render(
        job_title=job_metadata.get("job_title", "Unknown Title"),
        employer=job_metadata.get("employer", "Unknown Employer"),
        job_description=job_description,
        cv_text=cv_text
    )

def generate_cover_letter(prompt, model="gpt-4o"):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that writes professional cover letters."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content



def process_all_jobs():
    prompt_template = PROMPT_PATH.read_text()
    cv_text = CV_PATH.read_text()

    for job_dir in ROOT_DIR.iterdir():
        if not job_dir.is_dir():
            continue

        metadata_path = job_dir / "metadata.json"
        jobdesc_path = job_dir / "job_description.txt"
        output_path = job_dir / "cover_letter.tex"

        # Skip if already generated
        if output_path.exists():
            print(f"✅ Cover letter already exists for {job_dir.name}, skipping.")
            continue

        # Load metadata and description
        try:
            metadata = json.loads(metadata_path.read_text())
            job_description = jobdesc_path.read_text()
        except Exception as e:
            print(f"⚠️ Skipping {job_dir.name}: {e}")
            continue

        # Render prompt and call API
        prompt = render_prompt(metadata, job_description, cv_text, prompt_template)
        print(f"📝 Generating letter for: {metadata.get('job_title', job_dir.name)}")

        try:
            letter = generate_cover_letter(prompt)
            if letter is not None:
                output_path.write_text(letter)
                print(f"✅ Saved to {output_path.name}")
            else:
                print(f"⚠️ No letter returned for {job_dir.name}")
        except Exception as e:
            print(f"❌ Failed for {job_dir.name}: {e}")


if __name__ == "__main__":
    process_all_jobs()