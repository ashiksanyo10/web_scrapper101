from difflib import SequenceMatcher

def is_similar(a, b, threshold=0.9):
    """Check if two strings are similar above a certain threshold."""
    return SequenceMatcher(None, a, b).ratio() > threshold

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

            ambiguous_links = []
            for listing in listings:
                title_tag = listing.find('h3', class_='h2')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                director_tag = listing.find('p', class_='small')
                if not director_tag:
                    continue
                director_text = director_tag.get_text(strip=True)

                # Matching logic: Exact match, Partial match, Similarity check
                if movie_name.lower() == title.lower():
                    # Exact match
                    is_exact_match = True
                elif movie_name.lower() in title.lower():
                    # Partial match
                    is_exact_match = False
                elif is_similar(movie_name, title, threshold=0.85):
                    # Similarity match
                    is_exact_match = False
                else:
                    continue

                # Fetch details
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

                ambiguous_links.append(search_url)

                # Return results if unambiguous
                if len(ambiguous_links) == 1:
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
                        'link': search_url,
                        'is_exact_match': is_exact_match
                    }

            # Handle ambiguity
            if len(ambiguous_links) > 1:
                logging.warning(f"Ambiguous results for '{movie_name}'. Consider manual verification.")
                browser.quit()
                return {
                    'movie_name': movie_name,
                    'director_name': director_name,
                    'classification': 'N/A',
                    'release_year': 'N/A',
                    'run_time': 'N/A',
                    'label_issued_by': 'N/A',
                    'label_issued_on': 'N/A',
                    'MR': 'N/A',
                    'CD': f"Ambiguous results for '{movie_name}'. Consider manual verification",
                    'link': ", ".join(ambiguous_links)
                }

            browser.quit()
        except Exception as e:
            logging.error(f"Error fetching details for {movie_name} from website 1 (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)  # Wait before retry
    return None
