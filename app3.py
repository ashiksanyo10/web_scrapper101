import pandas as pd
from bs4 import BeautifulSoup
from helium import start_chrome, write, click, S, find_all, get_driver
import time
from datetime import datetime
from flask import Flask, request, send_file, jsonify
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

# File paths
output_file_path = 'rating.xlsx'

def wait_for_element(selector, timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if selector.exists():
            return True
        time.sleep(0.5)
    return False

def get_movie_details(movie_name, director_name, retries=3):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_url = base_url + movie_name.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)

            time.sleep(5)  # Wait for the page to load

            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')

            listings = soup.find_all('div', {'data-listing': ''})

            details = {
                'movie_name': movie_name,
                'director_name': director_name,
                'classification': 'N/A',
                'release_year': 'N/A',
                'run_time': 'N/A',
                'label_issued_by': 'N/A'
            }

            found = False

            for listing in listings:
                title_tag = listing.find('h3', class_='h2')
                if title_tag is None:
                    continue  # Skip this listing if the title tag is not found

                title = title_tag.get_text(strip=True)

                director_tag = listing.find('p', class_='small')
                if director_tag is None:
                    continue  # Skip this listing if the director tag is not found

                director_text = director_tag.get_text(strip=True)
                if director_name in director_text:
                    found = True

                    # Extract classification
                    classification_tag = listing.find('p', class_='large mb-2')
                    if classification_tag:
                        details['classification'] = classification_tag.get_text(strip=True)
                    else:
                        logging.warning(f"Classification tag not found for movie: {movie_name}")

                    # Extract the release year and runtime
                    table = listing.find('table', class_='rating-result-table')
                    if table:
                        lines = table.get_text(separator="\n", strip=True).split('\n')
                        for i, line in enumerate(lines):
                            if 'Running time:' in line:
                                details['run_time'] = lines[i + 1].strip()
                            elif 'Label issued by:' in line:
                                details['label_issued_by'] = lines[i + 1].strip()

                    # Extract release year from the director text
                    parts = director_text.split(',')
                    if len(parts) > 1:
                        details['release_year'] = parts[0].strip()

                    break

            if not found:
                details = {
                    'movie_name': movie_name,
                    'director_name': director_name,
                    'classification': 'N/A',
                    'release_year': 'N/A',
                    'run_time': 'N/A',
                    'label_issued_by': 'N/A'
                }

            browser.quit()
            return details

        except Exception as e:
            logging.error(f"Error fetching details for {movie_name} (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)  # Wait before retrying
    return None

def nz_title_check(movie_names, retries=3):
    browser = start_chrome('https://www.fvlb.org.nz/', headless=True)

    all_movies_details = []

    for i, movie_name in enumerate(movie_names):
        if i > 0 and i % 10 == 0:
            logging.debug("1 minute of batch break - please wait")
            time.sleep(60)  # 1 minute delay after every batch of 10 movies

        for attempt in range(retries):
            try:
                search_title_input = S("#fvlb-input")
                exact_match_checkbox = S("#ExactSearch")
                search_button = S(".submitBtn")

                write(movie_name, into=search_title_input)
                click(exact_match_checkbox)
                click(search_button)

                if not wait_for_element(S('.result-title')):
                    all_movies_details.append({
                        'title_name': movie_name,
                        'dir_name': 'N/A',
                        'classification': 'N/A',
                        'runtime': 'N/A'
                    })
                    break

                time.sleep(3)  # 3 seconds delay between each movie search

                movie_links = find_all(S('.result-title'))
                exact_match_found = False

                for link in movie_links:
                    if link.web_element.text.strip() == movie_name:
                        click(link)
                        exact_match_found = True
                        break

                if not exact_match_found:
                    write('', into=search_title_input)
                    click(search_button)

                    if not wait_for_element(S('.result-title')):
                        all_movies_details.append({
                            'title_name': movie_name,
                            'dir_name': 'N/A',
                            'classification': 'N/A',
                            'runtime': 'N/A'
                        })
                        break

                    time.sleep(3)  # 3 seconds delay between each movie search

                    movie_links = find_all(S('.result-title'))

                    for link in movie_links:
                        if movie_name.lower() in link.web_element.text.strip().lower():
                            click(link)
                            exact_match_found = True
                            break

                if not exact_match_found:
                    all_movies_details.append({
                        'title_name': movie_name,
                        'dir_name': 'N/A',
                        'classification': 'N/A',
                        'runtime': 'N/A'
                    })
                    break

                if not wait_for_element(S('h1')):
                    all_movies_details.append({
                        'title_name': movie_name,
                        'dir_name': 'N/A',
                        'classification': 'N/A',
                        'runtime': 'N/A'
                    })
                    break

                time.sleep(1)

                page_source = get_driver().page_source
                soup = BeautifulSoup(page_source, 'html.parser')

                movie_details = {}
                title_element = soup.find('h1')
                movie_details['title_name'] = title_element.text.strip() if title_element else 'N/A'

                director_element = soup.find('div', class_='film-director')
                movie_details['dir_name'] = director_element.text.strip().replace('Directed by ', '') if director_element else 'N/A'

                classification_element = soup.find('div', class_='film-classification')
                movie_details['classification'] = classification_element.text.strip() if classification_element else 'N/A'

                runtime_element = soup.find_all('div', class_='film-approved')[1]
                runtime = runtime_element.text.strip().replace('This title has a runtime of ', '').replace(' minutes.', '')
                movie_details['runtime'] = runtime if runtime else 'N/A'

                all_movies_details.append(movie_details)

                browser.back()
                break

            except Exception as e:
                logging.error(f"Error fetching NZ title check for {movie_name} (attempt {attempt+1}/{retries}): {e}")
                time.sleep(5)  # Wait before retrying

    get_driver().quit()

    return all_movies_details

@app.route('/')
def index():
    return send_file('index2.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            # Save the uploaded file temporarily
            temp_file_path = 'temp_upload.xlsx'
            file.save(temp_file_path)
            
            # Process the Excel file
            df = pd.read_excel(temp_file_path)
            movie_names = df['Movie_name'].tolist()
            director_names = df['Director_name'].tolist()

            # Process with scrapper 1
            results = []
            for movie_name, director_name in zip(movie_names, director_names):
                movie_details = get_movie_details(movie_name, director_name)
                if movie_details:
                    results.append(movie_details)
                else:
                    results.append({
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A'
                    })

            results_df = pd.DataFrame(results)
            not_found = results_df[results_df['classification'] == 'N/A']
            not_found_list = not_found['movie_name'].tolist()

            # Process with scrapper 2 for those not found in scrapper 1
            additional_results = nz_title_check(not_found_list)

            # Append additional results to the main results
            for i, row in not_found.iterrows():
                additional_result = next((item for item in additional_results if item['title_name'] == row['movie_name']), None)
                if additional_result:
                    results_df.loc[i, 'classification'] = additional_result['classification']
                    results_df.loc[i, 'run_time'] = additional_result['runtime']
                    results_df.loc[i, 'label_issued_by'] = 'N/A'  # Placeholder for scrapper 2, modify as needed

            # Save the combined results to the original file
            results_df.to_excel(temp_file_path, index=False)

            # Provide the updated file for download
            logging.info(f"Processed {len(movie_names)} movies. Found details for {len(results_df) - len(not_found)} movies.")
            return jsonify({'download_url': f'/download/{temp_file_path}'})
        else:
            return jsonify({'error': 'Invalid file format, must be .xlsx'}), 400
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return jsonify({'error': str(e)}), 500   
    
@app.route('/download/<filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
