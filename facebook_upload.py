import logging
import requests


def upload_to_facebook(video_file_path, title, description, access_token, page_id):
    url = f'https://graph.facebook.com/v12.0/{page_id}/videos'
    files = {
        'file': open(video_file_path, 'rb')
    }
    data = {
        'title': title,
        'description': description,
        'access_token': access_token
    }
    response = requests.post(url, files=files, data=data)
    if response.status_code == 200:
        logging.info('Video uploaded to Facebook. Response: %s', response.json())
        return response.json()
    else:
        logging.error('Failed to upload video to Facebook. Response: %s', response.json())
        return None

# @app.route('/upload_facebook', methods=['GET', 'POST'])
# def upload_facebook():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
#
#     if request.method == 'POST':
#         video_file = request.files['video_file']
#         title = request.form['title']
#         description = request.form['description']
#         access_token = request.form['access_token']
#         page_id = request.form['page_id']
#
#         if video_file:
#             video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_file.filename)
#             video_file.save(video_path)
#
#             upload_to_facebook(video_path, title, description, access_token, page_id)
#             flash('Video uploaded to Facebook!')
#             return redirect(url_for('dashboard'))
#
#     return render_template('upload_facebook.html')