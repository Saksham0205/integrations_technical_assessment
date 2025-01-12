import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import requests
from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis


CLIENT_ID = '329147ef-ac8b-4863-bced-77b7b195258f'
CLIENT_SECRET = 'e59aec7edddef2edf4388ef611b151ab5fc85c61f828df909c147085e8ffb4f1'
REDIRECT_URI = 'http://localhost:8000/integrations/airtable/oauth2callback'
authorization_url = f'https://airtable.com/oauth2/v1/authorize?client_id={CLIENT_ID}&response_type=code&owner=user&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fintegrations%2Fairtable%2Foauth2callback'

encoded_client_id_secret = base64.b64encode(f'{CLIENT_ID}:{CLIENT_SECRET}'.encode()).decode()
scope = 'data.records:read data.records:write data.recordComments:read data.recordComments:write schema.bases:read schema.bases:write'


async def authorize_hubspot(user_id, org_id):
    """Initialize OAuth flow for HubSpot"""
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = json.dumps(state_data)
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)

    return f'{authorization_url}&state={encoded_state}'


async def oauth2callback_hubspot(request: Request):
    """Handle OAuth callback from HubSpot"""
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error'))

    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(encoded_state)

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response, _ = await asyncio.gather(
            client.post(
                'https://api.hubapi.com/oauth/v1/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'code': code,
                    'redirect_uri': REDIRECT_URI
                }
            ),
            delete_key_redis(f'hubspot_state:{org_id}:{user_id}')
        )

    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    """Retrieve HubSpot credentials from Redis"""
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials


def create_integration_item_metadata_object(contact):
    """Create IntegrationItem object from HubSpot contact data"""
    return IntegrationItem(
        id=contact['id'],
        type='contact',
        name=f"{contact.get('properties', {}).get('firstname', '')} {contact.get('properties', {}).get('lastname', '')}".strip() or 'Unnamed Contact',
        creation_time=contact.get('properties', {}).get('createdate'),
        last_modified_time=contact.get('properties', {}).get('lastmodifieddate'),
        parent_id=None,  #HubSpot contacts don't have parent-child relationships in the same way as Notion
    )


async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """Fetch contacts from HubSpot and convert them to IntegrationItems"""
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')

    response = requests.get(
        'https://api.hubapi.com/crm/v3/objects/contacts',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        },
        params={
            'limit': 100,  # Adjust as needed
            'properties': ['firstname', 'lastname', 'createdate', 'lastmodifieddate']
        }
    )

    if response.status_code == 200:
        contacts = response.json().get('results', [])
        integration_items = [
            create_integration_item_metadata_object(contact)
            for contact in contacts
        ]
        print(integration_items)
        return integration_items
    else:
        raise HTTPException(status_code=response.status_code, detail='Failed to fetch HubSpot contacts')