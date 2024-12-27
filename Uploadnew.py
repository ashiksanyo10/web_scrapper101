@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        try:
            # Read the uploaded Excel file
            df = pd.read_excel(file)

            # Ensure required columns exist
            if 'Movie_name' not in df.columns or 'Director_name' not in df.columns:
                return jsonify({"error": "Invalid file format. Columns 'Movie_name' and 'Director_name' are required."}), 400

            results = []
            for index, row in df.iterrows():
                movie_name = row['Movie_name']
                director_name = row['Director_name']
                details = get_movie_details_from_nz_website(movie_name, director_name, retries=2)

                if details is None:
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
                        'search_result_comment': 'Error fetching details - please retry',
                        'link': 'N/A'
                    }

                results.append(details)

            # Convert results to DataFrame and save as Excel
            output_df = pd.DataFrame(results)
            output_filename = f"{datetime.datetime.now().strftime('%Y-%m-%d')}-NewWebsite.xlsx"
            output_path = os.path.join('outputs', output_filename)
            output_df.to_excel(output_path, index=False)

            # Provide file for download
            return send_file(output_path, as_attachment=True)

        except Exception as e:
            logging.error(f"Error processing file upload: {e}")
            return jsonify({"error": "An error occurred while processing the file."}), 500
