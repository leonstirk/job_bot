# Job Application Bot 🤖

This Python project automates parts of the job application process by:

* Logging into Seek with a persistent browser profile
* Scraping saved job listings
* Downloading metadata and job descriptions
* Using the OpenAI API to generate tailored LaTeX cover letters
* Saving outputs to a structured folder for manual review and editing

## Setup

1. Clone the repo
2. Create a `.env` file with:
```OPENAI_API_KEY=your_api_key```
3. Install dependencies:
```pip install -r requirements.txt```

## Development status

Currently supports scraping from Seek NZ. More platforms and job description enhancements are planned. But you know, it's just a fun little script. Use it.

## License

MIT License

