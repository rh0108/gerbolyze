#!/usr/bin/env python3

import subprocess
import zipfile
import tempfile
import os.path as path
import os
import sys
import shutil
import math

import gerber
from gerber.render import GerberCairoContext
import numpy as np
import cv2

def paste_image(target_gerber:str, outline_gerber:str, source_img:np.ndarray, extend_overlay_r_mil:float=12, extend_picture_r_mil:float=2):
    outline = gerber.loads(outline_gerber)
    (minx, maxx), (miny, maxy) = outline.bounds
    grbw, grbh = maxx - minx, maxy - miny

    imgh, imgw = source_img.shape
    scale = math.ceil(max(imgw/grbw, imgh/grbh)) # scale is in dpi

    target = gerber.loads(target_gerber)
    (tminx, tmaxx), (tminy, tmaxy) = target.bounds

    with tempfile.TemporaryDirectory() as tmpdir:
        img_file = path.join(tmpdir, 'target.png')

        fg, bg = gerber.render.RenderSettings((1, 1, 1)), gerber.render.RenderSettings((0, 0, 0))
        ctx = GerberCairoContext(scale=scale)
        ctx.render_layer(target, settings=fg, bgsettings=bg)
        ctx.dump(img_file)

        original_img = cv2.imread(img_file, cv2.IMREAD_GRAYSCALE)
    r = 1+2*max(1, int(extend_overlay_r_mil/1000 * scale))
    target_img = cv2.blur(original_img, (r, r))
    _, target_img = cv2.threshold(target_img, 255//(1+r), 255, cv2.THRESH_BINARY)

    qr = 1+2*max(1, int(extend_picture_r_mil/1000 * scale))
    # source_img = cv2.blur(source_img, (r, r))
    # cv2.imwrite('/tmp/03blurred.png', source_img)
    source_img = source_img[::-1]
    _, source_img = cv2.threshold(source_img, 127, 255, cv2.THRESH_BINARY)
    cv2.imwrite('/tmp/06thresh.png', source_img)
    tgth, tgtw = target_img.shape
    padded_img = np.zeros(shape=(max(imgh, tgth), max(imgw, tgtw)), dtype=source_img.dtype)
    padded_img[(tgth-imgh)//2:tgth-((tgth-imgh+1)//2), (tgtw-imgw)//2:tgtw-((tgtw-imgw+1)//2)] = source_img

    cv2.imwrite('/tmp/10padded.png', padded_img)
    cv2.imwrite('/tmp/20target.png', target_img)
    out_img = (np.multiply((padded_img/255.0), (target_img/255.0) * -1 + 1) * 255).astype(np.uint8)

    cv2.imwrite('/tmp/30multiplied.png', out_img)
    cv2.imwrite('/tmp/40vis.png', out_img + original_img)

    plot_contours(out_img, target, offx=(tminx, tminy), scale=scale)

    from gerber.render import rs274x_backend
    ctx = rs274x_backend.Rs274xContext(target.settings)
    target.render(ctx)
    return ctx.dump().getvalue()


def plot_contours(img:np.ndarray, layer:gerber.rs274x.GerberFile, offx:tuple, scale:float, debug=lambda *args:None):
    imgh, imgw = img.shape

    # Extract contours
    img_cont_out, contours, hierarchy = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_TC89_KCOS)

    aperture = list(layer.apertures)[0]

    # XXX
    layer.primitives.clear()

    from gerber.primitives import Line, Region
    debug('offx', offx, 'scale', scale)

    xbias, ybias = offx
    def map(coord):
        x, y = coord
        # FIXME sometimes only ybias is needed
        return (x/scale, y/scale + ybias)
    def contour_lines(c):
        return [ Line(map(start), map(end), aperture, level_polarity='dark', units=layer.settings.units)
            for start, end in zip(c, np.vstack((c[1:], c[:1]))) ]

    done = []
    process_stack = [-1]
    next_process_stack = []
    is_dark = True
    while len(done) != len(contours):
        for i, (_1, _2, _3, parent) in enumerate(hierarchy[0]):
            if parent in process_stack:
                contour = contours[i]
                polarity = 'dark' if is_dark else 'clear'
                debug('rendering {} with parent {} as {} with {} vertices'.format(i, parent, polarity, len(contour)))
                debug('process_stack is', process_stack)
                debug()
                layer.primitives.append(Region(contour_lines(contour[:,0]), level_polarity=polarity, units=layer.settings.units))
                next_process_stack.append(i)
                done.append(i)
        debug('skipping to next level')
        process_stack, next_process_stack = next_process_stack, []
        is_dark = not is_dark
    debug('done', done)

# Utility foo
# ===========

def find_gerber_in_dir(dir_path, file_or_ext):
    lname = path.join(dir_path, file_or_ext)
    if path.isfile(lname):
        with open(lname, 'r') as f:
            return lname, f.read()

    contents = os.listdir(dir_path)
    for entry in contents:
        if entry.lower().endswith(file_or_ext.lower()):
            lname = path.join(dir_path, entry)
            if not path.isfile(lname):
                continue
            with open(lname, 'r') as f:
                return lname, f.read()

    raise ValueError('Cannot find file or suffix "{}" in dir {}'.format(file_or_ext, dir_path))

def find_gerber_in_zip(zip_path, file_or_ext):
    with zipfile.ZeipFile(zip_path, 'r') as lezip:
        nlist = [ item.filename for item in zipin.infolist() ]
        if file_or_ext in nlist:
            return file_or_ext, lezip.read(file_or_ext)

        for n in nlist:
            if n.lower().endswith(file_or_ext.lower()):
                return n, lezip.read(n)

    raise ValueError('Cannot find file or suffix "{}" in zip {}'.format(file_or_ext, dir_path))

def replace_file_in_zip(zip_path, filename, contents):
    with tempfile.TemporaryDirectory() as tmpdir:
        tempname = path.join(tmpdir, 'out.zip')
        with zipfile.ZipFile(zip_path, 'r') as zipin, zipfile.ZipFile(tempname, 'w') as zipout:
            for item in zipin.infolist():
                if item.filename != filename:
                    zipout.writestr(item, zipin.read(item.filename))
            zipout.writestr(filename, contents)
        shutil.move(tempname, zip_path)

def paste_image_file(zip_or_dir, target, outline, source_img):
    if path.isdir(zip_or_dir):
        tname, target = find_gerber_in_dir(zip_or_dir, target)
        _, outline = find_gerber_in_dir(zip_or_dir, outline)
        
        out = paste_image(target, outline, source_img)

        # XXX
        with open('/tmp/out.GTO', 'w') as f:
#        with open(tname, 'w') as f:
            f.write(out)
    elif zipfile.is_zipfile(zip_or_dir):
        tname, target = find_gerber_in_zip(zip_or_dir, target)
        _, outline = find_gerber_in_zip(zip_or_dir, outline)
        
        out = paste_image(target, outline, source_img)
        replace_file_in_zip(zip_or_dir, tname, out)
    else:
        raise ValueError('{} does not look like either a folder or a zip file')

# Command line interface
# ======================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--target', default='.GTO', help='Target layer. Filename or extension in target folder/zip')
    parser.add_argument('-o', '--outline', default='.GKO', help='Target outline layer. Filename or extension in target folder/zip')
    parser.add_argument('zip_or_dir', default='.', nargs='?', help='Optional folder or zip with target files')
    parser.add_argument('source', help='Source image')
    args = parser.parse_args()

    source_img = cv2.imread(args.source, cv2.IMREAD_GRAYSCALE)
    paste_image_file(args.zip_or_dir, args.target, args.outline, source_img)
