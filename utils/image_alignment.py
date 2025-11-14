"""
Image Alignment Manager for StampZ

Provides automatic image registration/alignment for stamps of the same design.
Uses ORB feature detection to match structural elements (frame, borders, ornaments)
while avoiding denomination-specific features (numbers, colors).
"""

import numpy as np
import cv2
from PIL import Image
from typing import Optional, Tuple, Dict, Any
import pickle
import os


class ImageAlignmentManager:
    """
    Manages reference template and automatic alignment of new images.
    
    Uses ORB (Oriented FAST and Rotated BRIEF) feature detector which:
    - Detects corners and edges (strong on frame ornaments)
    - Ignores color (works on grayscale structure)
    - Fast and patent-free
    - Naturally prefers geometric features over smooth areas (like numbers)
    """
    
    def __init__(self):
        """Initialize the alignment manager."""
        self.reference_image = None  # PIL Image
        self.reference_keypoints = None
        self.reference_descriptors = None
        self.reference_size = None  # (width, height)
        self.reference_filepath = None  # Track loaded reference file
        self.reference_crop_box = None  # Store crop box used for reference (left, top, right, bottom)
        
        # Alignment mode: 'similarity', 'affine', or 'perspective'
        # similarity: rotation, translation, uniform scale only (most rigid)
        # affine: rotation, translation, scale, shear (no perspective warping)
        # perspective: full homography (allows perspective distortion)
        self.alignment_mode = 'similarity'  # Default to similarity for stamps
        
        # Auto-crop settings
        self.auto_crop_enabled = True  # Enable automatic content detection and cropping
        
        # ORB detector with optimized parameters for stamps
        self.orb = cv2.ORB_create(
            nfeatures=500,  # Detect up to 500 features
            scaleFactor=1.2,  # Scale pyramid factor
            nlevels=8,  # Number of pyramid levels
            edgeThreshold=15,  # Border pixels to ignore
            firstLevel=0,
            WTA_K=2,
            scoreType=cv2.ORB_HARRIS_SCORE,  # Use Harris corner detector score
            patchSize=31,
            fastThreshold=20
        )
        
        # Matcher for features
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        
        # Quality thresholds
        self.min_matches = 10  # Minimum matches needed for alignment
        self.ransac_threshold = 5.0  # RANSAC outlier threshold
    
    def _auto_crop_content(self, pil_image: Image.Image, padding: int = 10) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
        """
        Automatically detect and crop to stamp content, removing white/light borders.
        
        Args:
            pil_image: PIL Image to crop
            padding: Pixels of padding to keep around detected content
            
        Returns:
            Tuple of (cropped PIL Image, crop_box (left, top, right, bottom))
        """
        try:
            # Convert to grayscale numpy array
            gray = np.array(pil_image.convert('L'))
            
            # Apply adaptive threshold to detect content
            # This works well for stamps with various background colors
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 51, 10
            )
            
            # Find contours of content
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                # No content detected, return original
                return pil_image, (0, 0, pil_image.width, pil_image.height)
            
            # Find bounding box of all contours combined
            x_min, y_min = gray.shape[1], gray.shape[0]
            x_max, y_max = 0, 0
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                x_min = min(x_min, x)
                y_min = min(y_min, y)
                x_max = max(x_max, x + w)
                y_max = max(y_max, y + h)
            
            # Add padding and constrain to image bounds
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(pil_image.width, x_max + padding)
            y_max = min(pil_image.height, y_max + padding)
            
            # Crop the image
            crop_box = (x_min, y_min, x_max, y_max)
            cropped = pil_image.crop(crop_box)
            
            print(f"  Auto-cropped from {pil_image.size} to {cropped.size}")
            return cropped, crop_box
            
        except Exception as e:
            print(f"Warning: Auto-crop failed, using original image: {e}")
            return pil_image, (0, 0, pil_image.width, pil_image.height)
        
    def set_reference_image(self, pil_image: Image.Image) -> bool:
        """
        Set the reference image for alignment.
        
        Args:
            pil_image: PIL Image to use as reference
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Auto-crop reference image if enabled
            if self.auto_crop_enabled:
                print("Auto-cropping reference image...")
                pil_image, self.reference_crop_box = self._auto_crop_content(pil_image)
            else:
                self.reference_crop_box = (0, 0, pil_image.width, pil_image.height)
            
            # Store reference image
            self.reference_image = pil_image.copy()
            self.reference_size = pil_image.size
            
            # Convert to grayscale numpy array for feature detection
            gray = np.array(pil_image.convert('L'))
            
            # Detect features
            self.reference_keypoints, self.reference_descriptors = self.orb.detectAndCompute(gray, None)
            
            if self.reference_keypoints is None or len(self.reference_keypoints) < self.min_matches:
                print(f"Warning: Only detected {len(self.reference_keypoints) if self.reference_keypoints else 0} features")
                return False
            
            print(f"✓ Reference set: detected {len(self.reference_keypoints)} features")
            return True
            
        except Exception as e:
            print(f"Error setting reference image: {e}")
            return False
    
    def has_reference(self) -> bool:
        """Check if a reference image is set."""
        return self.reference_image is not None and self.reference_descriptors is not None
    
    def align_image(self, pil_image: Image.Image, show_matches: bool = False) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
        """
        Align a new image to the reference template.
        
        Args:
            pil_image: PIL Image to align
            show_matches: If True, return debug info about matched features
            
        Returns:
            Tuple of (aligned PIL Image or None, info dict)
            Info dict contains:
                - success: bool
                - num_matches: int
                - transform_matrix: numpy array or None
                - message: str
                - matched_keypoints: list of (x, y) tuples if show_matches=True
        """
        info = {
            'success': False,
            'num_matches': 0,
            'transform_matrix': None,
            'message': '',
            'matched_keypoints': []
        }
        
        if not self.has_reference():
            info['message'] = "No reference image set"
            return None, info
        
        try:
            # Auto-crop input image if enabled
            if self.auto_crop_enabled:
                print("Auto-cropping input image...")
                pil_image, crop_box = self._auto_crop_content(pil_image)
                info['crop_box'] = crop_box
            
            # Convert to grayscale numpy array
            gray = np.array(pil_image.convert('L'))
            
            # Detect features in new image
            keypoints, descriptors = self.orb.detectAndCompute(gray, None)
            
            if keypoints is None or len(keypoints) < self.min_matches:
                info['message'] = f"Not enough features detected ({len(keypoints) if keypoints else 0})"
                return None, info
            
            # Match features
            matches = self.matcher.match(self.reference_descriptors, descriptors)
            
            if len(matches) < self.min_matches:
                info['message'] = f"Not enough matches ({len(matches)} < {self.min_matches})"
                info['num_matches'] = len(matches)
                return None, info
            
            # Sort by distance (quality)
            matches = sorted(matches, key=lambda x: x.distance)
            
            # Extract matched keypoint coordinates
            ref_pts = np.float32([self.reference_keypoints[m.queryIdx].pt for m in matches])
            new_pts = np.float32([keypoints[m.trainIdx].pt for m in matches])
            
            # Calculate transformation matrix using RANSAC
            if self.alignment_mode == 'similarity':
                # Similarity transform: rotation, translation, uniform scale (no shear/perspective)
                M, mask = cv2.estimateAffinePartial2D(new_pts, ref_pts, method=cv2.RANSAC, 
                                                       ransacReprojThreshold=self.ransac_threshold)
            elif self.alignment_mode == 'affine':
                # Affine transform: rotation, translation, scale, shear (no perspective)
                M, mask = cv2.estimateAffine2D(new_pts, ref_pts, method=cv2.RANSAC, 
                                                ransacReprojThreshold=self.ransac_threshold)
            else:
                # Full perspective homography (allows perspective warping)
                M, mask = cv2.findHomography(new_pts, ref_pts, cv2.RANSAC, self.ransac_threshold)
            
            if M is None:
                info['message'] = "Could not calculate transformation"
                info['num_matches'] = len(matches)
                return None, info
            
            # Count inliers (good matches after RANSAC)
            inliers = np.sum(mask)
            
            if inliers < self.min_matches:
                info['message'] = f"Not enough inlier matches ({inliers})"
                info['num_matches'] = inliers
                return None, info
            
            # Warp image to align with reference
            img_array = np.array(pil_image)
            if self.alignment_mode in ['similarity', 'affine']:
                # Use warpAffine for 2x3 similarity/affine matrix
                aligned_array = cv2.warpAffine(img_array, M, self.reference_size)
            else:
                # Use warpPerspective for 3x3 homography
                aligned_array = cv2.warpPerspective(img_array, M, self.reference_size)
            
            # Convert back to PIL
            aligned_pil = Image.fromarray(aligned_array)
            
            # Success!
            info['success'] = True
            info['num_matches'] = int(inliers)
            info['transform_matrix'] = M
            info['message'] = f"Successfully aligned using {inliers} feature matches"
            
            # Store matched keypoints for visualization if requested
            if show_matches:
                inlier_indices = np.where(mask.ravel() == 1)[0]
                info['matched_keypoints'] = [
                    (int(new_pts[i][0]), int(new_pts[i][1])) 
                    for i in inlier_indices
                ]
            
            print(f"✓ Alignment successful: {inliers} matches")
            return aligned_pil, info
            
        except Exception as e:
            info['message'] = f"Alignment error: {str(e)}"
            print(f"Error during alignment: {e}")
            import traceback
            traceback.print_exc()
            return None, info
    
    def save_reference(self, filepath: str) -> bool:
        """
        Save reference template to file.
        
        Args:
            filepath: Path to save reference data
            
        Returns:
            True if successful
        """
        if not self.has_reference():
            return False
        
        try:
            # Convert keypoints to serializable format
            kp_data = [(kp.pt, kp.size, kp.angle, kp.response, kp.octave, kp.class_id) 
                       for kp in self.reference_keypoints]
            
            data = {
                'keypoints': kp_data,
                'descriptors': self.reference_descriptors,
                'size': self.reference_size
            }
            
            # Save reference image separately
            image_path = filepath.replace('.pkl', '_reference.png')
            self.reference_image.save(image_path)
            
            # Save feature data
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            
            print(f"✓ Reference saved to {filepath}")
            return True
            
        except Exception as e:
            print(f"Error saving reference: {e}")
            return False
    
    def load_reference(self, filepath: str) -> bool:
        """
        Load reference template from file.
        
        Args:
            filepath: Path to load reference data from
            
        Returns:
            True if successful
        """
        try:
            # Load feature data
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            # Reconstruct keypoints
            self.reference_keypoints = [
                cv2.KeyPoint(x=pt[0], y=pt[1], size=size, angle=angle,
                            response=response, octave=octave, class_id=class_id)
                for pt, size, angle, response, octave, class_id in data['keypoints']
            ]
            
            self.reference_descriptors = data['descriptors']
            self.reference_size = tuple(data['size'])
            self.reference_filepath = filepath  # Store filepath
            
            # Load reference image
            image_path = filepath.replace('.pkl', '_reference.png')
            if os.path.exists(image_path):
                self.reference_image = Image.open(image_path)
            
            print(f"✓ Reference loaded: {len(self.reference_keypoints)} features")
            return True
            
        except Exception as e:
            print(f"Error loading reference: {e}")
            return False
    
    def get_reference_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the current reference.
        
        Returns:
            Dict with reference info or None
        """
        if not self.has_reference():
            return None
        
        return {
            'num_features': len(self.reference_keypoints),
            'size': self.reference_size,
            'has_image': self.reference_image is not None,
            'filepath': self.reference_filepath
        }
    
    def set_alignment_mode(self, mode: str):
        """
        Set the alignment mode.
        
        Args:
            mode: 'similarity' (rotation, translation, uniform scale - most rigid),
                  'affine' (rotation, translation, scale, shear), or 
                  'perspective' (full homography with perspective warping)
        """
        if mode in ['similarity', 'affine', 'perspective']:
            self.alignment_mode = mode
            print(f"Alignment mode set to: {mode}")
        else:
            print(f"Invalid mode '{mode}'. Use 'similarity', 'affine', or 'perspective'.")
    
    def get_alignment_mode(self) -> str:
        """Get the current alignment mode."""
        return self.alignment_mode
    
    def clear_reference(self):
        """Clear the current reference."""
        self.reference_image = None
        self.reference_keypoints = None
        self.reference_descriptors = None
        self.reference_size = None
        self.reference_filepath = None
        self.reference_crop_box = None
        print("Reference cleared")
    
    def set_auto_crop(self, enabled: bool):
        """Enable or disable automatic content cropping."""
        self.auto_crop_enabled = enabled
        print(f"Auto-crop {'enabled' if enabled else 'disabled'}")
    
    def is_auto_crop_enabled(self) -> bool:
        """Check if auto-crop is enabled."""
        return self.auto_crop_enabled
