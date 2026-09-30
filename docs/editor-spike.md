# Media editor spike (P7b)

Run on 2026-09-30 against the dev Cloudinary account (Free plan: 25 credits a month, dynamic
folders). What Cloudinary actually does with each transformation the editor needs, on photos and
on video, the render flow chosen from it, and the gotchas. The builders
(`apps/api/src/socialhood/media/editor/transform.py` and `apps/web/src/lib/editor/transform.ts`)
follow this document; their golden cases (`packages/editor-fixtures/transform-cases.json`) were
also fetched live: all 86 builds, stills and covers of the 66 cases returned 200 with the size and
length the builder predicted (built for the spike assets).

Test assets, all under `socialhood-dev/editor-spike/` and deleted afterwards with their derived
files: a generated 1200 x 900 JPEG, an 8 s 640 x 360 H.264 video with a 440 Hz tone, a 200 x 80
PNG logo, and a 48 MB, 12 s, 1080p noise video. Two Cloudinary samples (`samples/sea-turtle`,
27 MB, 15 s, 1080p; `samples/elephants`, 38 MB, 48 s, 1080p) were used for the size tests; the
four derived files made of them were deleted too. Each result was checked by downloading it:
status, size and length with ffprobe, and colour with ffmpeg's `signalstats` (luma, saturation,
the U and V planes) against the untransformed file, or a region of it for overlays and timing.

## What works

✓ works, ✗ refused (4xx), **ignored** means a 200 with bytes identical to the untransformed
render: Cloudinary drops the effect silently.

| Tool | Photo | Video | Syntax used | Notes |
|---|---|---|---|---|
| Trim | n/a | ✓ | `so_1.5,eo_5.5` (and `so_2,du_3`) | 8 s → 4.08 s |
| Crop to an aspect | ✓ | ✓ | `c_fill,ar_4:5,g_center` | `ar_1.91:1` is **400** "Invalid aspect ratio"; `ar_1.91` works. `g_auto` works on both (2.4 s on an 8 s video) |
| Exact crop | ✓ | ✓ | `c_crop,w_,h_,x_,y_` then `c_scale,w_,h_` | what the builder uses: whole pixels, so the preview is exact |
| Rotate | ✓ | ✓ | `a_90`, `a_180`, `a_270` | dimensions swap |
| Flip | ✓ | ✓ | `a_hflip`, `a_vflip` | `a_hflip.90` also works on photos |
| Brightness | ✓ | ✓ | `e_brightness:-99…100` | |
| Contrast | ✓ | ✓ | `e_contrast:-100…100` | subtle on the test video |
| Saturation | ✓ | ✓ | `e_saturation:-100…100` | -100 is black and white on both |
| Gamma | ✓ | ✓ | `e_gamma:-50…150` | |
| Vignette | ✓ | ✓ | `e_vignette:0…100,b_black` | a photo's vignette is **transparent**, so JPEG shows white edges; `b_black` in the same component makes it dark like video's. Photos' is stronger than video's at the same value |
| Blur, noise | ✓ | ✓ | `e_blur:200`, `e_noise:40` | not in the editor |
| Vibrance | ✓ | **ignored** | `e_vibrance` | photo-only |
| Sepia, grayscale | ✓ | **ignored** | `e_sepia:80`, `e_grayscale` | video: grayscale is `e_saturation:-100` |
| Sharpen | ✓ | **ignored** | `e_sharpen:1…2000` | photo-only |
| Tint, hue, red/green/blue | ✓ | **ignored** | `e_tint:25:orange`, `e_hue:30`, `e_red:20` | photo-only; see warmth |
| Warmth (both) | ✓ | ✓ | `l_text:Arial_20:%20,b_rgb:FF8C0040/c_scale,w_{W},h_{H}/fl_layer_apply` | a one-space text layer with a translucent background, scaled to the frame: a colour wash. Orange warms, `0064FF` cools. `o_` on a text layer is **ignored** on video; the alpha in `b_rgb:RRGGBBAA` works |
| Artistic filters | ✓ 20 of 21 | **ignored** | `e_art:zorro` | `daenerys` is **400** "Unknown filter" |
| Auto-enhance | ✓ | **ignored** | `e_improve`, `e_improve:outdoor:60` | also `e_auto_color`, `e_auto_contrast`, `e_auto_brightness` (photos). `e_viesus_correct` is **500** (a paid add-on) |
| Text | ✓ | ✓ | `l_text:Poppins_64_bold_italic_center:Hello,co_rgb:FFFFFF,b_rgb:000000CC,bo_19px_solid_rgb:000000CC,c_limit,w_972` then `fl_layer_apply,fl_no_overflow,g_center,x_,y_` | see "Text" below |
| Text timing | n/a | ✓ | `so_2,eo_4` **on `fl_layer_apply`** | on the `l_text` component they are ignored (always shown) |
| Logo | ✓ | ✓ | `l_ws:{wid}:post:{id},c_scale,w_216,o_70` then `fl_layer_apply,fl_no_overflow,g_center,x_,y_` | slashes become colons; `o_` works for image layers on video; PNG alpha kept |
| Speed | n/a | ✓ | `e_accelerate:100` / `50` / `-50` | 8 s → 4.12 s (2x), 5.44 s (≈1.5x), 16.04 s (0.5x); sound kept |
| Fade in / out | n/a | ✓ | `e_fade:1000`, `e_fade:-1000` | luma 24.7 at 0.05 s (125 unfaded); 20.5 in the last frame |
| Mute | n/a | ✓ | `e_volume:mute` | silent AAC track (-91 dB). `ac_none` removes the track instead; we keep one for Instagram's spec |
| Still frame / cover | n/a | ✓ | `…/video/upload/so_2/{chain}/{id}.jpg` | every **image** effect applies to a frame (e_art, e_sepia…), so a video preview must use only video effects or it lies. `e_fade` is ignored on frames |

