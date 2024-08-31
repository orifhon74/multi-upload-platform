# @app.route('/upload_telegram', methods=['GET', 'POST'])
# def upload_telegram():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
#
#     if request.method == 'POST':
#         video_file = request.files['video_file']
#         caption = request.form['caption']
#
#         if video_file:
#             video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_file.filename)
#             video_file.save(video_path)
#
#             upload_to_telegram(video_path, caption)
#             flash('Video uploaded to Telegram!')
#             return redirect(url_for('dashboard'))
#
#     return render_template('upload_telegram.html')
#
# def upload_to_telegram(video_file_path, caption):
#     url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo'
#     files = {
#         'video': open(video_file_path, 'rb')
#     }
#     data = {
#         'chat_id': TELEGRAM_CHAT_ID,
#         'caption': caption
#     }
#     response = requests.post(url, files=files, data=data, verify=False)  # Disable SSL verification
#     logging.info('Sending video to Telegram. URL: %s', url)
#     logging.info('Files: %s', files)
#     logging.info('Data: %s', data)
#     if response.status_code == 200:
#         logging.info('Video uploaded to Telegram. Response: %s', response.json())
#         return response.json()
#     else:
#         logging.error('Failed to upload video to Telegram. Status code: %d', response.status_code)
#         logging.error('Response: %s', response.text)
#         return None