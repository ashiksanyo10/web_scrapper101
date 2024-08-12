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
            episode_names = df['Episode_name'].tolist()
            director_names = df['Director_name'].tolist()

            # Mapping MR statements to codes (remains unchanged)
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

            results = []
            for season_name, season_number, episode_number, episode_name, director_name in zip(season_names, season_numbers, episode_numbers, episode_names, director_names):
                
                # Handle missing Season_name or Director_name
                if not season_name:
                    results.append({
                        'season_name': 'No Season Name',
                        'episode_name': episode_name,
                        'director_name': director_name or 'No Director Details',
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'MR': 'N/A',
                        'CD': 'N/A'
                    })
                    continue

                if not is_valid_director_name(director_name):
                    results.append({
                        'season_name': season_name,
                        'episode_name': episode_name,
                        'director_name': 'Invalid Input',
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'MR': 'N/A',
                        'CD': 'N/A'
                    })
                    continue

                # Create search query with Season_name, Season_number, Episode_number
                search_query = f"{season_name} Season {season_number} Episode {episode_number}"

                # Attempt to get details from the first website
                details = get_series_details_from_website(search_query, episode_name, director_name)
                if not details:
                    # Attempt to get details from the NZ website
                    details = get_series_details_from_nz_website(search_query, episode_name, director_name)

                # If details are still not found, use default values
                if not details:
                    details = {
                        'season_name': season_name,
                        'episode_name': episode_name,
                        'director_name': director_name,
                        'classification': 'N/A',
                        'release_year': 'N/A',
                        'run_time': 'N/A',
                        'label_issued_by': 'N/A',
                        'label_issued_on': 'N/A',
                        'MR': 'N/A',
                        'CD': 'N/A'
                    }
                
                # Map MR statement to code
                mr_statement = details.get('MR', 'N/A')
                details['MR'] = mr_mapping.get(mr_statement, mr_statement)  # Convert MR to code, if possible

                results.append(details)

            # Save the combined results to an Excel file
            results_df = pd.DataFrame(results)
            filename = 'series_ratings.xlsx'
            results_df.to_excel(filename, index=False)

            return jsonify({'download_url': f'/download/{filename}'})
        else:
            return jsonify({'error': 'Invalid file format. Please upload an Excel file with .xlsx extension.'})
    except Exception as e:
        logging.error(f"Error processing upload: {e}")
        return jsonify({'error': 'An error occurred while processing the file. Please try again.'})
