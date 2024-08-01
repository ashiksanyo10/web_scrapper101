def get_movie_details_from_website(season_title, movie_name, director_name, retries=1):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_url = base_url + season_title.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)  # Wait for the page to load
            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.find_all('div', {'data-listing': ''})

            for listing in listings:
                title_tag = listing.find('h3', class_='h2')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                # Check if the Movie_name (alternate title) is in the title
                if movie_name.lower() in title.lower():
                    # Extract classification
                    classification_tag = listing.find('p', class_='large mb-2')
                    classification = classification_tag.get_text(strip=True) if classification_tag else 'N/A'

                    # Extract MR (e.g., "Parental guidance recommended for younger viewers")
                    mr_tag = listing.find('p', class_='large')
                    mr_text = mr_tag.get_text(strip=True) if mr_tag else 'N/A'

                    # Extract the release year, runtime, and label
                    table = listing.find('table', class_='rating-result-table')
                    run_time = 'N/A'
                    label_issued_by = 'N/A'
                    if table:
                        lines = table.get_text(separator="\n", strip=True).split('\n')
                        for i, line in enumerate(lines):
                            if 'Running time:' in line:
                                run_time = lines[i + 1].strip()
                            elif 'Label issued by:' in line:
                                label_issued_by = lines[i + 1].strip()

                    director_tag = listing.find('p', class_='small')
                    if director_tag:
                        director_text = director_tag.get_text(strip=True)
                        parts = director_text.split(',')
                        release_year = parts[0].strip() if len(parts) > 1 else 'N/A'
                    else:
                        release_year = 'N/A'

                    browser.quit()
                    return {
                        'season_title': season_title,
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': classification,
                        'release_year': release_year,
                        'run_time': run_time,
                        'label_issued_by': label_issued_by,
                        'MR': mr_text,  # Additional field for MR
                        'CD': classification  # Additional field for CD
                    }
            browser.quit()
        except Exception as e:
            logging.error(f"Error fetching details for {season_title} from website 1 (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)  # Wait before retrying
    return None

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            # Process the Excel file
            df = pd.read_excel(file)
            season_titles = df['Season_title'].tolist()
            movie_names = df['Movie_name'].tolist()
            director_names = df['Director_name'].tolist()

            results = []
            for season_title, movie_name, director_name in zip(season_titles, movie_names, director_names):
                if not is_valid_director_name(director_name):
                    results.append({
                        'season_title': season_title,
                        'movie_name': movie_name,
                        'director_name': 'No Director Details',
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A'
                    })
                    continue

                # Attempt to get details from the first website
                details = get_movie_details_from_website(season_title, movie_name, director_name)
                if not details:
                    # Attempt to get details from the NZ website
                    details = get_movie_details_from_nz_website(season_title, movie_name, director_name)

                # If details are still not found, use default values
                if not details:
                    details = {
                        'season_title': season_title,
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A'
                    }

                results.append(details)

            # Save the combined results to an Excel file
            results_df = pd.DataFrame(results)
            filename = 'movie_ratings.xlsx'
            results_df.to_excel(filename, index=False)

            return jsonify({'download_url': f'/download/{filename}'})
        else:
            return jsonify({'error': 'Invalid file format, must be .xlsx'}), 400
    except Exception as e:
        logging.error(f"Error processing file: {e}")
        return jsonify({'error': str(e)}), 500


