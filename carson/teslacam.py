"""
A module of utilities that pertain to dealing with camera footage recorded to
the USB drive '/TeslaCam'.  This is very much untested and should be used with
caution.
"""

import os, re
from os.path import exists, isdir, abspath, join, basename
from datetime import datetime, timedelta
from collections import namedtuple
from moviepy.editor import CompositeVideoClip, VideoFileClip, TextClip

Bounds = namedtuple('Bounds', 'width height')
Batch = namedtuple('Batch', 'filename fnfront fnleft fnright root')


def compose(directory=None, set_name=None, recursive=None, keep_originals=True, trim=None, resize=None, overwrite=False, verbose=False):
    """
    Create a composite video of the front cam with the left/right repeater cams into a new single file.

    directory
      The directory to scan for mp4 files.  If omitted, the currect directory is used and `recursive` is
      set to `True` (unless otherwise specified).

    set_name
      The specific set name to pick out.  It's a simple name match on the group of files so it can be something
      like `_06-30-31` to capture a single set with that timestamp from any day.  Or `2019-06-24` to
      capture everything from that date.  No dates are calculated or parsed with this so date format does
      not matter.

    recursive
      After scanning/collating the current directory, search/compose all sub directories.

    keep_originals
      After the composition is complete into one mp4 file, should the original files be retained?

    trim
      If specified, this should be a tuple with two ints indicating the second start/stop respectively to trim
      the final clip to.

    resize
      If specified, this should be a tuple with two ints indicating the width and height respectively of the
      final clip's dimensions.

    overwrite
      Default is False.  When False, the set will be skipped assuming it is already composited when the
      calculated composite filename already exists.
    """

    batch_started = datetime.now()

    font_args = dict(font='Helvetica', fontsize=40, color='white')

    if not directory:
        directory = '.'
        recursive = True if recursive is None else recursive

    if not isdir(directory):
        raise FileNotFoundError(f'The directory "{directory}" does not exist.')

    roots = [abspath(directory)]
    if verbose:
        print(f'walking directory: {roots[0]}' if recursive else f'directory: {roots[0]}')
    if recursive:
        for root, dirs, files in os.walk(roots[0]):
            roots.extend(join(root, d) for d in dirs if not d.startswith('.'))

    if verbose and recursive:
        print(f'Found {len(roots):,} directories.')

    re_cam_name = re.compile(r'.*(?P<camname>left|front|right).*')
    re_set_name = re.compile(r'\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}')

    def _cam_name_from_fn(fn):
        camname = 'other'
        match = re_cam_name.match(fn)
        if match:
            camname = match.groups()[0]
        return camname.capitalize()

    root_nbr = 0
    batches = []
    for root_nbr, root in enumerate(roots):
        root_nbr += 1
        if verbose:
            print(f'\ndirectory nbr={root_nbr:,} path={root}')
        files = [f for f in os.listdir(root) if not f.startswith('.') and not isdir(join(root, f)) and f.lower().endswith('.mp4')]
        sets = {f[:19] for f in files if f.lower().endswith('.mp4') and re_set_name.match(f[:19]) and (not set_name or set_name in f)}
        sets_found = 0
        for itr_set in sorted(sets):
            if set_name and set_name not in itr_set:
                continue

            filename = f'{itr_set}.mp4'
            if not overwrite and exists(join(root, filename)):
                if verbose:
                    print(f'set {itr_set}: {join(root, filename)} already exists.  Skipping.')
                continue

            fnames = [f for f in sorted(files) if f.startswith(itr_set) and f != filename]
            if verbose or len(fnames) != 3:
                print(f'set={itr_set} fnames={fnames}')
            if len(fnames) != 3:
                print(f'WARNING: Expected three files for the set.  Found {len(fnames)} so skipping.')
                continue

            fnfront, fnleft, fnright = fnames
            assert 'front' in fnfront and 'left' in fnleft and 'right' in fnright
            batches.append(Batch(filename, fnfront, fnleft, fnright, root))
            sets_found += 1
        if verbose:
            print(f'Composites for directory: {sets_found:,}' if sets_found else 'None found')

    conversion_started = datetime.now()
    if verbose:
        print(f'\nStarting composites.  batches={len(batches)}')

    previous_directory = ''
    # For logging purposes.  If the current batch's directory is different than the one before, start a new line so we
    # don't have to log the directory with each composite.

    durations = []
    for batch_nbr, batch in enumerate(batches):
        if verbose and previous_directory != batch.root:
            print(f'Directory: {batch.root}')
            previous_directory = batch.root

        batch_nbr += 1
        print(f'{batch_nbr:,} of {len(batches):,} {batch.filename}', end='  ')

        # Batch = namedtuple('Batch', 'filename fnfront fnleft fnright root')
        batch_started = datetime.now()
        try:
            clips = [VideoFileClip(join(batch.root, f), audio=False) for f in (batch.fnleft, batch.fnfront, batch.fnright)]

            clips_bounds = [Bounds(c.w, c.h) for c in clips]
            # The dimensions of each clip in the composite

            composite_size = (sum(c.w for c in clips), max(c.h for c in clips))
            # The overall size of the composite video

            if trim:
                # Do we need to trim the video to start seconds and stop seconds specified in the trim tuple?
                clips = [c.subclip(*trim) for c in clips]

            clips = [c.set_pos((sum(b.width for b in clips_bounds[:i]), 0)) for i, c in enumerate(clips)]
            composite_duration = max(c.duration for c in clips)

            labels = [TextClip(_cam_name_from_fn(basename(c.filename)), **font_args).set_duration(composite_duration) for c in clips]
            labels = [l.set_pos((30 + sum(b.width for b in clips_bounds[:i]), clips_bounds[i].height - 30 - font_args['fontsize'])) for i, l in enumerate(labels)]

            comp = CompositeVideoClip(clips + labels, size=composite_size)
            if resize:
                comp = comp.resize(width=resize[0], height=resize[1])
            # logger = verbose and 'bar' or None
            comp.write_videofile(join(batch.root, batch.filename), verbose=False, logger=None)

            duration = datetime.now() - batch_started
            durations.append(duration)
            if verbose:
                print(f'Duration={duration}  Overall={timedelta(seconds=sum(d.total_seconds() for d in durations))}')

        except KeyboardInterrupt:
            print(f'\nAborted because of Ctrl+C.  Duration: {datetime.now() - batch_started}')
            skipped = len(batches) - batch_nbr
            if skipped:
                print(f'Warning! Skipped {skipped} conversions.')
            break

    if verbose:
        avg = sum(d.total_seconds() for d in durations) / len(durations) if len(durations) else 0
        print(f'Overall Duration: {datetime.now() - conversion_started}  Averaged {avg:,.4f} seconds per batch for {len(durations):,} batches.\n')
