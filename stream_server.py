import aiohttp
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from youtubesearchpython.__future__ import VideosSearch

app = FastAPI()

API_BASE = "https://shrutibots.site"


# =========================================================
#                       UTIL
# =========================================================

def extract_video_id(url: str):
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0]
    return url.strip()


# =========================================================
#                       TOKEN
# =========================================================

async def get_token(video_id: str, media_type: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{API_BASE}/download",
            params={"url": video_id, "type": media_type},
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("download_token")


# =========================================================
#                       STREAM ENDPOINT
# =========================================================

@app.get("/stream")
async def stream_video(request: Request, url: str, type: str = "video"):

    video_id = extract_video_id(url)

    token = await get_token(video_id, type)
    if not token:
        raise HTTPException(status_code=400, detail="Failed to get token")

    shruti_stream = f"{API_BASE}/stream/{video_id}?type={type}&token={token}"

    headers = {}
    if "range" in request.headers:
        headers["Range"] = request.headers["range"]

    async with aiohttp.ClientSession() as session:
        upstream = await session.get(shruti_stream, headers=headers)

        if upstream.status not in (200, 206):
            raise HTTPException(status_code=upstream.status)

        response_headers = {
            "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
            "Content-Length": upstream.headers.get("Content-Length"),
            "Content-Range": upstream.headers.get("Content-Range"),
            "Content-Type": upstream.headers.get("Content-Type", "video/mp4"),
        }

        async def stream_generator():
            async for chunk in upstream.content.iter_chunked(1024 * 512):
                yield chunk

        return StreamingResponse(
            stream_generator(),
            status_code=upstream.status,
            headers={k: v for k, v in response_headers.items() if v},
        )


# =========================================================
#                 FULL VIDEO INFO ENDPOINT
# =========================================================

@app.get("/info")
async def full_video_info(url: str):

    video_id = extract_video_id(url)

    try:
        search = VideosSearch(video_id, limit=1)
        data = await search.next()
        result = data["result"][0]
    except Exception:
        raise HTTPException(status_code=404, detail="Video not found")

    return {
        "video_id": video_id,
        "raw_library_response": result,
        "all_thumbnails": result.get("thumbnails"),
        "channel_full_object": result.get("channel"),
        "accessibility": result.get("accessibility"),
        "description_snippet": result.get("descriptionSnippet"),
        "rich_thumbnail": result.get("richThumbnail"),
        "published_time": result.get("publishedTime"),
        "view_count_object": result.get("viewCount"),
        "duration": result.get("duration"),
        "is_live": result.get("isLive"),
        "badges": result.get("badges"),
        "link": result.get("link"),
        "title": result.get("title"),
    }


# =========================================================
#                       MAIN
# =========================================================

if __name__ == "__main__":
    uvicorn.run("stream_server:app", host="0.0.0.0", port=8000, reload=False)
