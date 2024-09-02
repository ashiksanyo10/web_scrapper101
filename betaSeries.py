import datetime
import pandas as pd
from bs4 import BeautifulSoup
from helium import start_chrome, write, click, S, find_all, get_driver
import time
from flask import Flask, request, send_file, jsonify
import logging
import re

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# MR Mapping
mr_mapping = {
    "Suitable for general audiences": "G",
    "Parental guidance recommended for younger viewers": "PG",
    "Suitable for mature audiences": "M",
    "Unsuitable for audiences under 13 years of age": "13",
    "Restricted to persons 13 years and over": "R13",
    "Restricted to persons 13 years and over unless accompanied by a parent or guardian": "RP13",
    "Restricted to persons 15 years and over": "R15",
    "Unsuitable for audiences under 16 years of age": "16",
    "Restricted to persons 16 years and over": "R16",
    "Restricted to persons 16 years and over unless accompanied by a parent or guardian": "RP16",
    "Unsuitable for audiences under 18 years of age": "18",
    "Restricted to persons 18 years and over": "R18",
    "Restricted to persons 17 years and over unless accompanied by a parent or guardian": "RP18"
}

def wait_for_element(selector, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if selector.exists():
            return True
        time.sleep(0.5)
    return False

def is_valid_director_name(name):
    return bool(name) and re.match("^[a-zA-Z ]+$", name)

def get_movie_details_from_website(season_name, season_number, episode_number, director_name, retries=1):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_query = f"{season_name}, Season {season_number}, Episode {episode_number}"
    search_url = base_url + search_query.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)  # Wait for the page to load
            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Check for Featured Result
            featured_result_tag = soup.find('h2', class_='h6 mb-10')
            if featured_result_tag and "Featured Results" in featured_result_tag.text:
                link = browser.current_url
                browser.quit()
                return {
                    'season_name': season_name,
                    'season_number': season_number,
                    'episode_number': episode_number,
                    'director_name': director_name,
                    'classification': 'N/A',
                    'MR_code': 'N/A',  # Ensure MR_code is 'N/A'
                    'release_year': 'N/A',
                    'run_time': 'N/A',
                    'label_issued_by': 'N/A',
                    'label_issued_on': 'N/A',
                    'Is_Featured_Result': 'Yes',
                    'CD': 'N/A',
                    'link': link
                }

            # Iterate through search results
            listings = soup.find_all('div', {'data-listing': ''})
            for listing in listings:
                title_tag = listing.find('h3', class_='h2')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                director_tag = listing.find('p', class_='small')
                if not director_tag:
                    continue
                director_text = director_tag.get_text(strip=True)
                if director_name.lower() in director_text.lower():
                    # Extract classification (for MR mapping)
                    classification_tag = listing.find('p', class_='large')
                    classification = classification_tag.get_text(strip=True) if classification_tag else 'N/A'
                    
                    # Correctly handle MR_code mapping or 'N/A'
                    MR_code = mr_mapping.get(classification, 'N/A') if classification != 'N/A' else 'N/A'

                    # Extract CD
                    cd_tag = listing.find('p', class_='large mb-2')
                    cd_value = cd_tag.get_text(strip=True) if cd_tag else 'N/A'

                    # Extract release year, runtime, label, and label issued on
                    table = listing.find('table', class_='rating-result-table')
                    run_time = 'N/A'
                    label_issued_by = 'N/A'
                    label_issued_on = 'N/A'
                    if table:
                        lines = table.get_text(separator="\n", strip=True).split('\n')
                        for i, line in enumerate(lines):
                            if 'Running time:' in line:
                                run_time = lines[i + 1].strip()
                            elif 'Label issued by:' in line:
                                label_issued_by = lines[i + 1].strip()
                            elif 'Label issued on:' in line:
                                label_issued_on = lines[i + 1].strip()

                    parts = director_text.split(',')
                    release_year = parts[0].strip() if len(parts) > 1 else 'N/A'

                    link = browser.current_url
                    browser.quit()
                    return {
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'director_name': director_name,
                        'classification': classification,
                        'MR_code': MR_code,
                        'release_year': release_year,
                        'run_time': run_time,
                        'label_issued_by': label_issued_by,
                        'label_issued_on': label_issued_on,
                        'Is_Featured_Result': 'No',
                        'CD': cd_value,
                        'link': link
                    }
            browser.quit()
        except Exception as e:
            logging.error(f"Error fetching details for {season_name}, Season {season_number}, Episode {episode_number} from website (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)  # Wait before retrying
    return None

def get_movie_details_from_nz_website(season_name, season_number, episode_number, director_name, retries=1):
    base_url = "https://www.fvlb.org.nz/search/"
    search_query = f"{season_name} Season {season_number} Episode {episode_number}"
    search_url = base_url + search_query.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)  # Wait for the page to load
            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            # Iterate through search results
            listings = soup.find_all('div', {'class': 'result-item'})
            for listing in listings:
                title_tag = listing.find('h3')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                director_tag = listing.find('p', class_='director')
                if not director_tag:
                    continue
                director_text = director_tag.get_text(strip=True)
                if director_name.lower() in director_text.lower():
                    # Extract classification (for MR mapping)
                    classification_tag = listing.find('p', class_='rating')
                    classification = classification_tag.get_text(strip=True) if classification_tag else 'N/A'
                    mr_code = mr_mapping.get(classification, 'N/A')

                    # Extract CD
                    cd_tag = listing.find('p', class_='content-description')
                    cd_value = cd_tag.get_text(strip=True) if cd_tag else 'N/A'

                    # Extract release year, runtime, label, and label issued on
                    release_year = 'N/A'
                    run_time = 'N/A'
                    label_issued_by = 'N/A'
                    label_issued_on = 'N/A'

                    link = browser.current_url
                    browser.quit()
                    return {
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'director_name': director_name,
                        'classification': mr_code,
                        'release_year': release_year,
                        'run_time': run_time,
                        'label_issued_by': label_issued_by,
                        'label_issued_on': label_issued_on,
                        'Is_Featured_Result': 'None',
                        'CD': cd_value,
                        'link': link
                    }
            browser.quit()
        except Exception as e:
            logging.error(f"Error fetching details for {season_name}, Season {season_number}, Episode {episode_number} from NZ website (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)  # Wait before retrying
    return None

@app.route('/')
def index():
    return send_file('index2.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            # Process the Excel file
            df = pd.read_excel(file)
            season_names = df['Season_name'].tolist()
            season_numbers = df['Season_number'].tolist()
            episode_numbers = df['Episode_number'].tolist()
            director_names = df['Director_name'].tolist()

            results = []
            for season_name, season_number, episode_number, director_name in zip(season_names, season_numbers, episode_numbers, director_names):
                if not season_name:
                    results.append({
                        'season_name': 'No Season name',
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'director_name': director_name,
                        'classification': 'No Season name',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'Is_Featured_Result': 'none',
                        'CD': 'No Season name',
                        'link': 'N/A'
                    })
                    continue

                if not is_valid_director_name(director_name):
                    results.append({
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'director_name': 'No Director name',
                        'classification': 'No Director name',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'Is_Featured_Result': 'none',
                        'CD': 'No Director name',
                        'link': 'N/A'
                    })
                    continue

                # Attempt to get details from the first website
                details = get_movie_details_from_website(season_name, season_number, episode_number, director_name)
                
                # If the first website does not return details, try the second website
                if not details:
                    details = get_movie_details_from_nz_website(season_name, season_number, episode_number, director_name)

                if not details:
                    details = {
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'director_name': director_name,
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'Is_Featured_Result': 'none',
                        'CD': 'N/A',
                        'link': 'N/A'
                    }
                
                results.append(details)

            # Save the combined results to an Excel file
            results_df = pd.DataFrame(results)
            filename = 'series_classifications.xlsx'
            results_df.to_excel(filename, index=False)

            return jsonify({'download_url': f'/download/{filename}'})
        else:
            return jsonify({'error': 'Invalid file format. Please upload an Excel file with .xlsx extension.'})
    except Exception as e:
        logging.error(f"Error processing upload: {e}")
        return jsonify({'error': 'An error occurred while processing the file. Please try again.'})

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True, port=8080)
