import os
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
import pickle
import json
import datetime
import argparse
from tabulate import tabulate
import time

class YouTubeAutomation:
    def __init__(self):
        self.youtube = None
        self.client_secrets_file = "client_secret.json"
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.scopes = ["https://www.googleapis.com/auth/youtube.upload",
                      "https://www.googleapis.com/auth/youtube",
                      "https://www.googleapis.com/auth/youtube.force-ssl"]
        self.token_file = "token.pickle"
        
    def authenticate(self):
        """Authenticate with YouTube API."""
        credentials = None
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                credentials = pickle.load(token)
        
        # If credentials don't exist or are invalid, get new ones
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes)
                credentials = flow.run_local_server(port=8080)
            
            # Save credentials for future use
            with open(self.token_file, 'wb') as token:
                pickle.dump(credentials, token)
        
        # Create YouTube API client
        self.youtube = googleapiclient.discovery.build(
            self.api_service_name, self.api_version, credentials=credentials)
        
        print("Authentication successful!")
        return True
    
    def upload_video(self, file_path, title, description, tags=None, category_id="22", 
                    privacy_status="private", publish_at=None):
        """Upload a video to YouTube."""
        if not self.youtube:
            if not self.authenticate():
                return False
        
        tags = tags or []
        
        # Prepare the request body
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": privacy_status,
            }
        }
        
        # Add scheduled publishing if provided
        if publish_at and privacy_status == "private":
            body["status"]["publishAt"] = publish_at.isoformat()
        
        # Create MediaFileUpload object for the file
        media = MediaFileUpload(file_path, resumable=True)
        
        # Execute the request to upload the video
        try:
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            
            print("Uploading video...")
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Uploaded {int(status.progress() * 100)}%")
            
            print(f"Upload complete! Video ID: {response['id']}")
            return response['id']
        
        except googleapiclient.errors.HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred: {e.content}")
            return None
    
    def list_my_videos(self, max_results=50):
        """List videos in your channel."""
        if not self.youtube:
            if not self.authenticate():
                return False
        
        try:
            request = self.youtube.videos().list(
                part="snippet,statistics,status",
                mine=True,
                maxResults=max_results
            )
            response = request.execute()
            
            # Format the results for display
            video_data = []
            for item in response.get("items", []):
                video_data.append([
                    item["id"],
                    item["snippet"]["title"],
                    item["statistics"].get("viewCount", "0"),
                    item["statistics"].get("likeCount", "0"),
                    item["status"]["privacyStatus"]
                ])
            
            headers = ["Video ID", "Title", "Views", "Likes", "Privacy Status"]
            print(tabulate(video_data, headers=headers))
            
            return response.get("items", [])
        
        except googleapiclient.errors.HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred: {e.content}")
            return None
    
    def update_video(self, video_id, title=None, description=None, tags=None, 
                    privacy_status=None, category_id=None):
        """Update video metadata."""
        if not self.youtube:
            if not self.authenticate():
                return False
        
        # Get current video data
        try:
            video_response = self.youtube.videos().list(
                part="snippet,status",
                id=video_id
            ).execute()
            
            if not video_response.get("items"):
                print(f"Video with ID {video_id} not found.")
                return False
            
            # Current data
            video_snippet = video_response["items"][0]["snippet"]
            video_status = video_response["items"][0]["status"]
            
            # Prepare update data
            update_body = {
                "id": video_id,
                "snippet": {
                    "title": title or video_snippet["title"],
                    "description": description or video_snippet["description"],
                    "tags": tags or video_snippet.get("tags", []),
                    "categoryId": category_id or video_snippet["categoryId"]
                },
                "status": {
                    "privacyStatus": privacy_status or video_status["privacyStatus"]
                }
            }
            
            # Execute update
            update_response = self.youtube.videos().update(
                part="snippet,status",
                body=update_body
            ).execute()
            
            print(f"Video {video_id} updated successfully!")
            return update_response
            
        except googleapiclient.errors.HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred: {e.content}")
            return None
    
    def delete_video(self, video_id):
        """Delete a video from your channel."""
        if not self.youtube:
            if not self.authenticate():
                return False
        
        try:
            self.youtube.videos().delete(id=video_id).execute()
            print(f"Video {video_id} deleted successfully!")
            return True
            
        except googleapiclient.errors.HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred: {e.content}")
            return False
    
    def schedule_video(self, video_id, publish_time):
        """Schedule a private video to be published at a specific time."""
        if not self.youtube:
            if not self.authenticate():
                return False
        
        try:
            # Format datetime if string
            if isinstance(publish_time, str):
                publish_time = datetime.datetime.fromisoformat(publish_time)
            
            # Prepare the update body
            update_body = {
                "id": video_id,
                "status": {
                    "privacyStatus": "private",
                    "publishAt": publish_time.isoformat()
                }
            }
            
            # Execute update
            update_response = self.youtube.videos().update(
                part="status",
                body=update_body
            ).execute()
            
            print(f"Video {video_id} scheduled for publishing at {publish_time}!")
            return update_response
            
        except googleapiclient.errors.HttpError as e:
            print(f"An HTTP error {e.resp.status} occurred: {e.content}")
            return None


