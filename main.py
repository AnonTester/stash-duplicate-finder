import json
import os
import requests
from typing import List, Dict, Any, Optional
from collections import defaultdict
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from rapidfuzz import fuzz
import aiofiles

app = FastAPI(title="Stash Duplicate Finder")

# Create necessary directories
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

# Mount static files and setup templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

CONFIG_FILE = "config.json"

class StashConfig(BaseModel):
    stash_endpoint: str
    api_key: Optional[str] = None

class Scene(BaseModel):
    id: str
    title: str
    stash_ids: List[Dict[str, str]]
    files: List[Dict[str, Any]]

class StashResponse(BaseModel):
    count: int
    scenes: List[Scene]

async def get_config() -> StashConfig:
    """Load configuration from file or create default if doesn't exist"""
    if not os.path.exists(CONFIG_FILE):
        return StashConfig(
            stash_endpoint="http://localhost:9999/graphql",
            api_key=""
        )
    
    async with aiofiles.open(CONFIG_FILE, 'r') as f:
        content = await f.read()
        config_data = json.loads(content)
        return StashConfig(**config_data)

async def save_config(config: StashConfig):
    """Save configuration to file"""
    async with aiofiles.open(CONFIG_FILE, 'w') as f:
        await f.write(json.dumps(config.dict(), indent=4))

async def fetch_all_scenes(config: StashConfig) -> StashResponse:
    """Fetch all scenes from Stash using GraphQL"""
    headers = {
        "Content-Type": "application/json",
    }
    
    if config.api_key:
        headers["ApiKey"] = config.api_key

    query = """
    query FindAllScenes {
      findScenes(
        filter: { per_page: -1 }
      ) {
        count
        scenes {
          id
          title
          stash_ids {
            stash_id
          }
          files {
            size
            basename
            path
            bit_rate
            height
            duration
            video_codec
            fingerprints{
              type
              value
            }
          }
        }
      }
    }
    """

    payload = {
        "query": query,
        "variables": {}
    }

    try:
        response = requests.post(config.stash_endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            raise HTTPException(status_code=400, detail=f"GraphQL Error: {data['errors']}")
        
        return StashResponse(**data["data"]["findScenes"])
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect to Stash: {str(e)}")

def find_duplicates_by_stashid(scenes: List[Scene]) -> Dict[str, List[Scene]]:
    """Find duplicates by stash_id"""
    stashid_groups = defaultdict(list)
    
    for scene in scenes:
        stash_ids = [stash_id["stash_id"] for stash_id in scene.stash_ids if stash_id.get("stash_id")]
        for stash_id in stash_ids:
            if stash_id:  # Only consider non-empty stash_ids
                stashid_groups[stash_id].append(scene)
    
    # Return only groups with duplicates
    return {stash_id: scenes for stash_id, scenes in stashid_groups.items() if len(scenes) > 1}

def find_duplicates_by_name(scenes: List[Scene]) -> Dict[str, List[Scene]]:
    """Find duplicates by name with fuzzy matching"""
    # First group by exact title (case insensitive)
    title_groups = defaultdict(list)
    for scene in scenes:
        if scene.title:
            normalized_title = scene.title.lower().strip()
            title_groups[normalized_title].append(scene)
    
    # Find fuzzy matches for groups that don't have exact matches
    processed = set()
    fuzzy_groups = {}
    
    titles = list(title_groups.keys())
    
    for i, title1 in enumerate(titles):
        if title1 in processed:
            continue
            
        group = title_groups[title1].copy()
        
        for j, title2 in enumerate(titles[i+1:], i+1):
            if title2 in processed:
                continue
                
            # Use fuzzy matching with a threshold
            similarity = fuzz.ratio(title1, title2)
            if similarity > 85:  # Adjust threshold as needed
                group.extend(title_groups[title2])
                processed.add(title2)
        
        if len(group) > 1:
            fuzzy_groups[title1] = group
        processed.add(title1)
    
    return fuzzy_groups

def find_duplicates_by_oshash(scenes: List[Scene]) -> Dict[str, List[Scene]]:
    """Find duplicates by oshash fingerprint"""
    oshash_groups = defaultdict(list)
    
    for scene in scenes:
        for file in scene.files:
            for fingerprint in file.get("fingerprints", []):
                if fingerprint.get("type") == "oshash":
                    oshash = fingerprint.get("value")
                    if oshash:
                        oshash_groups[oshash].append(scene)
    
    return {oshash: scenes for oshash, scenes in oshash_groups.items() if len(scenes) > 1}

def find_duplicates_by_phash(scenes: List[Scene]) -> Dict[str, List[Scene]]:
    """Find duplicates by phash fingerprint"""
    phash_groups = defaultdict(list)
    
    for scene in scenes:
        for file in scene.files:
            for fingerprint in file.get("fingerprints", []):
                if fingerprint.get("type") == "phash":
                    phash = fingerprint.get("value")
                    if phash:
                        phash_groups[phash].append(scene)
    
    return {phash: scenes for phash, scenes in phash_groups.items() if len(scenes) > 1}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Main page showing scene count and duplicate options"""
    config = await get_config()
    
    # Check if we have a valid configuration
    if not config.stash_endpoint or config.stash_endpoint == "http://localhost:9999/graphql":
        return RedirectResponse("/settings")
    
    try:
        stash_data = await fetch_all_scenes(config)
        scene_count = stash_data.count
        scenes = stash_data.scenes
    except HTTPException as e:
        scene_count = 0
        scenes = []
        error_message = f"Error fetching data: {e.detail}"
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": error_message,
            "config": config
        })
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "scene_count": scene_count,
        "scenes": scenes,
        "config": config
    })

@app.get("/duplicates/{duplicate_type}")
async def find_duplicates(duplicate_type: str, request: Request):
    """Find duplicates by various methods"""
    config = await get_config()
    
    try:
        stash_data = await fetch_all_scenes(config)
        scenes = stash_data.scenes
    except HTTPException as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Error fetching data: {e.detail}",
            "config": config
        })
    
    duplicate_groups = {}
    method_name = ""
    
    if duplicate_type == "stashid":
        duplicate_groups = find_duplicates_by_stashid(scenes)
        method_name = "Stash ID"
    elif duplicate_type == "name":
        duplicate_groups = find_duplicates_by_name(scenes)
        method_name = "Name (Fuzzy Match)"
    elif duplicate_type == "oshash":
        duplicate_groups = find_duplicates_by_oshash(scenes)
        method_name = "OSHASH"
    elif duplicate_type == "phash":
        duplicate_groups = find_duplicates_by_phash(scenes)
        method_name = "PHASH"
    else:
        raise HTTPException(status_code=404, detail="Duplicate type not found")
    
    return templates.TemplateResponse("duplicates.html", {
        "request": request,
        "duplicate_groups": duplicate_groups,
        "method_name": method_name,
        "duplicate_type": duplicate_type,
        "config": config,
        "total_duplicate_groups": len(duplicate_groups),
        "total_duplicate_scenes": sum(len(scenes) for scenes in duplicate_groups.values())
    })

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page to configure Stash connection"""
    config = await get_config()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "config": config
    })

@app.post("/settings")
async def update_settings(
    request: Request,
    stash_endpoint: str = Form(...),
    api_key: str = Form("")
):
    """Update Stash configuration"""
    config = StashConfig(
        stash_endpoint=stash_endpoint,
        api_key=api_key if api_key else None
    )
    
    await save_config(config)
    
    return RedirectResponse("/", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
