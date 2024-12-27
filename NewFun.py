def get_movie_details_from_website(movie_name, director_name, retries=1):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_url = base_url + movie_name.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)  # Wait for page to load
            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.find_all('div', {'data-listing': ''})

            exact_matches = []
            similar_matches = []

            for listing in listings:
                title_tag = listing.find('h3', class_='h2')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                director_tag = listing.find('p', class_='small')
                if not director_tag:
                    continue
                director_text = director_tag.get_text(strip=True)

                if title.lower() == movie_name.lower() and director_name.lower() in director_text.lower():
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

                    release_year = director_text.split(',')[0].strip() if ',' in director_text else 'N/A'
                    exact_matches.append({
                        'movie_name': movie_name,
                        'director_name': director_name,
                        'classification': classification,
                        'release_year': release_year,
                        'run_time': run_time,
                        'label_issued_by': label_issued_by,
                        'label_issued_on': label_issued_on,
                        'MR': mr_text,
                        'CD': classification,
                        'link': search_url,
                        'comment': 'found as direct search'
                    })

                elif movie_name.lower() in title.lower():
                    similar_matches.append(title)

            browser.quit()

            # Return exact match if found
            if exact_matches:
                return exact_matches[0]

            # Handle multiple similar matches
            if similar_matches:
                return {
                    'movie_name': movie_name,
                    'director_name': director_name,
                    'classification': 'N/A',
                    'release_year': 'N/A',
                    'run_time': 'N/A',
                    'label_issued_by': 'N/A',
                    'label_issued_on': 'N/A',
                    'MR': 'N/A',
                    'CD': 'N/A',
                    'link': search_url,
                    'comment': 'multiple search result found- need manual verification'
                }

            # No matches
            return {
                'movie_name': movie_name,
                'director_name': director_name,
                'classification': 'N/A',
                'release_year': 'N/A',
                'run_time': 'N/A',
                'label_issued_by': 'N/A',
                'label_issued_on': 'N/A',
                'MR': 'N/A',
                'CD': 'N/A',
                'link': search_url,
                'comment': 'no data found'
            }

        except Exception as e:
            logging.error(f"Error fetching details for {movie_name} from website (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(5)  # Retry delay

    return None


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
                        'CD': 'N/A',
                        'comment': 'no data found'
                    })
                    continue

                details = get_movie_details_from_website(movie_name, director_name)
                if not details:
                    details = get_movie_details_from_nz_website(movie_name, director_name)

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
                        'comment': 'no data found'
                    }

                results.append(details)

            results_df = pd.DataFrame(results)
            filename = 'movie_ratings_with_comments.xlsx'
            results_df.to_excel(filename, index=False)

            return jsonify({'download_url': f'/download/{filename}'})
        else:
            return jsonify({'error': 'Invalid file format. Please upload an Excel file with .xlsx extension.'})
    except Exception as e:
        logging.error(f"Error processing upload: {e}")
        return jsonify({'error': 'An error occurred while processing the file. Please try again.'})
