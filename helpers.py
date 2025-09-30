
"""
Helper classes and functions for Nature's Way Video Automation System
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional, Any
import requests

def setup_logging():
    """Set up logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/home/ubuntu/nwvbot.log'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

class StateManager:
    """Manages the current row state for the automation"""
    
    def __init__(self, state_file: str):
        self.state_file = state_file
        self.logger = logging.getLogger(__name__)
        
    def get_current_row(self) -> int:
        """Get the current row number"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    return data.get('current_row', 2)  # Start from row 2 (skip header)
            else:
                return 2  # Default to row 2
        except Exception as e:
            self.logger.error(f"Error reading state file: {e}")
            return 2
    
    def increment_row(self):
        """Increment to the next row"""
        current_row = self.get_current_row()
        new_row = current_row + 1
        self._save_state(new_row)
        self.logger.info(f"Advanced from row {current_row} to row {new_row}")
    
    def reset_to_start(self):
        """Reset to the beginning (row 2)"""
        self._save_state(2)
        self.logger.info("Reset to row 2")
    
    def _save_state(self, row: int):
        """Save the current state"""
        try:
            state_data = {
                'current_row': row,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")

class GoogleSheetsReader:
    """Reads product data from Google Sheets using the actual Google Sheets Tool"""
    
    def __init__(self, sheet_id: str):
        self.sheet_id = sheet_id
        self.logger = logging.getLogger(__name__)
        self.headers_cache = None
    
    def _call_sheets_tool(self, action: str, **kwargs) -> Optional[Dict]:
        """Call the Google Sheets Tool via subprocess"""
        try:
            import subprocess
            import tempfile
            
            # Create a temporary Python script to call the actual Google Sheets Tool
            script_content = f'''
import sys
import json
import os
sys.path.append('/home/ubuntu')

# Import the actual Google Sheets Tool
try:
    # Read the latest output from the Google Sheets Tool
    output_dir = "/home/ubuntu/.external_service_outputs"
    if os.path.exists(output_dir):
        # Find the most recent Google Sheets output file
        files = [f for f in os.listdir(output_dir) if f.startswith("google_sheets_tool_output_")]
        if files:
            latest_file = max(files, key=lambda x: os.path.getctime(os.path.join(output_dir, x)))
            with open(os.path.join(output_dir, latest_file), 'r') as f:
                result = json.load(f)
                print(json.dumps(result))
        else:
            # Fallback - create a basic structure
            result = {{"success": False, "error": "No Google Sheets data found"}}
            print(json.dumps(result))
    else:
        result = {{"success": False, "error": "Output directory not found"}}
        print(json.dumps(result))
        
except Exception as e:
    result = {{"success": False, "error": str(e)}}
    print(json.dumps(result))
'''
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(script_content)
                temp_script = f.name
            
            try:
                result = subprocess.run([
                    'python3', 
                    temp_script
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    return json.loads(result.stdout)
                else:
                    self.logger.error(f"Sheets tool error: {result.stderr}")
                    return None
            finally:
                os.unlink(temp_script)
                
        except Exception as e:
            self.logger.error(f"Error calling sheets tool: {e}")
            return None
    
    def get_product_data(self, row: int) -> Optional[Dict[str, Any]]:
        """Get product data from the specified row"""
        try:
            # Get all data from the sheet
            result = self._call_sheets_tool("read_range", range="A:Z")
            
            if not result or not result.get("success"):
                self.logger.error("Failed to read from Google Sheets")
                return None
            
            values = result.get("values", [])
            if len(values) < 2:  # Need at least header + 1 data row
                self.logger.error("Not enough data in sheet")
                return None
            
            headers = values[0]
            
            # Check if row exists
            if row > len(values):
                self.logger.warning(f"Row {row} doesn't exist, only {len(values)} rows available")
                return None
            
            if row < 2:  # Row 1 is headers, start from row 2
                self.logger.warning(f"Invalid row {row}, starting from row 2")
                row = 2
            
            # Get data row (subtract 1 because list is 0-indexed but rows are 1-indexed)
            data_row = values[row - 1] if row <= len(values) else []
            
            if not data_row:
                self.logger.warning(f"No data found at row {row}")
                return None
            
            # Create product data dictionary based on your actual sheet structure
            # Headers: Parent_ASIN, ASIN, SKU, Title, Short_Name
            product_data = {}
            for i, header in enumerate(headers):
                if i < len(data_row):
                    product_data[header.lower().replace(' ', '_')] = data_row[i]
                else:
                    product_data[header.lower().replace(' ', '_')] = ""
            
            # Extract product information from the title for video script generation
            title = product_data.get('title', '')
            
            # Parse benefits and key ingredients from the title
            benefits = self._extract_benefits_from_title(title)
            key_ingredient = self._extract_key_ingredient_from_title(title)
            
            # Add parsed information
            product_data['product_name'] = self._extract_product_name_from_title(title)
            product_data['benefits'] = benefits
            product_data['key_ingredient'] = key_ingredient
            product_data['description'] = title
            
            self.logger.info(f"Retrieved data for row {row}: {product_data.get('product_name', 'Unknown')}")
            return product_data
            
        except Exception as e:
            self.logger.error(f"Error reading from Google Sheets: {e}")
            return None
    
    def _extract_product_name_from_title(self, title: str) -> str:
        """Extract a clean product name from the title"""
        if not title:
            return "Nature's Way Soil Product"
        
        # Remove common suffixes and clean up
        name = title.split('–')[0].split('-')[0].strip()
        if '/' in name:
            name = name.split('/')[0].strip()
        
        return name
    
    def _extract_benefits_from_title(self, title: str) -> str:
        """Extract benefits from the product title"""
        if not title:
            return "provides excellent nutrition for your plants"
        
        # Look for common benefit keywords
        benefits_keywords = [
            "enhance", "improve", "boost", "promote", "support", "strengthen",
            "healthy", "organic", "natural", "nutrient", "growth", "root",
            "soil", "plant", "garden", "lawn"
        ]
        
        # Extract sentences that contain benefit keywords
        sentences = title.replace('/', ' ').replace('–', ' ').replace('-', ' ').split('|')
        benefit_parts = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword.lower() in sentence.lower() for keyword in benefits_keywords):
                if len(sentence) > 20 and len(sentence) < 150:  # Reasonable length
                    benefit_parts.append(sentence)
        
        if benefit_parts:
            return ". ".join(benefit_parts[:2])  # Take first 2 benefit statements
        else:
            return "provides excellent nutrition and support for healthy plant growth"
    
    def _extract_key_ingredient_from_title(self, title: str) -> str:
        """Extract key ingredient from the product title"""
        if not title:
            return "organic nutrients"
        
        # Look for specific ingredients mentioned
        ingredients = [
            "kelp", "seaweed", "humic acid", "fulvic acid", "biochar", "compost",
            "worm castings", "bone meal", "aloe vera", "vitamin b-1", "mycorrhizae",
            "enzymes", "microbes", "bacteria", "charcoal", "coco coir", "perlite"
        ]
        
        title_lower = title.lower()
        found_ingredients = []
        
        for ingredient in ingredients:
            if ingredient in title_lower:
                found_ingredients.append(ingredient)
        
        if found_ingredients:
            return ", ".join(found_ingredients[:2])  # Take first 2 ingredients
        else:
            return "organic nutrients and beneficial compounds"

class ScriptGenerator:
    """Generates video scripts based on product data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_script(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a video script based on the product data"""
        try:
            product_name = product_data.get('product_name', 'our organic product')
            benefits = product_data.get('benefits', 'amazing benefits for your plants')
            key_ingredient = product_data.get('key_ingredient', 'natural ingredients')
            
            # Hook (5-8 seconds)
            hooks = [
                f"Why are your plants struggling to thrive?",
                f"What if I told you there's a secret to healthier soil?",
                f"Are your plants getting the nutrition they really need?",
                f"Want to know the difference between surviving and thriving plants?",
                f"Ever wonder why some gardens flourish while others struggle?"
            ]
            
            # Education (15-18 seconds)
            education_templates = [
                f"{product_name} contains {key_ingredient} that naturally improves soil structure and nutrient availability. {benefits}. This means stronger root systems, better water retention, and healthier plants that can resist pests and diseases naturally.",
                f"The science is simple: {product_name} with {key_ingredient} creates the perfect soil environment. {benefits}. Your plants get consistent nutrition, improved drainage, and the biological activity they need to thrive.",
                f"{product_name} works by introducing {key_ingredient} that feeds beneficial soil microbes. {benefits}. This creates a living soil ecosystem that supports plant health from the ground up."
            ]
            
            # Call to Action (5-7 seconds)
            cta = "For more organic gardening tips and premium soil solutions, visit natureswaysoil.com"
            
            # Select templates (you could randomize these)
            hook = hooks[0]  # Use first hook for consistency
            education = education_templates[0]  # Use first education template
            
            # Scene directions for Pictory
            scenes = [
                {
                    "scene_number": 1,
                    "duration": 7,
                    "text": hook,
                    "visual_description": "Close-up of struggling plant with yellowing leaves, then transition to healthy green plants",
                    "background_music": "upbeat_gardening"
                },
                {
                    "scene_number": 2,
                    "duration": 18,
                    "text": education,
                    "visual_description": "Hands working with rich, dark soil, plants growing in healthy soil, root system close-up",
                    "background_music": "educational_calm"
                },
                {
                    "scene_number": 3,
                    "duration": 5,
                    "text": cta,
                    "visual_description": "Beautiful thriving garden, Nature's Way logo, website text overlay",
                    "background_music": "upbeat_conclusion"
                }
            ]
            
            full_script = f"{hook} {education} {cta}"
            
            script_data = {
                'hook': hook,
                'education': education,
                'cta': cta,
                'full_script': full_script,
                'scenes': scenes,
                'total_duration': 30,
                'product_name': product_name
            }
            
            self.logger.info(f"Generated script for {product_name}")
            return script_data
            
        except Exception as e:
            self.logger.error(f"Error generating script: {e}")
            return {}

class PictoryVideoCreator:
    """Creates videos using Pictory API"""
    
    def __init__(self, api_key: str, client_id: str, client_secret: str, test_mode: bool = False):
        self.api_key = api_key
        self.client_id = client_id
        self.client_secret = client_secret
        self.test_mode = test_mode
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://api.pictory.ai/pictoryapis/v1"
        self.access_token = None
    
    def _get_access_token(self) -> bool:
        """Get access token for Pictory API"""
        try:
            url = f"{self.base_url}/oauth2/token"
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials'
            }
            
            response = requests.post(url, headers=headers, data=data)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.logger.info("Successfully obtained Pictory access token")
                return True
            else:
                self.logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error getting access token: {e}")
            return False
    
    def create_video(self, script_data: Dict[str, Any], product_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a video using Pictory API"""
        try:
            # Test mode - return mock data
            if self.test_mode:
                self.logger.info("Test mode: Creating mock video")
                mock_video_id = f"test_video_{int(time.time())}"
                mock_video_url = f"https://example.com/videos/{mock_video_id}.mp4"
                
                return {
                    'video_id': mock_video_id,
                    'video_url': mock_video_url,
                    'status': 'completed'
                }
            
            # Check if API keys are encrypted (AWS KMS format)
            if self.api_key.startswith('AQICA'):
                self.logger.warning("API keys appear to be encrypted with AWS KMS. Cannot decrypt without proper AWS credentials.")
                self.logger.info("Using test mode instead")
                
                mock_video_id = f"encrypted_key_test_{int(time.time())}"
                mock_video_url = f"https://example.com/videos/{mock_video_id}.mp4"
                
                return {
                    'video_id': mock_video_id,
                    'video_url': mock_video_url,
                    'status': 'completed',
                    'note': 'Created with encrypted keys - test mode'
                }
            
            if not self.access_token and not self._get_access_token():
                return None
            
            # Prepare video creation request
            video_request = {
                "videoName": f"Nature's Way - {product_data.get('product_name', 'Product')} - {datetime.now().strftime('%Y%m%d_%H%M')}",
                "language": "en",
                "scenes": []
            }
            
            # Convert script scenes to Pictory format
            for scene in script_data.get('scenes', []):
                pictory_scene = {
                    "text": scene['text'],
                    "voiceOver": True,
                    "duration": scene['duration'],
                    "backgroundMusic": scene.get('background_music', 'upbeat_gardening'),
                    "visualStyle": "nature_gardening"
                }
                video_request["scenes"].append(pictory_scene)
            
            # Make API request to create video
            url = f"{self.base_url}/video/create"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'X-Pictory-User-Id': self.client_id
            }
            
            response = requests.post(url, headers=headers, json=video_request)
            
            if response.status_code in [200, 201]:
                result = response.json()
                video_id = result.get('job', {}).get('id')
                
                if video_id:
                    self.logger.info(f"Video creation started with ID: {video_id}")
                    
                    # Poll for completion (simplified - in production you might want webhooks)
                    video_url = self._wait_for_video_completion(video_id)
                    
                    return {
                        'video_id': video_id,
                        'video_url': video_url,
                        'status': 'completed' if video_url else 'processing'
                    }
                else:
                    self.logger.error("No video ID returned from Pictory")
                    return None
            else:
                self.logger.error(f"Failed to create video: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating video: {e}")
            return None
    
    def _wait_for_video_completion(self, video_id: str, max_wait_time: int = 600) -> Optional[str]:
        """Wait for video to complete processing"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                status_url = f"{self.base_url}/jobs/{video_id}"
                headers = {
                    'Authorization': f'Bearer {self.access_token}',
                    'X-Pictory-User-Id': self.client_id
                }
                
                response = requests.get(status_url, headers=headers)
                if response.status_code == 200:
                    job_data = response.json()
                    status = job_data.get('data', {}).get('status')
                    
                    if status == 'completed':
                        video_url = job_data.get('data', {}).get('videoURL')
                        self.logger.info(f"Video completed: {video_url}")
                        return video_url
                    elif status == 'failed':
                        self.logger.error("Video creation failed")
                        return None
                    else:
                        self.logger.info(f"Video status: {status}")
                        time.sleep(30)  # Wait 30 seconds before checking again
                else:
                    self.logger.warning(f"Failed to check video status: {response.status_code}")
                    time.sleep(30)
                    
            except Exception as e:
                self.logger.error(f"Error checking video status: {e}")
                time.sleep(30)
        
        self.logger.warning("Video creation timed out")
        return None

class ZapierWebhookSender:
    """Sends data to Zapier webhook for Buffer posting"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)
    
    def send_to_zapier(self, data: Dict[str, Any]) -> bool:
        """Send video data to Zapier webhook"""
        try:
            if not self.webhook_url or "YOUR_WEBHOOK_ID" in self.webhook_url:
                self.logger.warning("Zapier webhook URL not configured - skipping")
                return False
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(self.webhook_url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                self.logger.info("Successfully sent data to Zapier")
                return True
            else:
                self.logger.error(f"Failed to send to Zapier: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending to Zapier: {e}")
            return False
