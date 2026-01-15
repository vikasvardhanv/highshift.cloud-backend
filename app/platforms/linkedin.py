import httpx
import urllib.parse
from app.utils.logger import logger

async def get_auth_url(client_id: str, redirect_uri: str, state: str, scopes: list):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": " ".join(scopes)
    }
    encoded_params = urllib.parse.urlencode(params)
    return f"https://www.linkedin.com/oauth/v2/authorization?{encoded_params}"

async def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        res.raise_for_status()
        return res.json()

async def post_to_profile(access_token: str, author_urn: str, text: str):
    async with httpx.AsyncClient() as client:
        body = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        res = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json"
            },
            json=body
        )
        res.raise_for_status()
        return res.json()

async def register_upload(access_token: str, author_urn: str, media_type: str = "image"):
    """
    Step 1: Register the media upload to get an upload URL.
    media_type: 'image' or 'video'
    """
    recipe = "urn:li:digitalmediaRecipe:feedshare-image" if media_type == "image" else "urn:li:digitalmediaRecipe:feedshare-video"
    
    async with httpx.AsyncClient() as client:
        body = {
            "registerUploadRequest": {
                "recipes": [recipe],
                "owner": author_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        res = await client.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json"
            },
            json=body
        )
        res.raise_for_status()
        return res.json()

async def upload_asset(upload_url: str, data: bytes, access_token: str):
    """
    Step 2: Upload the binary data (image or video) to the URL from Step 1.
    """
    async with httpx.AsyncClient() as client:
        # LinkedIn upload URLs often require specific headers or no auth header depending on return
        # Usually checking the response from registerUpload gives headers.
        # For simplicity we try basic PUT with binary body.
        # Large videos might need chunking, but registerUpload for feedshare-video usually gives a single URL for < 200MB.
        res = await client.put(
            upload_url,
            content=data,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/octet-stream"} 
        )
        if res.status_code not in [200, 201]:
             # Retry without auth header (sometimes the URL is a signed S3 URL)
             res = await client.put(upload_url, content=data, headers={"Content-Type": "application/octet-stream"})
             
        res.raise_for_status()
        return True

async def post_with_media(access_token: str, author_urn: str, text: str, asset_urn: str, media_type: str = "image"):
    """
    Step 3: Create the UGC post referencing the uploaded asset URN.
    """
    category = "IMAGE" if media_type == "image" else "VIDEO"
    
    async with httpx.AsyncClient() as client:
        body = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": category,
                    "media": [
                        {
                            "status": "READY",
                            "description": {"text": text},
                            "media": asset_urn,
                            "title": {"text": text[:200]} 
                        }
                    ]
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }
        res = await client.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json"
            },
            json=body
        )
        res.raise_for_status()
        return res.json()

async def get_me(access_token: str):
    """
    Fetch the LinkedIn user profile information.
    Supports both legacy /v2/me and modern /v2/userinfo (OIDC).
    """
    async with httpx.AsyncClient() as client:
        # Try modern UserInfo first (OIDC)
        try:
            res = await client.get(
                "https://api.linkedin.com/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if res.status_code == 200:
                data = res.json()
                member_id = data.get("sub")
                full_name = data.get("name")
                picture = data.get("picture")
                return {
                    "id": f"urn:li:person:{member_id}",
                    "name": full_name,
                    "picture": picture,
                    "raw": data
                }
        except Exception as e:
            logger.warning(f"LinkedIn /userinfo failed, falling back to /me: {str(e)}")

        # Fallback to legacy /me
        res = await client.get(
            "https://api.linkedin.com/v2/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0"
            }
        )
        res.raise_for_status()
        profile_data = res.json()
        
        member_id = profile_data.get('id')
        urn = f"urn:li:person:{member_id}" if member_id and not member_id.startswith('urn:li:person:') else member_id
        
        first_name = profile_data.get('localizedFirstName', '')
        last_name = profile_data.get('localizedLastName', '')
        full_name = f"{first_name} {last_name}".strip() or "LinkedIn User"
        
        # Try to get profile picture via projection
        picture = None
        try:
            pic_res = await client.get(
                "https://api.linkedin.com/v2/me?projection=(id,profilePicture(displayImage~:playableStreams))",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0"
                }
            )
            if pic_res.status_code == 200:
                pic_data = pic_res.json()
                display_image = pic_data.get('profilePicture', {}).get('displayImage~', {})
                streams = display_image.get('playableStreams', [])
                if streams:
                    picture = streams[-1].get('identifiers', [{}])[0].get('identifier')
        except Exception as e:
            logger.warning(f"Could not fetch LinkedIn profile picture: {str(e)}")

        return {
            "id": urn,
            "name": full_name,
            "picture": picture,
            "raw": profile_data
        }

async def get_organizations(access_token: str):
    """
    Fetch LinkedIn Organizations (Company Pages) managed by the user.
    """
    async with httpx.AsyncClient() as client:
        # 1. Get Organizational Entity ACLs (find where the user is an admin)
        res = await client.get(
            "https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Restli-Protocol-Version": "2.0.0"
            }
        )
        if res.status_code != 200:
            logger.error(f"Failed to fetch LinkedIn ACLs: {res.text}")
            return []
            
        acls = res.json().get("elements", [])
        org_urns = [a["organizationalTarget"] for a in acls if a.get("role") in ["ADMINISTRATOR", "LEAD_ADMIN"]]
        
        if not org_urns:
            return []
            
        # 2. Fetch specific details for each organization
        organizations = []
        for urn in org_urns:
            try:
                # urn:li:organization:123 -> 123
                org_id = urn.split(":")[-1]
                org_res = await client.get(
                    f"https://api.linkedin.com/v2/organizations/{org_id}?projection=(id,localizedName,logoV2(displayImage~:playableStreams))",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Restli-Protocol-Version": "2.0.0"
                    }
                )
                if org_res.status_code == 200:
                    org_data = org_res.json()
                    
                    # Get logo
                    logo = None
                    streams = org_data.get("logoV2", {}).get("displayImage~", {}).get("playableStreams", [])
                    if streams:
                        logo = streams[-1].get("identifiers", [{}])[0].get("identifier")
                        
                    organizations.append({
                        "id": urn,
                        "name": org_data.get("localizedName"),
                        "picture": logo,
                        "raw": org_data
                    })
            except Exception as e:
                logger.warning(f"Failed to fetch details for organization {urn}: {str(e)}")
                
        return organizations
