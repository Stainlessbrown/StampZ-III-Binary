import sys
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.self_contained_crop import write_self_contained_crop, read_self_contained_crop, is_self_contained_crop, CropTiffError


def make_crop():
    h, w = 12, 16
    arr = (np.arange(h*w*3).reshape(h,w,3).astype(np.uint16)*97)
    mask = np.full((h,w),255,dtype=np.uint8)
    mask[:2,:3] = 0
    preview = np.dstack([(arr//257).astype(np.uint8),mask])
    im = Image.fromarray(preview,'RGBA')
    im._stampz_16bit_data = arr
    im._stampz_alpha_mask = mask
    im._stampz_16bit_encoding = 'linear'
    im._stampz_display_encoding = 'linear'
    im._stampz_is_raw = True
    im._stampz_crop_record = {'bbox':[5,6,21,18], 'parent_size':[40,50], 'operation':'mask-and-crop', 'parent_rgb16_sha256':'abc'}
    im._stampz_crop_parent_file = 'test source.tif'
    return im

def test_roundtrip_renamed(tmp_path):
    src=make_crop()
    dest=tmp_path/'no suffix whatsoever.tif'
    write_self_contained_crop(dest, src)
    assert is_self_contained_crop(dest)
    im, md=read_self_contained_crop(dest)
    np.testing.assert_array_equal(im._stampz_16bit_data,src._stampz_16bit_data)
    np.testing.assert_array_equal(im._stampz_alpha_mask,src._stampz_alpha_mask)
    assert im._stampz_is_raw and im._stampz_authenticated_crop
    assert md['crop_authenticated']
    renamed=tmp_path/'pretend-aligned-crp.tif'; dest.rename(renamed)
    im, _=read_self_contained_crop(renamed)
    np.testing.assert_array_equal(im._stampz_16bit_data,src._stampz_16bit_data)

def test_integrity_tamper(tmp_path):
    src=make_crop()
    dest=tmp_path/'crop.tif'
    write_self_contained_crop(dest,src)
    with tifffile.TiffFile(dest) as tif:
        original=tif.pages[0].asarray().copy()
        preview=tif.pages[1].asarray().copy()
        desc=tif.pages[0].description
    original[3,4,0]^=1
    with tifffile.TiffWriter(dest) as writer:
        writer.write(original, photometric='rgb',extrasamples='UNASSALPHA', metadata=None, description=desc,software='StampZ-Crop-TIFF-v1')
        writer.write(preview, photometric='rgb',extrasamples='UNASSALPHA',metadata=None)
    with pytest.raises(CropTiffError):
        read_self_contained_crop(dest)

def test_atomic_no_overwrite(tmp_path):
    src=make_crop(); dest=tmp_path/'crop.tif'
    write_self_contained_crop(dest,src)
    before=dest.read_bytes()
    with pytest.raises(FileExistsError):
        write_self_contained_crop(dest,src)
    assert dest.read_bytes()==before

def test_reject_unknown_encoding(tmp_path):
    src=make_crop(); src._stampz_16bit_encoding=None
    with pytest.raises(CropTiffError):
        write_self_contained_crop(tmp_path/'bad.tif',src)

def test_srgb_roundtrip(tmp_path):
    src=make_crop(); src._stampz_16bit_encoding='srgb';src._stampz_display_encoding='srgb';src._stampz_is_raw=False
    write_self_contained_crop(tmp_path/'ordinary.tif',src)
    im, meta=read_self_contained_crop(tmp_path/'ordinary.tif')
    assert im._stampz_16bit_encoding=='srgb' and not meta['is_raw']

def test_ordinary_rgba16_not_misclassified_as_legacy_layer(tmp_path):
    from utils.native_layer_preparation import prepare_native_layer
    pixels = np.zeros((6, 7, 4), dtype=np.uint16)
    pixels[:, :, 3] = 65535
    path = tmp_path / 'renamed-crp-aligned.tif'
    tifffile.imwrite(path, pixels, photometric='rgb', extrasamples='UNASSALPHA',
                      description='StampZ Linear RAW; Encoding=linear; RAW-derived=Yes',
                      metadata=None)
    im = Image.new('RGBA',(7,6))
    assert prepare_native_layer(im,path) is im


def test_legacy_companion_not_silently_ignored(tmp_path):
    from utils.native_layer_preparation import prepare_native_layer, NativeLayerPreparationError
    pixels = np.zeros((6,7,4), dtype=np.uint16)
    pixels[:,:,3] = 65535
    path = tmp_path / 'anything.tif'
    tifffile.imwrite(path,pixels,photometric='rgb',extrasamples='UNASSALPHA',metadata=None)
    (tmp_path / 'anything.layer.json').write_text('{"invalid":true}')
    with pytest.raises(NativeLayerPreparationError):
        prepare_native_layer(Image.new('RGBA',(7,6)),path)


def test_tampered_preview_rejected(tmp_path):
    src = make_crop(); dest = tmp_path / 'crop.tif'
    write_self_contained_crop(dest,src)
    with tifffile.TiffFile(dest) as tf:
        native=tf.pages[0].asarray().copy()
        preview=tf.pages[1].asarray().copy()
        desc=tf.pages[0].description
    preview[4,5,1] ^= 1
    with tifffile.TiffWriter(dest) as tf:
        tf.write(native,photometric='rgb',extrasamples='UNASSALPHA',metadata=None,description=desc,software='StampZ-Crop-TIFF-v1')
        tf.write(preview,photometric='rgb',extrasamples='UNASSALPHA',metadata=None)
    with pytest.raises(CropTiffError):
        read_self_contained_crop(dest)
