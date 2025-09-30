#!/usr/bin/env python3
"""
SocialPilot Integration for Nature's Way Video Bot
Posts videos to multiple social media platforms using SocialPilot API
"""

import requests
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

class SocialPilotPoster:
    def __init__(self):
        self.api_key = self._get_api_key()
        self.base_url = "https://api.socialpilot.co/v1"
        # Try different authentication methods
        self.headers_bearer = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.headers_api_key = {
            "Authorization": f"API-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        self.headers_simple = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
    
    def _get_api_key(self) -> str:
        """Get SocialPilot API key from secrets file"""
        try:
            with open('/home/ubuntu/.api_secret_infos/api_secrets.json', 'r') as f:
                secrets = json.load(f)
                return secrets['SOCIALPILOT']['secrets']['API_KEY']
        except Exception as e:
            print(f"Error loading SocialPilot API key: {e}")
            return None
    
    def get_accounts(self) -> List[Dict]:
        """Get all connected social media accounts - try different auth methods"""
        auth_methods = [
            ("Bearer", self.headers_bearer),
            ("API-Key", self.headers_api_key), 
            ("X-API-Key", self.headers_simple)
        ]
        
        for method_name, headers in auth_methods:
            try:
                print(f"Trying {method_name} authentication...")
                response = requests.get(f"{self.base_url}/accounts", headers=headers)
                
                if response.status_code == 200:
                    print(f"✅ {method_name} authentication successful!")
                    self.headers = headers  # Set working headers
                    return response.json().get('data', [])
                else:
                    print(f"❌ {method_name} failed: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"Exception with {method_name}: {e}")
        
        print("All authentication methods failed")
        return []
    
    def upload_media(self, video_path: str) -> Optional[str]:
        """Upload video to SocialPilot and get media ID"""
        try:
            with open(video_path, 'rb') as video_file:
                files = {'media': video_file}
                headers_upload = {"Authorization": f"Bearer {self.api_key}"}
                
                response = requests.post(
                    f"{self.base_url}/media",
                    headers=headers_upload,
                    files=files
                )
                
                if response.status_code == 200:
                    media_data = response.json()
                    return media_data.get('data', {}).get('id')
                else:
                    print(f"Error uploading media: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            print(f"Exception uploading media: {e}")
            return None
    
    def create_post(self, accounts: List[str], text: str, media_id: Optional[str] = None) -> Dict:
        """Create a post on specified social media accounts"""
        try:
            post_data = {
                "accounts": accounts,
                "text": text,
                "schedule_time": None  # Post immediately
            }
            
            if media_id:
                post_data["media"] = [media_id]
            
            response = requests.post(
                f"{self.base_url}/posts",
                headers=self.headers,
                json=post_data
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error creating post: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            print(f"Exception creating post: {e}")
            return {"error": str(e)}
    
    def post_video(self, video_path: str, script_data: Dict, product_data: Dict) -> Dict:
        """Post video to social media platforms using SocialPilot"""
        
        print(f"Starting SocialPilot video posting process...")
        
        # Get connected accounts
        accounts = self.get_accounts()
        if not accounts:
            return {
                "status": "error",
                "message": "No connected social media accounts found in SocialPilot"
            }
        
        print(f"Found {len(accounts)} connected accounts")
        
        # Upload video
        print("Uploading video to SocialPilot...")
        media_id = self.upload_media(video_path)
        if not media_id:
            return {
                "status": "error", 
                "message": "Failed to upload video to SocialPilot"
            }
        
        print(f"Video uploaded successfully. Media ID: {media_id}")
        
        # Create post text
        product_name = product_data.get('product_name', 'Nature\'s Way Product')
        hook = script_data.get('hook', 'Transform your garden naturally!')
        cta = script_data.get('cta', 'Visit natureswaysoil.com for more!')
        
        post_text = f"{hook}\n\n{product_name}\n\n{cta}\n\n#NaturesWay #OrganicGardening #PlantCare #GreenThumb #HealthyPlants"
        
        # Get account IDs for posting (limit to first 3 accounts to avoid spam)
        account_ids = [acc['id'] for acc in accounts[:3]]
        
        print(f"Posting to {len(account_ids)} accounts...")
        
        # Create the post
        post_result = self.create_post(account_ids, post_text, media_id)
        
        if "error" in post_result:
            return {
                "status": "error",
                "message": post_result["error"]
            }
        
        # Format results
        results = []
        post_data = post_result.get('data', {})
        
        for i, account in enumerate(accounts[:3]):
            platform = account.get('type', 'unknown').lower()
            account_name = account.get('name', f'Account_{i+1}')
            
            results.append({
                "platform": platform,
                "account": account_name,
                "status": "posted",
                "post_id": f"sp_{media_id}_{i}",
                "url": f"https://socialpilot.co/posts/{media_id}",  # SocialPilot dashboard URL
                "scheduled_time": datetime.now().isoformat()
            })
        
        return {
            "status": "success",
            "message": f"Video posted to {len(results)} social media accounts",
            "posts": results,
            "media_id": media_id,
            "accounts_used": len(results)
        }

def test_socialpilot():
    """Test SocialPilot integration"""
    poster = SocialPilotPoster()
    
    # Test getting accounts
    print("Testing SocialPilot connection...")
    accounts = poster.get_accounts()
    
    if accounts:
        print(f"✅ Successfully connected to SocialPilot!")
        print(f"Found {len(accounts)} connected accounts:")
        for acc in accounts:
            print(f"  - {acc.get('name', 'Unknown')} ({acc.get('type', 'Unknown')})")
        return True
    else:
        print("❌ Failed to connect to SocialPilot or no accounts found")
        return False

if __name__ == "__main__":
    test_socialpilot()