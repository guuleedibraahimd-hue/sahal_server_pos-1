# Sahal Server — AI Video Clothes Studio

## What was added

The System Admin panel now has **🎬 AI Video Studio**.

Workflow:

1. Admin opens AI Video Studio.
2. Uploads a short video.
3. Uploads a clothing/coat image.
4. Browser automatically extracts the video's first frame.
5. Server sends the first frame + garment to Segmind Try-On Diffusion.
6. The generated try-on frame is used as the reference image for Segmind Video Tryon V2.
7. The final video is saved to Firebase Storage.
8. Admin can preview and open/download the result.

## Required server environment variable

Add this secret to your hosting environment:

`SEGMIND_API_KEY=YOUR_SEGMIND_API_KEY`

Optional:

`AI_VIDEO_MAX_SECONDS=50`

Do **not** put the Segmind key in HTML/JavaScript.

## Current video limit

Segmind Video Tryon V2 currently accepts videos up to 50 seconds per clip. The UI blocks longer videos.

Your existing 2:19 video is longer than that limit. For that video, either:

- use a clip of 50 seconds or less for the first test, or
- add a later chunking/concatenation workflow to process the full 2:19 as multiple clips.

## API flow

The implementation uses:

- Segmind `try-on-diffusion` for the modified first frame.
- Segmind `video-tryon-v2` for the final video.

Both calls use the same `SEGMIND_API_KEY`.

## Local Windows test

From the project folder:

```bash
pip install -r requirements.txt
set SEGMIND_API_KEY=YOUR_KEY
python app.py
```

If you use PowerShell:

```powershell
$env:SEGMIND_API_KEY="YOUR_KEY"
python app.py
```

Your existing Firebase environment variables are still required because the project already uses Firebase.

## Render

In Render → your service → Environment, add:

`SEGMIND_API_KEY`

Then redeploy.

## Important

The AI generation itself is not free. Segmind charges according to its current credits/pricing. The Flask code only provides the interface and API integration; it does not remove the provider's usage charges.
