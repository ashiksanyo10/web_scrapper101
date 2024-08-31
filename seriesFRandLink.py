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

# File paths
output_file_path = 'series_ratings.xlsx'

def wait_for_element(selector, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if selector.exists():
            return True
        time.sleep(0.5)
    return False

def is_valid_director_name(name):
    return bool(name) and re.match("^[a-zA-Z ]+$", name)

def get_series_details_from_classificationoffice(season_name, season_number, episode_number, director_name, retries=1):
    # Construct search query
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_query = f"{season_name}, Season {season_number}, Episode {episode_number}"
    search_url = base_url + search_query.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)  # Wait for the page to load
            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Check for "Featured Result" in the tag
            featured_results_tag = soup.find('h2', class_='h6 mb-10')
            if featured_results_tag and "Featured Result" in featured_results_tag.text.strip():
                # "Featured Result" is found, set the status and return with details
                classification = release_year = run_time = label_issued_by = label_issued_on = 'N/A'

                # Extract all details for "Featured Results"
                featured_result_details = soup.find_all('div', {'data-listing': ''})
                if featured_result_details:
                    # Extract data from the first "Featured Result"
                    listing = featured_result_details[0]  # Take the first listing

                    classification_tag = listing.find('p', class_='large mb-2')
                    classification = classification_tag.get_text(strip=True) if classification_tag else 'N/A'

                    table = listing.find('table', class_='rating-result-table')
                    if table:
                        lines = table.get_text(separator="\n", strip=True).split('\n')
                        for i, line in enumerate(lines):
                            if 'Running time:' in line:
                                run_time = lines[i + 1].strip()
                            elif 'Label issued by:' in line:
                                label_issued_by = lines[i + 1].strip()
                            elif 'Label issued on:' in line:
                                label_issued_on = lines[i + 1].strip()

                    # Return result with "Found as Featured Results"
                    browser.quit()
                    return {
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'director_name': director_name,
                        'classification': classification,
                        'release_year': release_year,
                        'run_time': run_time,
                        'label_issued_by': label_issued_by,
                        'label_issued_on': label_issued_on,
                        'status': 'Found as Featured Results',
                        'link': search_url
                    }

            # If "Featured Result" is not found, proceed with normal search logic
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

                # Match director's name if "Featured Results" is not found
                if director_name.lower() in director_text.lower():
                    classification_tag = listing.find('p', class_='large mb-2')
                    classification = classification_tag.get_text(strip=True) if classification_tag else 'N/A'

                    mr_tag = listing.find('p', class_='large')
                    mr_text = mr_tag.get_text(strip=True) if mr_tag else 'N/A'

                    # Extract other details
                    table = listing.find('table', class_='rating-result-table')
                    run_time, label_issued_by, label_issued_on = 'N/A', 'N/A', 'N/A'
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

                    browser.quit()
                    return {
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'director_name': director_name,
                        'classification': classification,
                        'release_year': release_year,
                        'run_time': run_time,
                        'label_issued_by': label_issued_by,
                        'label_issued_on': label_issued_on,
                        'status': 'Found as Exact Match',
                        'link': search_url
                    }
            browser.quit()
        except Exception as e:
            logging.error(f"Error fetching details for {season_name}, Season {season_number}, Episode {episode_number} from website (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)
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

            # Ensure necessary columns are treated correctly
            df['Season_name'] = df['Season_name'].astype(str)
            df['Season_number'] = df['Season_number'].astype(str)
            df['Episode_number'] = df['Episode_number'].astype(str)
            df['Episode_name'] = df['Episode_name'].astype(str)
            df['Director_name'] = df['Director_name'].astype(str)

            season_names = df['Season_name'].tolist()
            season_numbers = df['Season_number'].tolist()
            episode_numbers = df['Episode_number'].tolist()
            episode_names = df['Episode_name'].tolist()
            director_names = df['Director_name'].tolist()

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
                # Other mappings...
            }

            results = []
            for season_name, season_number, episode_number, episode_name, director_name in zip(season_names, season_numbers, episode_numbers, episode_names, director_names):
                if not season_name or season_name.strip() == '':
                    results.append({
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'episode_name': episode_name,
                        'director_name': director_name,
                        'error': 'No Season name',
                        'link': 'N/A'
                    })
                    continue

                if not director_name or director_name.strip() == '':
                    results.append({
                        'season_name': season_name,
                        'season_number': season_number,
                        'episode_number': episode_number,
                        'episode_name': episode_name,
                        'director_name': director_name,
                        'error': 'No Director name',
                        'link': 'N/A'
                    })
                    continue

                # Construct search query URL
                base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
                search_query = f"{season_name}, Season {season_number}, Episode {episode_number}"
                search_url = base_url + search_query.replace(" ", "+")

                # Fetch series details
                details = get_series_details_from_classificationoffice(season_name, season_number, episode_number, director_name)

                if not details:
                    # Handle case if details are not found
                    logging.info(f"No matching details found for {season_name}, Season {season_number}, Episode {episode_number}, Director {director_name}")
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
                        'status': 'Not Found',
                        'link': search_url  # Now search_url is defined and accessible
                    }

                details['MR'] = mr_mapping.get(details.get('classification', ''), 'N/A')
                details['CD'] = mr_mapping.get(details.get('classification', ''), 'N/A')

                results.append(details)

            # Save results to an Excel file
            results_df = pd.DataFrame(results)
            filename = 'series_ratings.xlsx'
            results_df.to_excel(filename, index=False)

            return jsonify({'download_url': f'/download/{filename}'})
        else:
            return jsonify({'error': 'Invalid file format. Please upload an Excel (.xlsx) file.'}), 400
    except Exception as e:
        logging.error(f"Error processing file upload: {e}")
        return jsonify({'error': 'An error occurred while processing the file.'}), 500


@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(filename, as_attachment=True)
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        return jsonify({'error': 'File not found or error in downloading the file.'}), 404

if __name__ == '__main__':
    app.run(debug=True,port =8080) 
