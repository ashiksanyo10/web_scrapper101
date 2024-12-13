import re
import time
import logging
from bs4 import BeautifulSoup
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from datetime import datetime
from fuzzywuzzy import fuzz

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Start Chrome browser
def start_chrome(url, headless=True):
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = Chrome(options=options)
    driver.get(url)
    return driver

# Clean movie title to remove years or standalone numbers
def clean_movie_title(title):
    """
    Removes standalone years or numbers from the title.
    Example: "Absolutely Fabulous Christmas Special 2002" -> "Absolutely Fabulous Christmas Special"
    """
    cleaned_title = re.sub(r'\b(19|20)\d{2}\b', '', title)  # Removes years like 1990-2099
    cleaned_title = re.sub(r'\b\d+\b', '', cleaned_title)   # Removes standalone numbers
    return ' '.join(cleaned_title.split())  # Remove extra spaces

# Fuzzy match for movie titles
def fuzzy_match(search_title, movie_titles, threshold=80):
    """
    Finds the closest match for a movie title from a list of movie titles using fuzzy matching.
    """
    best_match = None
    highest_score = threshold
    for movie_title in movie_titles:
        score = fuzz.ratio(search_title.lower(), movie_title.lower())
        if score > highest_score:
            highest_score = score
            best_match = movie_title
    return best_match

# Fetch movie details from website
def get_movie_details_from_website(movie_name, director_name, retries=1):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    cleaned_title = clean_movie_title(movie_name)

    for attempt in range(retries):
        try:
            for title_to_search in [movie_name, cleaned_title]:
                search_url = base_url + title_to_search.replace(" ", "+")
                browser = start_chrome(search_url, headless=True)
                time.sleep(5)  # Wait for page to load
                page_source = browser.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                listings = soup.find_all('div', {'data-listing': ''})

                # Extract movie titles
                movie_titles = [listing.find('h3', class_='h2').get_text(strip=True) for listing in listings if listing.find('h3', class_='h2')]
                matched_title = fuzzy_match(title_to_search, movie_titles)

                for listing in listings:
                    title_tag = listing.find('h3', class_='h2')
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    if matched_title and title.lower() == matched_title.lower():
                        # Extract details
                        director_tag = listing.find('p', class_='small')
                        director_text = director_tag.get_text(strip=True) if director_tag else 'N/A'
                        
                        if director_name.lower() in director_text.lower():
                            classification_tag = listing.find('p', class_='large mb-2')
                            classification = classification_tag.get_text(strip=True) if classification_tag else 'N/A'

                            run_time = 'N/A'
                            label_issued_by = 'N/A'
                            table = listing.find('table', class_='rating-result-table')
                            if table:
                                lines = table.get_text(separator="\n", strip=True).split('\n')
                                for i, line in enumerate(lines):
                                    if 'Running time:' in line:
                                        run_time = lines[i + 1].strip()
                                    elif 'Label issued by:' in line:
                                        label_issued_by = lines[i + 1].strip()

                            release_year = director_text.split(',')[0].strip() if ',' in director_text else 'N/A'
                            browser.quit()
                            return {
                                'movie_name': title_to_search,
                                'director_name': director_name,
                                'classification': classification,
                                'release_year': release_year,
                                'run_time': run_time,
                                'label_issued_by': label_issued_by,
                            }
                browser.quit()
        except Exception as e:
            logging.error(f"Error fetching details for {movie_name} from website (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)

    return {
        'movie_name': movie_name,
        'director_name': 'N/A',
        'classification': 'N/A',
        'release_year': 'N/A',
        'run_time': 'N/A',
        'label_issued_by': 'N/A',
    }

# Process Excel input and output results
def process_movies(input_excel, output_excel):
    import pandas as pd

    # Read input Excel file
    df = pd.read_excel(input_excel)

    # Prepare output DataFrame
    results = []
    for _, row in df.iterrows():
        movie_name = row['Movie_name']
        director_name = row['Director_name']
        logging.info(f"Fetching details for: {movie_name} (Director: {director_name})")
        details = get_movie_details_from_website(movie_name, director_name)
        results.append(details)

    # Save results to a new Excel file
    output_df = pd.DataFrame(results)
    output_df.to_excel(output_excel, index=False)

# Main function
if __name__ == "__main__":
    input_file = "input_movies.xlsx"
    today_date = datetime.now().strftime("%Y-%m-%d")
    output_file = f"{today_date}-ProcessedMovies.xlsx"

    process_movies(input_file, output_file)
    logging.info(f"Processing completed. Results saved to {output_file}.")
