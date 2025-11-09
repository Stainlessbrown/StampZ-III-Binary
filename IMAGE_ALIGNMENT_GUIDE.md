# Image Alignment Feature Guide

## Overview

StampZ now includes **automatic image alignment** for stamps of the same design. This allows you to:
- Set one "reference" stamp image as the template
- Automatically align other stamps of the same design to match
- Apply the same sampling marker positions across multiple images
- Perfect for analyzing multiple examples of the same stamp issue

## How It Works

Uses **ORB (Oriented FAST and Rotated BRIEF)** feature detection:
- ✅ Detects **frame ornaments, corners, borders** (structural features)
- ✅ Ignores **colors and denomination numbers**
- ✅ Handles rotation, scale, translation, and perspective
- ✅ Fast (< 1 second per image)
- ✅ No machine learning training needed

## Workflow

### 1. Set Reference Template

**File → Image Alignment → Set as Reference Template**

1. Load your "definitive" stamp image (best quality, clear features)
2. Select **File → Image Alignment → Set as Reference Template**
3. System detects features (typically 100-500 depending on stamp complexity)
4. You'll see: "✓ Reference template set successfully! Detected X features"

**What makes a good reference:**
- Clear frame/border details
- Good scan quality
- Typical positioning (not rotated/skewed)
- Average wear (not heavily worn or perfect mint)

### 2. Auto-Align New Images

**File → Image Alignment → Auto-Align to Reference**

1. Load another stamp of the **same design** (different shade/denomination OK)
2. Select **File → Image Alignment → Auto-Align to Reference**
3. Image automatically aligns to reference in ~1 second
4. Title bar shows "[ALIGNED]" to indicate registration

**Result:**
- Image is now in same position/orientation as reference
- You can apply the same template/sampling markers
- Precise color comparison across multiple stamps

### 3. Save/Load Reference (Optional)

**Save for reuse:**
- **File → Image Alignment → Save Reference...**
- Saves to `.pkl` file for later use
- Can reload without re-setting reference

**Load saved reference:**
- **File → Image Alignment → Load Reference...**
- Instantly ready to align new images

## Example Use Case

**Scenario:** Analyzing 10 examples of the 1¢ Franklin stamp

1. Load best quality 1¢ stamp → **Set as Reference Template**
2. Place sampling markers (frame, background, portrait, etc.)
3. Analyze colors, export results
4. Load next 1¢ stamp → **Auto-Align to Reference**
5. Apply same template → markers are perfectly positioned!
6. Repeat for all 10 stamps

**Time saved:** Minutes per stamp vs manual repositioning

## What Features Does It Match?

**ORB automatically prioritizes:**
- ✅ **Frame corners and ornaments** (strongest features)
- ✅ **Border patterns and scrollwork**
- ✅ **Portrait/vignette edges** (outline, not details)
- ✅ **Text edges** (shape, not content)

**ORB naturally avoids:**
- ❌ Denomination numbers (smooth curves, weak features)
- ❌ Colors (works on grayscale structure)
- ❌ Fine portrait details (too variable with wear)

## Success Criteria

**Alignment works best when:**
- Same stamp design (different denominations OK!)
- Similar scan resolution (within 20%)
- Not extremely worn vs mint
- Frame/borders visible
- Minimum 10 matching features found

**Alignment may fail if:**
- Completely different stamp design
- Extreme wear (frame damaged)
- Very different scanning conditions
- One stamp heavily cropped

## Troubleshooting

### "Could not detect enough features"
- Image may be too low quality
- Try a clearer scan
- Ensure frame/borders are visible

### "Not enough matches"
- Stamps may be too different
- Try a different reference that's more similar
- Check if it's actually the same design

### "Alignment successful" but looks wrong
- Rare false positive
- Try with a different reference
- Manual review recommended

## Technical Details

**Feature Detection:**
- 500 features maximum
- Harris corner score for quality
- 8-level scale pyramid

**Matching:**
- Brute-force matcher with Hamming distance
- RANSAC outlier rejection (5.0 pixel threshold)
- Minimum 10 inlier matches required

**Transformation:**
- Full homography (handles rotation, scale, skew, perspective)
- Warp to reference size
- Maintains original color depth

## File I/O

**No OpenCV file format issues:**
- Uses your existing PIL pipeline for all file operations
- OpenCV only processes numpy arrays (no file reading/writing)
- Supports all your existing formats (TIFF, PNG, JPEG)

## Performance

- Feature detection: ~0.5 seconds
- Matching: ~0.2 seconds
- Warping: ~0.3 seconds
- **Total: ~1 second per image**

---

**Questions?** The feature automatically avoids numbers by design - ORB naturally prefers the geometric features of frames and borders over smooth numerical text!
