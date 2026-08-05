import asyncio
import aiohttp
import os

async def test():
    email = os.environ.get("FLIPR_EMAIL", "jfl95880@gmail.com")
    password = os.environ.get("FLIPR_PASSWORD", "Flipr95880$") # Je suppose
    
    async with aiohttp.ClientSession() as session:
        # Auth
        auth_data = {
            "grant_type": "password",
            "username": email,
            "password": password
        }
        async with session.post("https://apis.goflipr.com/OAuth2/token", data=auth_data) as resp:
            data = await resp.json()
            token = data.get("access_token")
            if not token:
                print("Auth failed", data)
                return
            print("Token OK")
            
        headers = {"Authorization": f"Bearer {token}"}
        
        # Get Pools
        async with session.get("https://apis.goflipr.com/Pool/GetPools", headers=headers) as resp:
            pools = await resp.json()
            print("Pools:", pools)
            if not pools:
                return
            pool_id = pools[0]["Id"]
            
        # Get Status
        async with session.get(f"https://apis.goflipr.com/FliprHub/GetStatus/{pool_id}", headers=headers) as resp:
            status = await resp.text()
            print("Hub Status:", status)

asyncio.run(test())
