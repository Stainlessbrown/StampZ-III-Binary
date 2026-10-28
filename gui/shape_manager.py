"""
Shape management for the StampZ application.
Handles creation, manipulation, and rendering of crop shapes (polygons, circles, ovals).
"""

from enum import Enum, auto
import tkinter as tk
from typing import List, Optional, Tuple, Callable
from PIL import Image, ImageDraw, ImageTk
import logging

from utils.geometry import Point, validate_polygon, get_polygon_validation_state, PolygonValidationState
from utils.mask_generator import MaskColor, create_shape_mask, get_shape_bbox
from utils.rounded_shapes import Circle, Oval

logger = logging.getLogger(__name__)


class ShapeType(Enum):
    """Enumeration of supported shape types."""
    POLYGON = auto()
    CIRCLE = auto()
    OVAL = auto()
    RECTANGLE = auto()
    SQUARE = auto()


class ShapeManager:
    """Manages shape creation, manipulation, and rendering."""
    
    # Constants
    VERTEX_RADIUS = 5
    VERTEX_GRAB_RADIUS = 10
    MIN_VERTICES = 3
    MAX_VERTICES = 8
    MIN_SHAPE_SIZE = 10
    PREVIEW_COLOR = "#99CCFF"
    ACTIVE_VERTEX_COLOR = "#FF3300"
    
    def __init__(self, canvas: tk.Canvas, core, status_callback: Optional[Callable[[str], None]] = None):
        """Initialize shape manager.
        
        Args:
            canvas: The tkinter Canvas widget
            core: CanvasCore instance for coordinate transformations
            status_callback: Optional callback for status messages
        """
        self.canvas = canvas
        self.core = core
        self.status_callback = status_callback or (lambda _: None)
        
        # Shape state
        self.current_shape_type: ShapeType = ShapeType.POLYGON
        self.current_color: str = "#FFFFFF"  # Default white to match control panel
        self.mask_alpha: int = 80
        self.mask_image: Optional[ImageTk.PhotoImage] = None
        
        # Polygon management
        self.vertices: List[Point] = []
        self.active_vertex: Optional[int] = None
        self.hover_vertex: Optional[int] = None
        
        # Circle/Oval management
        self.shape_center: Optional[Point] = None
        self.shape_radius: Optional[float] = None
        self.shape_width: Optional[float] = None
        self.shape_height: Optional[float] = None
        
        # Control point state for circles/ovals
        self.active_control_point: Optional[str] = None
        
        # Whole-shape dragging state
        self.moving_shape = False
        self.move_offset_x = 0.0
        self.move_offset_y = 0.0
        
        # Dimensions callback
        self.dimensions_callback: Optional[Callable[[int, int], None]] = None
    
    def set_shape_type(self, shape_type: ShapeType) -> None:
        """Set the current shape type.
        
        Args:
            shape_type: New shape type to use
        """
        self.current_shape_type = shape_type
        self.clear_shape()
        self.update_display()
    
    def set_color(self, color: str) -> None:
        """Set the line and vertex color.
        
        Args:
            color: Color hex code or name
        """
        self.current_color = color
        self.update_display()
    
    def set_mask_alpha(self, alpha: int) -> None:
        """Set the alpha value for the mask.
        
        Args:
            alpha: Alpha value (0-255)
        """
        self.mask_alpha = alpha
        self.update_display()

    def set_crop_dimensions(self, width: int, height: int) -> None:
        """Apply exact pixel dimensions to the current crop selection."""
        self.shape_manager.set_shape_dimensions(width, height)
    
    def set_dimensions_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set callback function to call when crop dimensions change.
        
        Args:
            callback: Function to call with (width, height)
        """
        self.dimensions_callback = callback
    
    def clear_shape(self) -> None:
        """Clear the current shape."""
        self.vertices.clear()
        self.active_vertex = None
        self.hover_vertex = None
        self.shape_center = None
        self.shape_radius = None
        self.shape_width = None
        self.shape_height = None
        self.active_control_point = None
        self.mask_image = None
        
        # Clear dimensions display
        if self.dimensions_callback:
            self.dimensions_callback(0, 0)
        
        # Update Fine Square button state
        self._update_fine_square_button()
    
    def set_max_vertices(self, count: int) -> None:
        """Set the maximum number of vertices allowed.
        
        Args:
            count: Maximum number of vertices (3-8)
        """
        if not 3 <= count <= 8:
            raise ValueError("Vertex count must be between 3 and 8")
        self.MAX_VERTICES = count
        
        # Remove excess vertices if any
        while len(self.vertices) > count:
            self.vertices.pop()
    
    def get_vertices(self) -> List[Point]:
        """Get the current vertex list.
        
        Returns:
            Copy of current vertices
        """
        return self.vertices.copy()
    
    def set_vertices(self, vertices: List[Point]) -> None:
        """Set new vertices and update dimensions.
        
        Args:
            vertices: New vertices to set
        """
        self.vertices = vertices.copy()
        self._update_dimensions_display()  # Update dimensions first
        self.update_display()  # Then update full display
        
        # Update Fine Square button state
        self._update_fine_square_button()
        
        # Enable/disable Fine Square button when there are exactly 4 vertices
        if hasattr(self.canvas, 'main_app') and self.canvas.main_app:
            if hasattr(self.canvas.main_app, 'control_panel'):
                control_panel = self.canvas.main_app.control_panel
                if hasattr(control_panel, 'fine_square_btn'):
                    state = 'normal' if len(vertices) == 4 else 'disabled'
                    control_panel.fine_square_btn.config(state=state)
    
    def add_vertex(self, image_x: float, image_y: float) -> bool:
        """Add a new vertex at the specified coordinates.
        
        Args:
            image_x, image_y: Vertex coordinates in image space
            
        Returns:
            True if vertex was added successfully
        """
        print(f"DEBUG: add_vertex called with ({image_x:.1f}, {image_y:.1f})")
        print(f"DEBUG: current_shape_type: {self.current_shape_type}")
        print(f"DEBUG: current vertices count: {len(self.vertices)}, max: {self.MAX_VERTICES}")
        
        if self.current_shape_type != ShapeType.POLYGON:
            print(f"DEBUG: Not polygon shape type, returning False")
            return False
        
        if len(self.vertices) >= self.MAX_VERTICES:
            print(f"DEBUG: Maximum vertices reached, returning False")
            return False
        
        # Convert to Cartesian coordinates (y=0 at bottom)
        image_height = self.core.original_image.height
        cartesian_y = image_height - image_y
        new_vertex = Point(image_x, cartesian_y)
        self.vertices.append(new_vertex)
        print(f"DEBUG: Added vertex, new count: {len(self.vertices)}")
        self._update_fine_square_button()
        self.update_display()
        return True
    
    def start_circle(self, image_x: float, image_y: float) -> None:
        """Start creating a circle shape.
        
        Args:
            image_x, image_y: Center coordinates in image space
        """
        if self.current_shape_type != ShapeType.CIRCLE:
            return
        
        self.shape_center = Point(image_x, image_y)
        self.shape_radius = 0
        self.update_display()
    
    def update_circle(self, image_x: float, image_y: float) -> None:
        """Update circle radius during creation.
        
        Args:
            image_x, image_y: Current mouse coordinates in image space
        """
        if not self.shape_center:
            return
        
        # Calculate radius from mouse position
        dx = image_x - self.shape_center.x
        dy = image_y - self.shape_center.y
        requested_radius = (dx * dx + dy * dy) ** 0.5

        # Maximum radius that fits within all four image boundaries
        image_width = self.core.original_image.width
        image_height = self.core.original_image.height

        max_radius = max(0.0, min(
            self.shape_center.x,
            image_width - self.shape_center.x,
            self.shape_center.y,
            image_height - self.shape_center.y
        ))

        # Keep the center fixed and limit the radius
        self.shape_radius = min(
            max(self.MIN_SHAPE_SIZE, requested_radius),
            max_radius
        )

        self.update_display()
    
    def start_oval(self, image_x: float, image_y: float) -> None:
        """Start creating an oval shape.
        
        Args:
            image_x, image_y: Center coordinates in image space
        """
        if self.current_shape_type != ShapeType.OVAL:
            return
        
        self.shape_center = Point(image_x, image_y)
        self.shape_width = 0
        self.shape_height = 0
        self.update_display()
    
    def update_oval(self, image_x: float, image_y: float) -> None:
        """Update oval dimensions during creation.
        
        Args:
            image_x, image_y: Current mouse coordinates in image space
        """
        if not self.shape_center:
            return
        
        # Calculate width and height
        self.shape_width = max(self.MIN_SHAPE_SIZE, abs(image_x - self.shape_center.x) * 2)
        self.shape_height = max(self.MIN_SHAPE_SIZE, abs(image_y - self.shape_center.y) * 2)
        self.update_display()

    def start_rectangle(self, image_x: float, image_y: float) -> None:
        """Start a Rectangle or Square crop."""
        if self.current_shape_type not in (ShapeType.RECTANGLE, ShapeType.SQUARE):
            return

        self.shape_center = Point(image_x, image_y)
        self.shape_width = 0
        self.shape_height = 0
        self.update_display()

    def update_rectangle(self, image_x: float, image_y: float) -> None:
        """Update Rectangle or Square dimensions."""
        if not self.shape_center:
            return

        width = max(self.MIN_SHAPE_SIZE, abs(image_x - self.shape_center.x) * 2)
        height = max(self.MIN_SHAPE_SIZE, abs(image_y - self.shape_center.y) * 2)

        if self.current_shape_type == ShapeType.SQUARE:
            side = max(width, height)
            width = side
            height = side

        self.shape_width = width
        self.shape_height = height
        self.update_display()

    def move_shape(self, image_x: float, image_y: float) -> None:
        """Move a crop selection while keeping it inside the image."""
        if not self.moving_shape or self.shape_center is None:
            return

        # Calculate the selection's half-dimensions
        if self.current_shape_type == ShapeType.CIRCLE:
            half_width = self.shape_radius
            half_height = self.shape_radius
        elif self.current_shape_type in (
            ShapeType.OVAL, ShapeType.RECTANGLE, ShapeType.SQUARE
        ):
            half_width = self.shape_width / 2
            half_height = self.shape_height / 2
        else:
            return

        if half_width is None or half_height is None:
            return

        image_width = self.core.original_image.width
        image_height = self.core.original_image.height

        # Calculate the requested new center
        center_x = image_x - self.move_offset_x
        center_y = image_y - self.move_offset_y

        # Keep the entire shape within image boundaries
        center_x = max(
            half_width,
            min(center_x, image_width - half_width)
        )
        center_y = max(
            half_height,
            min(center_y, image_height - half_height)
        )

        self.shape_center = Point(center_x, center_y)
        self.update_display()

    def set_shape_dimensions(self, width: int, height: int) -> None:
        """Set exact dimensions while preserving the selection center."""
        if self.shape_center is None:
            return

        if self.current_shape_type == ShapeType.POLYGON:
            return

        if width < 1 or height < 1:
            return

        # Determine the actual requested dimensions
        if self.current_shape_type in (ShapeType.CIRCLE, ShapeType.SQUARE):
            height = width

        image_width = self.core.original_image.width
        image_height = self.core.original_image.height
        print(
            f"DEBUG: Crop boundary check: "
            f"requested={width}x{height}, "
            f"image={image_width}x{image_height}, "
            f"center=({self.shape_center.x:.1f}, "
            f"{self.shape_center.y:.1f})"
        )
        

        # Reject dimensions larger than the source image
        if width > image_width or height > image_height:
            self._update_dimensions_display()
            return

        # Preserve exact dimensions while keeping the selection inside
        half_width = width / 2
        half_height = height / 2

        center_x = max(
            half_width,
            min(self.shape_center.x, image_width - half_width)
        )
        center_y = max(
            half_height,
            min(self.shape_center.y, image_height - half_height)
        )

        self.shape_center = Point(center_x, center_y)    

        if self.current_shape_type == ShapeType.CIRCLE:
            self.shape_radius = width / 2

        elif self.current_shape_type == ShapeType.SQUARE:
            self.shape_width = width
            self.shape_height = width

        elif self.current_shape_type in (ShapeType.OVAL, ShapeType.RECTANGLE):
            self.shape_width = width
            self.shape_height = height

        self.update_display()

    def is_point_inside_shape(self, image_x: float, image_y: float) -> bool:
        """Check whether a Cartesian image point is inside the current shape."""
        if self.shape_center is None:
            return False

        dx = image_x - self.shape_center.x
        dy = image_y - self.shape_center.y

        if self.current_shape_type == ShapeType.CIRCLE:
            return self.shape_radius is not None and (
                dx * dx + dy * dy <= self.shape_radius * self.shape_radius
            )

        if self.current_shape_type in (
            ShapeType.OVAL, ShapeType.RECTANGLE, ShapeType.SQUARE
        ):
            if not self.shape_width or not self.shape_height:
                return False

            half_width = self.shape_width / 2
            half_height = self.shape_height / 2

            if self.current_shape_type == ShapeType.OVAL:
                return (
                    (dx / half_width) ** 2 +
                    (dy / half_height) ** 2 <= 1.0
                )

            return abs(dx) <= half_width and abs(dy) <= half_height

        return False

    def find_vertex_at_point(self, screen_x: int, screen_y: int) -> Optional[int]:
        """Find a vertex near the given screen coordinates.
        
        Args:
            screen_x, screen_y: Screen coordinates
            
        Returns:
            Vertex index if found, None otherwise
        """
        for i, vertex in enumerate(self.vertices):
            vertex_screen = self.core.image_to_screen_coords(vertex.x, vertex.y)
            distance = ((screen_x - vertex_screen[0]) ** 2 + (screen_y - vertex_screen[1]) ** 2) ** 0.5
            if distance <= self.VERTEX_GRAB_RADIUS:
                return i
        return None
    
    def move_vertex(self, vertex_index: int, image_x: float, image_y: float) -> None:
        """Move a vertex to new coordinates.
        
        Args:
            vertex_index: Index of vertex to move
            image_x, image_y: New coordinates in image space
        """
        if 0 <= vertex_index < len(self.vertices):
            # Store in Cartesian coordinates (y=0 at bottom)
            image_height = self.core.original_image.height
            cartesian_y = image_height - image_y
            self.vertices[vertex_index] = Point(image_x, cartesian_y)
            self.update_display()
    
    def get_cropped_image(self) -> Image.Image:
        """Get the cropped version of the image based on current shape.
        
        Returns:
            Cropped PIL Image (with _stampz_16bit_data preserved if present)
            
        Raises:
            ValueError: If no valid shape is defined
        """
        import numpy as np
        
        if not self.core.original_image:
            raise ValueError("No image loaded")
        
        current_shape = self._get_current_shape()
        if not current_shape:
            raise ValueError("No valid shape defined")
        
        # Check if we have 16-bit data to preserve
        has_16bit = hasattr(self.core.original_image, '_stampz_16bit_data')
        print(f"DEBUG get_cropped_image: has _stampz_16bit_data: {has_16bit}")
        
        # Create mask
        mask = Image.new('L', self.core.original_image.size, 0)

        if isinstance(current_shape, (Circle, Oval)):
            image_height = self.core.original_image.height

            image_center = Point(
                current_shape.center.x,
                image_height - current_shape.center.y
            )

            if isinstance(current_shape, Circle):
                mask_shape = Circle(image_center, current_shape.radius)
            else:
                mask_shape = Oval(
                    image_center,
                    current_shape.width,
                    current_shape.height
                )

            # Generate the rounded mask using exact integer pixel bounds
            if isinstance(current_shape, Circle):
                crop_width = round(current_shape.radius * 2)
                crop_height = crop_width
            else:
                crop_width = round(current_shape.width)
                crop_height = round(current_shape.height)

            crop_left = round(mask_shape.center.x - crop_width / 2)
            crop_top = round(mask_shape.center.y - crop_height / 2)

            draw = ImageDraw.Draw(mask)
            draw.ellipse(
                (
                    crop_left,
                    crop_top,
                    crop_left + crop_width - 1,
                    crop_top + crop_height - 1
                ),
                fill=255
            )

        elif self.current_shape_type in (ShapeType.RECTANGLE, ShapeType.SQUARE):
            # Convert Cartesian coordinates to Pillow image coordinates
            left, bottom, right, top = current_shape
            image_height = self.core.original_image.height

            image_top = image_height - top
            image_bottom = image_height - bottom

            draw = ImageDraw.Draw(mask)
            crop_width = round(self.shape_width)
            crop_height = round(self.shape_height)

            crop_left = round(self.shape_center.x - crop_width / 2)
            crop_top = round(
                self.core.original_image.height
                - self.shape_center.y
                - crop_height / 2
            )

            draw.rectangle(
                (
                    crop_left,
                    crop_top,
                    crop_left + crop_width - 1,
                    crop_top + crop_height - 1
                ),
                fill=255
            )

        else:
            # Handle polygon
            # Convert vertices from Cartesian to image coordinates
            image_height = self.core.original_image.height
            vertices_xy = [
                (v.x, image_height - v.y) for v in current_shape
            ]
            draw = ImageDraw.Draw(mask)
            draw.polygon(vertices_xy, fill=255)
            print(f"DEBUG: Crop mask vertices: {vertices_xy}")

        # Get bounding box in Pillow image coordinates
        if isinstance(current_shape, (Circle, Oval)):
            if isinstance(current_shape, Circle):
                crop_width = round(current_shape.radius * 2)
                crop_height = crop_width
            else:
                crop_width = round(current_shape.width)
                crop_height = round(current_shape.height)

            crop_left = round(mask_shape.center.x - crop_width / 2)
            crop_top = round(mask_shape.center.y - crop_height / 2)

            bbox = (
                crop_left,
                crop_top,
                crop_left + crop_width,
                crop_top + crop_height
            )

        elif self.current_shape_type in (ShapeType.RECTANGLE, ShapeType.SQUARE):
            crop_width = round(self.shape_width)
            crop_height = round(self.shape_height)

            crop_left = round(self.shape_center.x - crop_width / 2)
            crop_top = round(
                self.core.original_image.height
                - self.shape_center.y
                - crop_height / 2
            )

            bbox = (
                crop_left,
                crop_top,
                crop_left + crop_width,
                crop_top + crop_height
            )

        else:
            bbox = self._get_polygon_bbox()

        # Handle 16-bit images specially to preserve precision
        if has_16bit:
            # Crop the 16-bit numpy array directly
            img_16bit = self.core.original_image._stampz_16bit_data
            mask_array = np.array(mask)
            
            # Preserve original 16-bit analytical RGB values.
            # Transparency is stored separately from the RGB array.
            left, top, right, bottom = bbox

            cropped_16bit = np.array(
                img_16bit[top:bottom, left:right],
                copy=True
            )

            cropped_mask = np.array(
                mask.crop(bbox),
                dtype=np.uint8
            )

            # Construct an RGBA display image with transparent areas.
            # This is display-only; analytical values remain 16-bit.
            cropped_rgb8 = np.round(
                cropped_16bit[:, :, :3].astype(np.float64) / 257.0
            ).astype(np.uint8)

            cropped = Image.fromarray(cropped_rgb8, mode='RGB')
            cropped.putalpha(Image.fromarray(cropped_mask, mode='L'))

            # Preserve the analytical RGB data and separate alpha mask.
            cropped._stampz_16bit_data = cropped_16bit[:, :, :3]
            cropped._stampz_alpha_mask = cropped_mask
            cropped._stampz_is_raw = getattr(
                self.core.original_image, '_stampz_is_raw', False
            )
            cropped._stampz_16bit_encoding = getattr(
                self.core.original_image, '_stampz_16bit_encoding', None
            )

            print(
                f"DEBUG get_cropped_image: preserved 16-bit RGB "
                f"{cropped_16bit.shape}, alpha {cropped_mask.shape}"
            )
            
            return cropped
        
        # Standard 8-bit cropping
        # Apply mask and crop. The resulting image is always RGBA: pixels
        # outside the shape have alpha=0 (fully transparent) and pixels
        # inside keep their original colour. Returning RGBA preserves the
        # shape when saved as PNG or TIFF (both support alpha). The save
        # manager will flatten RGBA onto white only when saving as JPEG,
        # so legacy behaviour is retained for that case.
        orig_rgba = self.core.original_image.convert('RGBA')
        result = Image.new('RGBA', self.core.original_image.size, (0, 0, 0, 0))
        result.paste(orig_rgba, mask=mask)
        
        cropped = result.crop(bbox)
        return cropped
    
    def _get_current_shape(self):
        """Get the current shape object."""
        if self.current_shape_type == ShapeType.POLYGON:
            if len(self.vertices) < 3:
                return None
            return self.vertices
        elif self.current_shape_type == ShapeType.CIRCLE:
            if not self.shape_center or self.shape_radius is None:
                return None
            return Circle(self.shape_center, self.shape_radius)
        elif self.current_shape_type == ShapeType.OVAL:
            if not self.shape_center or self.shape_width is None or self.shape_height is None:
                return None
            return Oval(self.shape_center, self.shape_width, self.shape_height)
        elif self.current_shape_type in (ShapeType.RECTANGLE, ShapeType.SQUARE):
            if (self.shape_center is None or
                    self.shape_width is None or
                    self.shape_height is None):
                return None

            if self.shape_width <= 0 or self.shape_height <= 0:
                return None

            return (
                self.shape_center.x - self.shape_width / 2,
                self.shape_center.y - self.shape_height / 2,
                self.shape_center.x + self.shape_width / 2,
                self.shape_center.y + self.shape_height / 2,
            )      
        return None
    
    def _get_polygon_bbox(self) -> Tuple[int, int, int, int]:
        """Get bounding box for current polygon."""
        if not self.vertices:
            return (0, 0, 0, 0)
        
        # Get x coordinates (same in both systems)
        min_x = min(v.x for v in self.vertices)
        max_x = max(v.x for v in self.vertices)
        
        # Get y coordinates in Cartesian space (y=0 at bottom)
        max_cartesian_y = max(v.y for v in self.vertices)
        min_cartesian_y = min(v.y for v in self.vertices)
        
        # Transform to image space (y=0 at top)
        image_height = self.core.original_image.height
        # The highest y in Cartesian becomes lowest in image space
        min_y = image_height - max_cartesian_y
        max_y = image_height - min_cartesian_y
        
        return (int(min_x), int(min_y), int(max_x), int(max_y))
    
    def update_display(self) -> None:
        """Update the shape display and mask."""
        if not self.core.original_image:
            return
        
        # Clear previous shape visuals
        self.canvas.delete('shape')
        self.canvas.delete('vertex')
        self.canvas.delete('mask')
        
        # Draw current shape
        if self.current_shape_type == ShapeType.POLYGON:
            self._draw_polygon()
        elif self.current_shape_type == ShapeType.CIRCLE:
            self._draw_circle()
        elif self.current_shape_type == ShapeType.OVAL:
            self._draw_oval()
        elif self.current_shape_type in (ShapeType.RECTANGLE, ShapeType.SQUARE):
            self._draw_rectangle()
        
        # Update mask
        self._update_mask()
        
        # Update dimensions display
        self._update_dimensions_display()
    
    def _draw_polygon(self) -> None:
        """Draw polygon shape and vertices."""
        # Always draw vertices, even if there's only one
        for i, vertex in enumerate(self.vertices):
            screen_pos = self.core.image_to_screen_coords(vertex.x, vertex.y)
            
            # Choose color based on state
            if i == self.active_vertex:
                color = self.ACTIVE_VERTEX_COLOR
            elif i == self.hover_vertex:
                color = self.PREVIEW_COLOR
            else:
                color = self.current_color
            
            self.canvas.create_oval(
                screen_pos[0] - self.VERTEX_RADIUS,
                screen_pos[1] - self.VERTEX_RADIUS,
                screen_pos[0] + self.VERTEX_RADIUS,
                screen_pos[1] + self.VERTEX_RADIUS,
                fill=color, outline='white', width=2, tags='vertex'
            )
        
        # Only draw lines if we have at least 2 vertices
        if len(self.vertices) < 2:
            return
        
        # Get validation state for line styling
        validation_state = get_polygon_validation_state(self.vertices)
        
        # Debug output for validation state
        if len(self.vertices) >= 4 and len(self.vertices) % 2 == 0:
            from utils.geometry import are_opposite_sides_parallel, are_corners_square
            sides_parallel = are_opposite_sides_parallel(self.vertices, 0.5)
            corners_square = are_corners_square(self.vertices, 2.0)
            print(f"DEBUG: Validation - {len(self.vertices)} vertices, parallel: {sides_parallel}, square: {corners_square}, state: {validation_state}")
        
        # Determine line style and color based on validation state
        if validation_state == PolygonValidationState.ODD_VERTICES:
            line_style = {}  # Solid lines (no dash)
            color = self.current_color
        elif validation_state == PolygonValidationState.FULLY_VALID:
            line_style = {}  # Solid lines
            color = '#00CC00'  # Green for fully valid
        elif validation_state == PolygonValidationState.PARTIAL_VALID:
            line_style = {'dash': (15, 5)}  # Long dashes - some criteria met
            color = '#FFAA00'  # Orange for partial
        else:  # INVALID
            line_style = {'dash': (3, 3)}  # Very short dashes - invalid
            color = '#FF3300'  # Red for invalid
        
        # Draw lines with appropriate styling
        for i in range(len(self.vertices)):
            start = self.vertices[i]
            end = self.vertices[(i + 1) % len(self.vertices)]
            
            start_screen = self.core.image_to_screen_coords(start.x, start.y)
            end_screen = self.core.image_to_screen_coords(end.x, end.y)
            
            self.canvas.create_line(
                start_screen[0], start_screen[1],
                end_screen[0], end_screen[1],
                fill=color, width=2, tags='shape', **line_style
            )
    
    def _draw_circle(self) -> None:
        """Draw circle shape."""
        if not self.shape_center or self.shape_radius is None:
            return
        
        center_screen = self.core.image_to_screen_coords(self.shape_center.x, self.shape_center.y)
        radius_screen = self.shape_radius * self.core.image_scale
        
        self.canvas.create_oval(
            center_screen[0] - radius_screen,
            center_screen[1] - radius_screen,
            center_screen[0] + radius_screen,
            center_screen[1] + radius_screen,
            outline=self.current_color, width=2, tags='shape'
        )
    
    def _draw_oval(self) -> None:
        """Draw oval shape."""
        if not self.shape_center or self.shape_width is None or self.shape_height is None:
            return
        
        center_screen = self.core.image_to_screen_coords(self.shape_center.x, self.shape_center.y)
        width_screen = self.shape_width * self.core.image_scale / 2
        height_screen = self.shape_height * self.core.image_scale / 2
        
        self.canvas.create_oval(
            center_screen[0] - width_screen,
            center_screen[1] - height_screen,
            center_screen[0] + width_screen,
            center_screen[1] + height_screen,
            outline=self.current_color, width=2, tags='shape'
        )

    def _draw_rectangle(self) -> None:
        """Draw Rectangle or Square crop selection."""
        if (not self.shape_center or
                self.shape_width is None or
                self.shape_height is None):
            return

        center_screen = self.core.image_to_screen_coords(
            self.shape_center.x, self.shape_center.y
        )

        half_width = self.shape_width * self.core.image_scale / 2
        half_height = self.shape_height * self.core.image_scale / 2

        self.canvas.create_rectangle(
            center_screen[0] - half_width,
            center_screen[1] - half_height,
            center_screen[0] + half_width,
            center_screen[1] + half_height,
            outline=self.current_color,
            width=2,
            tags='shape'
        )
    
    def _update_mask(self) -> None:
        """Update the mask overlay."""
        current_shape = self._get_current_shape()
        if not current_shape:
            return
        
        try:
            # Create mask based on shape type
            if isinstance(current_shape, (Circle, Oval)):
                image_height = self.core.original_image.height
                image_center = Point(
                    current_shape.center.x,
                    image_height - current_shape.center.y
                )

                if isinstance(current_shape, Circle):
                    mask_shape = Circle(image_center, current_shape.radius)
                else:
                    mask_shape = Oval(
                        image_center,
                        current_shape.width,
                        current_shape.height
                    )

                mask_pil = create_shape_mask(
                    self.core.original_image,
                    mask_shape,
                    alpha=self.mask_alpha,
                    highlight_vertices=False,
                    highlight_color=MaskColor.BLACK
                )
                
            elif self.current_shape_type in (ShapeType.RECTANGLE, ShapeType.SQUARE):
                mask_pil = Image.new(
                    'RGBA', self.core.original_image.size, (0, 0, 0, 0)
                )
                draw = ImageDraw.Draw(mask_pil)

                # Convert Cartesian Y to Pillow image coordinates
                left, bottom, right, top = current_shape
                image_height = self.core.original_image.height

                image_top = image_height - top
                image_bottom = image_height - bottom

                draw.rectangle(
                    (left, image_top, right - 1, image_bottom - 1),
                    fill=(0, 0, 0, self.mask_alpha)
                )

            else:
                # Polygon mask
                mask_pil = Image.new('RGBA', self.core.original_image.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(mask_pil)
                # Convert vertices from Cartesian (y=0 at bottom) to image coordinates (y=0 at top)
                image_height = self.core.original_image.height
                vertices_xy = [(v.x, image_height - v.y) for v in current_shape]
                draw.polygon(vertices_xy, fill=(0, 0, 0, self.mask_alpha))
                print(f"DEBUG: Display mask vertices: {vertices_xy}")
            
            # Resize mask to match display
            display_size = (
                int(self.core.original_image.width * self.core.image_scale),
                int(self.core.original_image.height * self.core.image_scale)
            )
            
            if display_size[0] > 0 and display_size[1] > 0:
                mask_resized = mask_pil.resize(display_size, Image.Resampling.LANCZOS)
                self.mask_image = ImageTk.PhotoImage(mask_resized)
                
                # Draw mask
                self.canvas.create_image(
                    self.core.image_offset[0], self.core.image_offset[1],
                    anchor=tk.NW, image=self.mask_image, tags='mask'
                )
        
        except Exception as e:
            logger.error(f"Error updating mask: {e}")
    
    def _update_dimensions_display(self) -> None:
        """Update crop dimensions display."""
        if not self.dimensions_callback:
            return
        
        width = 0
        height = 0
        
        try:
            if self.current_shape_type == ShapeType.POLYGON and len(self.vertices) >= 3:
                bbox = self._get_polygon_bbox()
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
            elif self.current_shape_type == ShapeType.CIRCLE and self.shape_center and self.shape_radius is not None:
                diameter = int(self.shape_radius * 2)
                width = diameter
                height = diameter
            elif self.current_shape_type == ShapeType.OVAL and self.shape_center and self.shape_width is not None and self.shape_height is not None:
                width = int(self.shape_width)
                height = int(self.shape_height)
            elif self.current_shape_type in (ShapeType.RECTANGLE, ShapeType.SQUARE):
                if (self.shape_center is not None and
                        self.shape_width is not None and
                        self.shape_height is not None):
                    width = int(self.shape_width)
                    height = int(self.shape_height)
            
            self.dimensions_callback(width, height)
        
        except Exception:
            self.dimensions_callback(0, 0)
    
    def _update_fine_square_button(self) -> None:
        """Enable/disable Fine Square button based on current shape.
        Only enabled for 4-vertex polygons."""
        has_button = (
            hasattr(self.canvas, 'main_app') and
            hasattr(self.canvas.main_app, 'control_panel') and
            hasattr(self.canvas.main_app.control_panel, 'fine_square_btn')
        )
        
        if has_button:
            # Enable Fine Square only for 4-vertex polygons
            enable_fine_square = (
                self.current_shape_type == ShapeType.POLYGON and
                len(self.vertices) == 4
            )
            state = 'normal' if enable_fine_square else 'disabled'
            self.canvas.main_app.control_panel.fine_square_btn.config(state=state)