def main():
    parser = argparse.ArgumentParser(description='YouTube Video Automation Tool')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Upload command
    upload_parser = subparsers.add_parser('upload', help='Upload a video')
    upload_parser.add_argument('file', help='Path to video file')
    upload_parser.add_argument('title', help='Video title')
    upload_parser.add_argument('--description', help='Video description', default='')
    upload_parser.add_argument('--tags', help='Comma-separated tags', default='')
    upload_parser.add_argument('--category', help='Category ID', default='22')
    upload_parser.add_argument('--privacy', choices=['private', 'public', 'unlisted'], 
                              help='Privacy status', default='private')
    upload_parser.add_argument('--schedule', help='Schedule time (ISO format)', default=None)
    
    # List command
    list_parser = subparsers.add_parser('list', help='List your videos')
    list_parser.add_argument('--max', type=int, help='Maximum number of videos', default=50)
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update video metadata')
    update_parser.add_argument('video_id', help='Video ID')
    update_parser.add_argument('--title', help='New title')
    update_parser.add_argument('--description', help='New description')
    update_parser.add_argument('--tags', help='Comma-separated tags')
    update_parser.add_argument('--privacy', choices=['private', 'public', 'unlisted'], 
                              help='Privacy status')
    update_parser.add_argument('--category', help='Category ID')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a video')
    delete_parser.add_argument('video_id', help='Video ID')
    
    # Schedule command
    schedule_parser = subparsers.add_parser('schedule', help='Schedule a video')
    schedule_parser.add_argument('video_id', help='Video ID')
    schedule_parser.add_argument('time', help='Publish time (ISO format)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Initialize YouTube automation
    yt = YouTubeAutomation()
    
    # Process commands
    if args.command == 'upload':
        # Parse tags
        tags = [tag.strip() for tag in args.tags.split(',')] if args.tags else []
        
        # Parse schedule time
        schedule_time = None
        if args.schedule:
            schedule_time = datetime.datetime.fromisoformat(args.schedule)
        
        # Upload video
        yt.upload_video(
            args.file, 
            args.title, 
            args.description, 
            tags=tags, 
            category_id=args.category, 
            privacy_status=args.privacy,
            publish_at=schedule_time
        )
    
    elif args.command == 'list':
        yt.list_my_videos(max_results=args.max)
    
    elif args.command == 'update':
        # Parse tags
        tags = None
        if args.tags:
            tags = [tag.strip() for tag in args.tags.split(',')]
        
        # Update video
        yt.update_video(
            args.video_id,
            title=args.title,
            description=args.description,
            tags=tags,
            privacy_status=args.privacy,
            category_id=args.category
        )
    
    elif args.command == 'delete':
        # Confirm deletion
        confirm = input(f"Are you sure you want to delete video {args.video_id}? (y/n): ")
        if confirm.lower() == 'y':
            yt.delete_video(args.video_id)
        else:
            print("Deletion cancelled.")
    
    elif args.command == 'schedule':
        # Schedule video
        schedule_time = datetime.datetime.fromisoformat(args.time)
        yt.schedule_video(args.video_id, schedule_time)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    # Allow OAuth from local machine
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    main()