One effect per component: `e_brightness:20,e_contrast:20` applies only one of them. Chain
components instead (`e_brightness:20/e_contrast:20` applied both).

### Text

- Fonts: Cloudinary renders Google fonts by name. Worked: Poppins, Montserrat, Playfair Display,
  Pacifico, Anton, Permanent Marker (the editor's six), and Roboto, Open Sans, Oswald, Lobster,
  Lato, Merriweather, Dancing Script, Roboto Slab, Caveat, Abril Fatface, Noto Sans, Mukta, Teko,
  Rubik, Hind, Arial, Times New Roman, Georgia, Courier New, Verdana, Impact, Helvetica. **400**
  "Unsupported font family": Bebas Neue, Inter, Space Grotesk, Noto Sans Devanagari, Tiro
  Devanagari Hindi, Baloo 2. A name with spaces is `Playfair%20Display`.
- Styles: `_bold`, `_italic`, `_center`, `_right`, `_stroke`, `_letter_spacing_10` work.
- Escaping: the text is percent-encoded UTF-8, and `,` `/` `%` are encoded **twice** (`%252C`,
  `%252F`, `%2525`); `%0A` is a line break; `#?&:'"()+=<>` work encoded once; `_ - . ~` as they are.
- Hindi renders in any of the fonts (a Devanagari fallback), properly shaped; Poppins has its own
  Devanagari.
- Emoji: symbols in the Basic Multilingual Plane (❤ ★) draw in one colour. Anything outside it (🔥,
  most emoji): encoded once it is **400** "Invalid encoding", encoded twice it silently draws
  nothing. The API refuses such text (422); the builders drop it.
- Size: `c_fit,w_` makes the text box (and its background) the full width; `c_limit,w_` keeps the
  box to the text and scales a line that is too long down to fit; `w_` alone scales short text up
  to the width. The builder uses `c_limit` at 90% of the width; lines break only where the owner
  typed a newline.
- Overflow: a layer past the edge **grows a photo's canvas** (1200 x 900 became 1368 x 936, and
  1409 x 900 for a box near the left edge); `fl_layer_apply,fl_no_overflow` keeps the size. Video
  clips to the frame anyway.
- Timing on video: `so_`/`eo_` on `fl_layer_apply` count in the timeline at that point of the
  chain. After a trim they are seconds of the trimmed clip (a box at 0 to 2 s after
  `so_2,eo_8` showed for the first 2 s of the output). Before `e_accelerate` they speed up with the
  video (a box at 2 to 4 s, then 2x, showed from 1 to 2 s). So text times are seconds of the trimmed
  clip, the timeline the trim filmstrip shows, and overlays go before the speed change.

## Rendering video: eager, not on the fly

- `POST /v1_1/{cloud}/video/explicit` (signed) with `public_id`, `type=upload`,
  `eager={transformation}/mp4|{cover}/jpg` and `eager_async=true` answers 200 at once:
  `eager[i] = {status: "processing", batch_id, url, secure_url}` (the URL includes the source's
  version). The 8 s 360p render was ready in about 4 s; a 8 s 720p render of the 48 MB 1080p video
  in 7 s.
- Finished renders appear in the Admin API's `GET resources/video/upload/{public_id}`: `derived`
  lists `transformation` (URL-decoded: `%20` comes back as a space), `format`, `bytes`, `id` and
  `secure_url`. Only 10 are listed by default; pass `max_results=500` (and follow
  `derived_next_cursor`).
- Don't poll by requesting the derived URL: a HEAD right after the eager call answered 200 at once
  with no length, because it rendered the video again on the fly (billed twice; slow for big files).
