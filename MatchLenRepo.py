def get_movie_details_from_nz_website(movie_name, director_name, retries=1):
    base_url = "https://www.classificationoffice.govt.nz/find-a-rating/?search="
    search_url = base_url + movie_name.replace(" ", "+")

    for attempt in range(retries):
        try:
            browser = start_chrome(search_url, headless=True)
            time.sleep(5)  # Wait for the page to load
            page_source = browser.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.find_all('div', {'data-listing': ''})

            # Track matches
            exact_matches = []
            similar_matches = []
            for listing in listings:
                title_tag = listing.find('h3', class_='h2')
                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                if title.lower() == movie_name.lower():
                    exact_matches.append(title)
                elif movie_name.lower() in title.lower() or title.lower() in movie_name.lower():
                    similar_matches.append(title)

            browser.quit()

            # Handle results
            if len(exact_matches) == 1:
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
                    'search_result_comment': "found as direct search",
                    'link': search_url
                }
            elif len(similar_matches) > 1:  # Multiple similar matches
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
                    'search_result_comment': "multiple search results found - need manual verification",
                    'link': search_url
                }
            else:  # No matches
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
                    'search_result_comment': "no data found",
                    'link': search_url
                }

        except Exception as e:
            logging.error(f"Error fetching details for {movie_name} from website (attempt {attempt+1}/{retries}): {e}")
            time.sleep(5)

    return None
