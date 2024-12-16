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

# Function to perform a strict search with movie_name and director_name
def search_movie_exact_title(movie_name, director_name):
    # Search for the exact movie title
    search_url = f"https://www.examplemoviewebsite.com/search?q={movie_name}"
    search_results = get_search_results(search_url)  # Retrieve search results

    # Match director name
    for result in search_results:
        if director_name.lower() in result['director'].lower():  # Match director
            if result['title'] == movie_name:  # Strict title match
                return result
    
    # Handle case for year in title
    movie_name_without_year = remove_year_from_title(movie_name)
    search_url_without_year = f"https://www.examplemoviewebsite.com/search?q={movie_name_without_year}"
    search_results_without_year = get_search_results(search_url_without_year)

    # Check again with title without year
    for result in search_results_without_year:
        if director_name.lower() in result['director'].lower():
            if result['title'] == movie_name_without_year:
                return result

    return None  # No match found

# Function to remove year from title (e.g., "2002")
def remove_year_from_title(title):
    return re.sub(r' \(\d{4}\)$', '', title)

# Function to get search results (simulated)
def get_search_results(search_url):
    response = requests.get(search_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    search_results = []
    for item in soup.find_all('div', class_='search-result'):
        title = item.find('h3').get_text()
        director = item.find('p', class_='director').get_text()
        search_results.append({'title': title, 'director': director})
    
    return search_results

# Function to get movie details from the website
def get_movie_details_from_website(movie_name, director_name, retries=1):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_url = base_url + movie_name.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)
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
            logging.error(f"Error fetching details for {movie_name} (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)
    return None

# Function to get movie details from NZ website
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

# Flask route for file upload and processing
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

            # Results list
            results = []
            for movie_name, director_name in zip(movie_names, director_names):
                # Clean movie name and perform search
                clean_name = clean_movie_name(movie_name)
                result = search_movie_exact_title(clean_name, director_name)

                if result:
                    results.append({
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': result['classification'],
                        'release_year': result['release_year'],
                        'run_time': result['run_time'],
                        'label_issued_by': result['label_issued_by'],
                        'label_issued_on': result['label_issued_on'],
                        'MR': result['MR'],
                        'CD': result['CD'],
                        'link': result['link']
                    })
                else:
                    results.append({
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'MR': 'N/A',
                        'CD': 'N/A',
                        'link': 'N/A'
                    })

            results_df = pd.DataFrame(results)
            filename = 'movie_ratings.xlsx'
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
