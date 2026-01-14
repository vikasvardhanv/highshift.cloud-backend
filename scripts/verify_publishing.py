import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.platforms import twitter, instagram, facebook, linkedin

class TestVideoPublishing(unittest.IsolatedAsyncioTestCase):
    
    @patch("httpx.AsyncClient")
    async def test_twitter_upload_video(self, mock_client_cls):
        print("\nTesting Twitter Video Upload...")
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Mock responses
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"media_id_string": "12345", "processing_info": {"state": "succeeded"}}
        mock_client.post.return_value = response
        
        status_response = MagicMock()
        status_response.json.return_value = {"processing_info": {"state": "succeeded"}}
        mock_client.get.return_value = status_response

        # Test
        media_id = await twitter.upload_media("fake_token", media_data=b"fake_video_bytes", media_type="video/mp4")
        
        # Verify INIT call
        init_call = mock_client.post.call_args_list[0]
        self.assertIn("command", init_call.kwargs["data"])
        self.assertEqual(init_call.kwargs["data"]["media_category"], "tweet_video")
        print("✅ Twitter Video Upload verified")

    @patch("httpx.AsyncClient")
    async def test_instagram_publish_video(self, mock_client_cls):
        print("\nTesting Instagram Video Publish...")
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Mock responses
        create_res = MagicMock()
        create_res.status_code = 200
        create_res.json.return_value = {"id": "container_123"}
        
        publish_res = MagicMock()
        publish_res.status_code = 200
        publish_res.json.return_value = {"id": "media_123"}
        
        # Side effect for post: create then publish. Or mocking post return value.
        # Since we call post twice (create, publish), we need side_effect.
        mock_client.post.side_effect = [create_res, publish_res]
        
        status_res = MagicMock()
        status_res.status_code = 200
        status_res.json.return_value = {"status_code": "FINISHED"}
        mock_client.get.return_value = status_res

        # Test
        await instagram.publish_video("fake_token", "ig_user_123", "http://vid.url/1.mp4", "caption")
        
        # Verify Create Container call
        create_call = mock_client.post.call_args_list[0]
        params = create_call.kwargs["params"]
        self.assertEqual(params["media_type"], "VIDEO")
        self.assertEqual(params["video_url"], "http://vid.url/1.mp4")
        print("✅ Instagram Video Publish verified")

    @patch("httpx.AsyncClient")
    async def test_facebook_post_video(self, mock_client_cls):
        print("\nTesting Facebook Video Post...")
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"id": "post_123"}
        mock_client.post.return_value = response

        # Test
        await facebook.post_video("fake_token", "page_123", "desc", "http://vid.url/1.mp4")
        
        # Verify Post call
        post_call = mock_client.post.call_args_list[0]
        self.assertIn("/videos", post_call.args[0])
        self.assertEqual(post_call.kwargs["params"]["file_url"], "http://vid.url/1.mp4")
        print("✅ Facebook Video Post verified")

    @patch("httpx.AsyncClient")
    async def test_linkedin_video_flow(self, mock_client_cls):
        print("\nTesting LinkedIn Video Flow...")
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        reg_response = MagicMock()
        reg_response.status_code = 200
        reg_response.json.return_value = {
            "value": {
                "uploadMechanism": {
                    "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest": {"uploadUrl": "http://upload.linkedin"}
                },
                "asset": "urn:li:asset:123"
            },
            "id": "urn:li:share:123"
        }
        
        post_response = MagicMock()
        post_response.status_code = 200
        post_response.json.return_value = {"id": "urn:li:share:123"}
        
        mock_client.post.side_effect = [reg_response, post_response]
        
        put_response = MagicMock()
        put_response.status_code = 200
        mock_client.put.return_value = put_response

        # Test
        token = "fake_token"
        urn = "urn:li:person:123"
        
        # 1. Register
        await linkedin.register_upload(token, urn, media_type="video")
        reg_call = mock_client.post.call_args_list[0]
        self.assertIn("feedshare-video", reg_call.kwargs["json"]["registerUploadRequest"]["recipes"][0])
        
        # 2. Upload (Skipping as it's just a PUT)
        
        # 3. Post
        await linkedin.post_with_media(token, urn, "text", "asset_urn", media_type="video")
        post_call = mock_client.post.call_args_list[1] 
        self.assertEqual(post_call.kwargs["json"]["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"], "VIDEO")

        print("✅ LinkedIn Video Flow verified")

if __name__ == "__main__":
    unittest.main()
