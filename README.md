# JustPark Web Scraper

A Python script that automates logging into JustPark and downloading transaction data.

## Features

- Automated login to JustPark using credentials from environment variables
- Downloads transaction data from the billing dashboard
- Saves downloaded files with timestamps in a dedicated directory
- Command-line interface for flexible configuration
- Robust error handling and retry mechanism
- Detailed logging

## Requirements

- Python 3.12+
- Playwright
- Python-dotenv
- Other dependencies as specified in pyproject.toml

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install -e .
   ```
3. Install Playwright browsers:
   ```
   playwright install
   ```
4. Create a `.env` file with your JustPark credentials:
   ```
   JUSTPARK_EMAIL=your_email@example.com
   JUSTPARK_PASSWORD=your_password
   ```

## Usage

### Basic Usage

Run the script with default settings:

```
python justpark_scraper.py
```

### Command-line Options

The script supports several command-line options for customization:

```
python justpark_scraper.py --help
```

Available options:

- `--headless`: Run the browser in headless mode (no visible UI)
- `--retries N`: Set maximum number of retry attempts (default: 3)
- `--delay N`: Set delay between retry attempts in seconds (default: 5)
- `--output-dir PATH`: Specify directory to save downloaded files
- `--debug`: Enable debug logging

Examples:

```
# Run in headless mode with 5 retry attempts
python justpark_scraper.py --headless --retries 5

# Specify a custom output directory
python justpark_scraper.py --output-dir /path/to/downloads

# Enable debug logging
python justpark_scraper.py --debug
```

## Logs

The script generates logs in two places:
- Console output
- `scraper.log` file in the script directory

## Notes

- The script uses Playwright to automate browser interactions
- By default, the browser runs in visible mode for debugging
- For production use, use the `--headless` flag

## Security

- Never commit your `.env` file to version control
- Keep your credentials secure 