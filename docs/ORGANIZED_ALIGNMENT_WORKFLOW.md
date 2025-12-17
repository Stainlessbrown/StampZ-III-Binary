# Organized Alignment Workflow

## Overview
When using Image Alignment in StampZ, you can now keep aligned images organized in a separate subdirectory, making analysis cleaner and easier.

## Workflow

### 1. Set Up Your Reference
1. Open your reference stamp image
2. Go to **File → Image Alignment → Set as Reference Template**
3. The reference is now stored in memory

### 2. Bulk Align with Output Directory
1. Go to **File → Image Alignment → Bulk Align Images...**
2. Select all images you want to align (they should be similar stamps)
3. Click "Browse..." to choose an output directory
   - **Tip:** Create a subfolder like `aligned/` in your working directory
4. Check "Copy reference image to output directory" (enabled by default)
5. Click "Process Images"

### 3. Result
All aligned images will be saved to your output directory:
- `reference_template.tif` - Your reference image
- `stamp1_aligned.tif` - First aligned image
- `stamp2_aligned.tif` - Second aligned image
- etc.

## Benefits
- **Clean working directory**: Original scans stay separate from aligned versions
- **Easy analysis**: All aligned images in one folder, ready for batch color analysis
- **Reference included**: The reference image is copied to the output folder so you have the complete set
- **No manual sorting**: Everything is organized automatically

## Example Directory Structure

Before alignment:
```
/MyStamps/
  ├── scan001.tif (reference)
  ├── scan002.tif
  ├── scan003.tif
  └── scan004.tif
```

After bulk alignment to `aligned/` subfolder:
```
/MyStamps/
  ├── scan001.tif (originals remain)
  ├── scan002.tif
  ├── scan003.tif
  ├── scan004.tif
  └── aligned/
      ├── reference_template.tif
      ├── scan002_aligned.tif
      ├── scan003_aligned.tif
      └── scan004_aligned.tif
```

Now you can:
- Load all images from `aligned/` folder for consistent analysis
- Use the same template coordinates on all aligned stamps
- Keep your original scans intact in the parent directory

## Notes
- The reference image is saved as TIFF format (`reference_template.tif`) for maximum quality
- Aligned images keep their original format (TIFF, PNG, JPEG)
- You can uncheck "Copy reference image to output directory" if you don't want it included
