import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI()
API_BASE = "https://shrutibots.site"


# ---------------- TOKEN ---------------- #

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


# ---------------- STREAM ---------------- #

@app.get("/stream")
async def stream_video(request: Request, url: str, type: str = "video"):

    # Extract video ID
    if "v=" in url:
        video_id = url.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in url:
        video_id = url.split("youtu.be/")[-1].split("?")[0]
    else:
        video_id = url.strip()

    token = await get_token(video_id, type)
    if not token:
        raise HTTPException(status_code=400, detail="Failed to get token")

    shruti_stream = f"{API_BASE}/stream/{video_id}?type={type}&token={token}"

    headers = {}
    if "range" in request.headers:
        headers["Range"] = request.headers["range"]

    session = aiohttp.ClientSession()
    upstream = await session.get(shruti_stream, headers=headers)

    if upstream.status not in (200, 206):
        await session.close()
        raise HTTPException(status_code=upstream.status)

    response_headers = {
        "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
        "Content-Length": upstream.headers.get("Content-Length"),
        "Content-Range": upstream.headers.get("Content-Range"),
        "Content-Type": upstream.headers.get("Content-Type", "video/mp4"),
    }

    async def stream_generator():
        try:
            async for chunk in upstream.content.iter_chunked(1024 * 512):
                yield chunk
        except Exception:
            pass
        finally:
            await upstream.release()
            await session.close()

    return StreamingResponse(
        stream_generator(),
        status_code=upstream.status,
        headers={k: v for k, v in response_headers.items() if v},
    )

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    uvicorn.run("stream_server:app", host="0.0.0.0", port=8000, reload=False)
