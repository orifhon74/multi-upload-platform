from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
import logging

# def upload_to_youtube(video_file, title, description, category, tags):
#     try:
#         youtube = build('youtube', 'v3', developerKey='AIzaSyB2guaXg1OUb2Efg1iMrV3KqKGs3buoxf8')
#
#         body = {
#             'snippet': {
#                 'title': title,
#                 'description': description,
#                 'tags': tags,
#                 'categoryId': category
#             },
#             'status': {
#                 'privacyStatus': 'public'
#             }
#         }
#
#         media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
#         request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
#         response = request.execute()
#
#         logging.info('Video uploaded. Video ID: %s', response['id'])
#         return response['id']
#     except HttpError as e:
#         logging.error('An HTTP error %d occurred:\n%s', e.resp.status, e.content)
#         raise e


def upload_to_youtube(video_file, title, description, category, tags, credentials):
    youtube = build('youtube', 'v3', credentials=credentials)

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category
        },
        'status': {
            'privacyStatus': 'public',
            'madeForKids': False
        }
    }

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
    response = request.execute()

    logging.info('Video uploaded. Video ID: %s', response['id'])
    return response['id']

# AIzaSyB2guaXg1OUb2Efg1iMrV3KqKGs3buoxf8