- Notifications (`eager_notification_url`): not received in the spike, because the spike machine
  has no public URL. Their signature is SHA-1 by default: the account's own API answers are signed
  that way (the upload response's `signature` equals
  `sha1("public_id=…&version=…" + api_secret)`), and Cloudinary signs a notification as
  `X-Cld-Signature = sha1(body + X-Cld-Timestamp + api_secret)` (SHA-256 on accounts switched to
  it). `/webhooks/cloudinary` verifies either, rejects a timestamp older than 2 hours or 5 minutes
  ahead, and fails closed. Verify arrival on staging (TB.6).
- On the fly: no 423 in the spike. Full 1080p re-encodes answered 200 synchronously: 27 MB and 15 s
  in 10.6 s, 38 MB and 48 s in 22.7 s, the uploaded 48 MB and 12 s in 19.9 s. Trims of the same
  files took 1.3 to 1.9 s, a frame 1 s. Too slow to hand Instagram as a fetch URL, and it would
  render again whenever the cache is cold, so video renders are eager. (P7's publishing already
  sends unedited video as an on-the-fly `vc_h264,ac_aac,f_mp4` URL: worth moving to eager too; not
  in this phase.)
- Account limits (usage API `media_limits`): video uploads up to 100 MB, images 10 MB and 25 MP.

## Credits

The usage API reported 0.19 credits used before the spike (11 transformations) and 4.27 credits
after it: 3,933 transformation units, 3.93 credits. The spike made about 160 distinct image
transformations and about 130 video derivations, mostly 8 s at 360p plus about ten 1080p ones up to
48 s. Images cost one unit each, so video accounts for most of the 3,900: Cloudinary bills video
by output length and resolution, and a 30 s 1080p Reel will cost far more than a photo. TB.6
measures one render of a 30 s 1080p Reel (usage before and after) and records it here, so the
render caps can be checked against the Cloudinary plan's credits.

## The render flow

1. **Preview in the browser, from the same builder.** The editor builds every preview URL with the
   TypeScript builder: a photo's preview is its render (on the fly, scaled down to the editor's
   width with `still(…, {maxWidth})`); a video's is a still frame at the playhead with the same
   crop, colour, text showing at that moment and logo (`still(…, {atS})`), plus the original
   video playing for timing. The trim filmstrip and the cover picker use stills.
2. **Save the edit.** The composer saves each item's spec in the draft (`edits`, parallel to
   `asset_ids`). Saving never renders.
3. **Render on Done.** The editor asks for the render: `POST …/media-renders {asset_id, spec}`.
   The same spec of the same asset is one row (spec hash): asking again returns it. A photo's
   render is `ready` at once (its URL is the on-the-fly transformation). A video's is `pending`,
   counts against `video_renders_monthly` (402 when over), and start_render sends the eager call
   (with the notification URL when API_BASE_URL is set): `rendering`.
4. **Finish.** The Cloudinary notification (primary) or poll_render (every 15 s, up to 10 minutes;
   the only way without a public API URL) marks it `ready` with its URL, size and length, or
   `failed` with the reason. sweep_stuck_renders restarts pending renders lost for 2 minutes and
   fails renders unfinished after 30. Each change publishes `media_render.updated`, and the posts
   using the render get `scheduled_post.updated`.
5. **Gate.** A post whose video edit isn't rendered fails the checklist's `edits` item, and
   schedule and publish now answer 422 on `edits.{i}`. Photos never wait.
6. **Publish the rendered file.** Photos: the build URL (JPEG, up to 1440 px wide). Video: the
   render's URL (H.264, up to 1080 px wide). A Reel with a cover sends `cover_url`, the still at
   `cover_s` (an image transformation of the source, so it needs no render of its own).

## Gotchas

- Effects video ignores return 200 with the effect missing, not an error: the builders never emit
  them for video, and `problems()` refuses them on a video's spec.
- Image effects apply to video frames, so a video still built with them would lie.
- A photo's vignette is transparent (white in JPEG) without `b_black`.
- Overlays past the edge grow a photo's canvas without `fl_no_overflow`.
- Text timing only works on `fl_layer_apply`; overlays speed up with `e_accelerate` after them.
- `ar_1.91:1` is refused; the builder crops in pixels and never uses `ar_`.
- Video output sizes must be even for H.264 (a 203 px crop came back 202 px wide); the builder
  makes every video crop and output size even.
- Derived transformations come back URL-decoded from the Admin API and notifications; compare
  decoded strings.
- Unsigned on-the-fly URLs: anyone who knows a public id can ask for new transformations on our
  credits. Strict transformations (signed URLs) would stop that, but then every preview needs a
  signature from the API. Left off in R1 (as P3 and P7 already rely on unsigned delivery URLs);
  noted for P9's security pass.
- Rotation metadata: phone photos and videos may carry an orientation flag. The builder takes the
  width and height Cloudinary reports; check a portrait phone video and an EXIF-rotated photo in
  TB.6 (a wrong pair would crop the wrong way).
