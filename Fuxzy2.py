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

output_file_path = 'movie_ratings.xlsx'

# MR and CD mappings
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

cd_mapping = {
    "General": "G",
    "Parental Guidance": "PG",
    "Mature": "M",
    "Unrestricted": "R13",
    "R": "R",
    "RP": "RP"
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

def clean_movie_name(movie_name):
    # Remove year-like suffix (e.g., "2002") at the end of the movie name
    return re.sub(r"\s+\d{4}$", "", movie_name)

def get_movie_details_from_website(movie_name, director_name, retries=1):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_url = base_url + movie_name.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)  # Wait
            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
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

                    classification_tag = listing.find('p', class_='large mb-2')
                    classification = classification_tag.get_text(strip=True) if classification_tag else 'N/A'

                    mr_tag = listing.find('p', class_='large')
                    mr_text = mr_tag.get_text(strip=True) if mr_tag else 'N/A'

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

                    browser.quit()
                    return {
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': classification,
                        'release_year': release_year,
                        'run_time': run_time,
                        'label_issued_by': label_issued_by,
                        'label_issued_on': label_issued_on,
                        'MR': mr_text,
                        'CD': classification,
                        'link': search_url
                    }
            browser.quit()
        except Exception as e:
            logging.error(f"Error fetching details for {movie_name} from website 1 (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)  # Wait
    return None

def get_movie_details_from_nz_website(movie_name, director_name, retries=1):
    base_url = "https://www.fvlb.org.nz/"
    browser = start_chrome(base_url, headless=True)

    for attempt in range(retries):
        try:
            search_title_input = S("#fvlb-input")
            exact_match_checkbox = S("#ExactSearch")
            search_button = S(".submitBtn")

            write(movie_name, into=search_title_input)
            click(exact_match_checkbox)
            click(search_button)

            if not wait_for_element(S('.result-title')):
                browser.quit()
                return None

            time.sleep(3)  # Wait

            movie_links = find_all(S('.result-title'))
            for link in movie_links:
                if movie_name.lower() in link.web_element.text.strip().lower():
                    click(link)
                    time.sleep(1)

                    page_source = get_driver().page_source
                    soup = BeautifulSoup(page_source, 'html.parser')

                    title_element = soup.find('h1')
                    title_name = title_element.text.strip() if title_element else 'N/A'

                    director_element = soup.find('div', class_='film-director')
                    dir_name = director_element.text.strip().replace('Directed by ', '') if director_element else 'N/A'

                    if director_name.lower() in dir_name.lower():
                        classification_element = soup.find('div', class_='film-classification')
                        classification = classification_element.text.strip() if classification_element else 'N/A'

                        runtime_element = soup.find_all('div', class_='film-approved')[1]
                        runtime = runtime_element.text.strip().replace('This title has a runtime of ', '').replace(' minutes.', 'N/A')

                        browser.quit()
                        return {
                            'movie_name': movie_name,
                            'director_name': director_name,
                            'classification': classification,
                            'release_year': 'N/A',
                            'run_time': runtime,
                            'label_issued_by': 'N/A',
                            'label_issued_on': 'N/A',
                            'link': 'N/A'
                        }

            browser.back()
        except Exception as e:
            logging.error(f"Error fetching details for {movie_name} from NZ website (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)  # Wait

    get_driver().quit()
    return None

@app.route('/')
def index():
    return send_file('index2.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)
            
            df['Movie_name'] = df['Movie_name'].fillna('').astype(str)
            df['Director_name'] = df['Director_name'].fillna('').astype(str)

            movie_names = df['Movie_name'].tolist()
            director_names = df['Director_name'].tolist()

            results = []
            for movie_name, director_name in zip(movie_names, director_names):
                if not is_valid_director_name(director_name):
                    results.append({
                        'movie_name': movie_name,
                        'director_name': 'No Director Details',
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'MR': 'N/A',
                        'CD': 'N/A'
                    })
                    continue

                clean_name = clean_movie_name(movie_name)
                details = get_movie_details_from_website(clean_name, director_name)

                if not details:
                    details = get_movie_details_from_nz_website(clean_name, director_name)

                if not details:
                    details = {
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'MR': 'N/A',
                        'CD': 'N/A',
                    }
                
                # MR Mapping
                mr_statement = details.get('MR', 'N/A')
                details['MR'] = mr_mapping.get(mr_statement, mr_statement)  

                # CD Mapping
                cd_statement = details.get('CD', 'N/A')
                details['CD'] = cd_mapping.get(cd_statement, cd_statement)

                results.append(details)

            results_df = pd.DataFrame(results)
            filename = 'movie_ratings.xlsx'
            results_df.to_excel(filename, index=False)

            return jsonify({'download_url': f'/download/{filename}'})
        else:
            return jsonify({'error': 'Invalid file format. Please upload an Excel file with .xlsx extension.'})
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return jsonify({'error': 'Failed to process the file.'}), 500


@app.route('/download/<filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
