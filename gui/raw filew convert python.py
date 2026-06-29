import rawpy
import tifffile
import numpy as np
import matplotlib.pyplot as plt
from skimage.color import rgb2lab # For standard CIE L*a*b* conversion

def process_and_analyze_colors(raw_path):
    # 1. Extract pure, unmanipulated 16-bit linear RGB array
    with rawpy.imread(raw_path) as raw:
        linear_rgb = raw.postprocess(
            gamma=(1, 1),              # Strict linear data
            no_auto_bright=True,       # Bypasses software auto-exposure
            output_color=rawpy.ColorSpace.raw, # Raw sensor color spectrum
            output_bps=16,             # 16-bit depth (0 to 65535)
            use_camera_wb=False,       # Prevents arbitrary camera tint shifts
            use_auto_wb=False
        )
    
    # 2. Normalize array to 0.0 - 1.0 floats for scientific computing
    # This prevents integer overflow/underflow during math matrix multiplication
    normalized_rgb = linear_rgb.astype(np.float32) / 65535.0
    
    # 3. Apply standard sRGB linear-to-CIELAB conversion
    # skimage expects 0-1 float inputs. This maps linear data accurately into
    # L* (Lightness), a* (Green to Red), and b* (Blue to Yellow)
    lab_matrix = rgb2lab(normalized_rgb)
    
    # 4. Extract specific regions for color recognition analysis
    # Example: Let's extract the exact color coordinates of the very center pixel
    height, width, _ = lab_matrix.shape
    center_y, center_x = height // 2, width // 2
    center_pixel_lab = lab_matrix[center_y, center_x]
    
    print("\n--- ANALYTICAL COLOR READOUT (Center Pixel) ---")
    print(f"Lightness (L*): {center_pixel_lab[0]:.2f}  (Range: 0 to 100)")
    print(f"Green/Red  (a*): {center_pixel_lab[1]:.2f}  (Negative=Green, Positive=Red)")
    print(f"Blue/Yellow(b*): {center_pixel_lab[2]:.2f}  (Negative=Blue, Positive=Yellow)")
    
    # 5. Visualizing the data with Matplotlib
    # Because linear data is pitch black to humans, we apply a software 
    # display-only gamma profile just so you can physically see your target regions.
    display_safe_rgb = np.power(normalized_rgb, 1/2.2) 
    
    fig, ax = plt.subplots(1, 2, figsize=(12, 6))
    
    # Subplot 1: Human-viewable representation
    ax[0].imshow(display_safe_rgb)
    ax[0].plot(center_x, center_y, 'ro', markersuffix='Center Target') # Mark center
    ax[0].set_title("Visual Reference Map (Gamma 2.2 applied for display)")
    ax[0].axis('off')
    
    # Subplot 2: Heatmap of Lightness channel (L*) for homogeneity/shadow analysis
    im = ax[1].imshow(lab_matrix[:, :, 0], cmap='gray')
    fig.colorbar(im, ax=ax[1], label='L* Value')
    ax[1].set_title("True Lightness Density Matrix (L*)")
    ax[1].axis('off')
    
    plt.tight_layout()
    plt.show()